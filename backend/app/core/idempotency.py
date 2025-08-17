"""
Idempotency implementation with Redis locks and deterministic keys.
Ensures OCR operations are not duplicated for the same image.
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import redis
from redis.exceptions import LockError

from app.config import settings
from app.core.telemetry import logger
from app.core.metrics import cache_hit_total, cache_miss_total

# Redis client for idempotency
redis_client = redis.from_url(settings.REDIS_URL) if settings.USE_REDIS else None


class IdempotencyKey:
    """Generate deterministic idempotency keys for OCR operations."""
    
    @staticmethod
    def generate(
        image_hash: str,
        pipeline_version: str = "v2.0.0",
        scryfall_snapshot: str = None,
        ocr_config: Dict[str, Any] = None,
        language: str = "en"
    ) -> str:
        """
        Generate a deterministic idempotency key.
        
        Args:
            image_hash: SHA256 hash of the image
            pipeline_version: Version of the OCR pipeline
            scryfall_snapshot: Version/date of Scryfall data
            ocr_config: OCR configuration (confidence threshold, etc.)
            language: Language for OCR
            
        Returns:
            Deterministic idempotency key
        """
        # Default OCR config
        if ocr_config is None:
            ocr_config = {
                "min_conf": settings.OCR_MIN_CONF,
                "min_lines": settings.OCR_MIN_LINES,
                "vision_enabled": settings.ENABLE_VISION_FALLBACK,
                "preprocessing": "4-variant"
            }
        
        # Default Scryfall snapshot to today's date
        if scryfall_snapshot is None:
            scryfall_snapshot = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Create deterministic key components
        key_data = {
            "image": image_hash,
            "pipeline": pipeline_version,
            "scryfall": scryfall_snapshot,
            "config": ocr_config,
            "lang": language
        }
        
        # Generate SHA256 of the key data
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()
        
        return f"idem:{key_hash[:16]}"


class IdempotentOperation:
    """Manage idempotent operations with Redis locks."""
    
    def __init__(self, key: str, ttl_seconds: int = None):
        """
        Initialize idempotent operation.
        
        Args:
            key: Idempotency key
            ttl_seconds: TTL for cached results (defaults to GDPR retention)
        """
        self.key = key
        self.lock_key = f"{key}:lock"
        self.result_key = f"{key}:result"
        
        # Default TTL based on GDPR job retention
        if ttl_seconds is None:
            ttl_seconds = settings.DATA_RETENTION_JOBS_HOURS * 3600
        
        self.ttl = ttl_seconds
        self.redis = redis_client
        self.lock = None
    
    def acquire_lock(self, timeout: float = 30.0) -> bool:
        """
        Acquire a distributed lock for this operation.
        
        Args:
            timeout: Maximum time to wait for lock
            
        Returns:
            True if lock acquired, False otherwise
        """
        if not self.redis:
            return True  # No Redis, proceed without lock
        
        try:
            # Create lock with auto-release after timeout
            self.lock = self.redis.lock(
                self.lock_key,
                timeout=timeout,
                blocking_timeout=5.0  # Wait up to 5 seconds to acquire
            )
            
            acquired = self.lock.acquire(blocking=True)
            
            if acquired:
                logger.info(f"Acquired lock for idempotency key: {self.key}")
            else:
                logger.warning(f"Failed to acquire lock for: {self.key}")
            
            return acquired
            
        except LockError as e:
            logger.error(f"Lock error for {self.key}: {e}")
            return False
    
    def release_lock(self):
        """Release the distributed lock."""
        if self.lock:
            try:
                self.lock.release()
                logger.info(f"Released lock for: {self.key}")
            except LockError:
                # Lock may have auto-expired
                pass
    
    def get_cached_result(self) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available.
        
        Returns:
            Cached result or None
        """
        if not self.redis:
            return None
        
        try:
            result = self.redis.get(self.result_key)
            if result:
                cache_hit_total.labels(cache_type='idempotency').inc()
                logger.info(f"Cache hit for idempotency key: {self.key}")
                return json.loads(result)
            else:
                cache_miss_total.labels(cache_type='idempotency').inc()
                return None
                
        except Exception as e:
            logger.error(f"Error getting cached result for {self.key}: {e}")
            return None
    
    def cache_result(self, result: Dict[str, Any]) -> bool:
        """
        Cache the result with TTL.
        
        Args:
            result: Result to cache
            
        Returns:
            True if cached successfully
        """
        if not self.redis:
            return False
        
        try:
            result_json = json.dumps(result)
            self.redis.setex(
                self.result_key,
                self.ttl,
                result_json
            )
            logger.info(f"Cached result for {self.key} with TTL {self.ttl}s")
            return True
            
        except Exception as e:
            logger.error(f"Error caching result for {self.key}: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - always release lock."""
        self.release_lock()


async def idempotent_ocr(
    image_hash: str,
    ocr_function,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute OCR operation idempotently.
    
    Args:
        image_hash: SHA256 hash of the image
        ocr_function: Async function to execute OCR
        **kwargs: Additional arguments for OCR function
        
    Returns:
        OCR result (cached or fresh)
    """
    # Generate idempotency key
    key = IdempotencyKey.generate(
        image_hash=image_hash,
        ocr_config={
            "min_conf": settings.OCR_MIN_CONF,
            "min_lines": settings.OCR_MIN_LINES,
            "vision_enabled": settings.ENABLE_VISION_FALLBACK
        }
    )
    
    with IdempotentOperation(key) as op:
        # Check for cached result
        cached = op.get_cached_result()
        if cached:
            cached["from_cache"] = True
            return cached
        
        # Acquire lock to prevent concurrent execution
        if not op.acquire_lock():
            # Another process is handling this - wait and retry
            time.sleep(1)
            cached = op.get_cached_result()
            if cached:
                cached["from_cache"] = True
                return cached
            
            # Still no result, proceed anyway
            logger.warning(f"Proceeding without lock for {key}")
        
        # Execute OCR operation
        try:
            result = await ocr_function(image_hash=image_hash, **kwargs)
            result["idempotency_key"] = key
            result["from_cache"] = False
            
            # Cache the result
            op.cache_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"OCR operation failed for {key}: {e}")
            raise


def cleanup_expired_keys():
    """
    Clean up expired idempotency keys.
    This is handled automatically by Redis TTL, but this function
    can be used for manual cleanup or monitoring.
    """
    if not redis_client:
        return
    
    try:
        # Count keys about to expire
        expiring_soon = 0
        for key in redis_client.scan_iter(match="idem:*:result"):
            ttl = redis_client.ttl(key)
            if 0 < ttl < 3600:  # Expiring within an hour
                expiring_soon += 1
        
        logger.info(f"Idempotency keys expiring soon: {expiring_soon}")
        
    except Exception as e:
        logger.error(f"Error during idempotency cleanup: {e}")