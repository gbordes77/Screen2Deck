"""
Redis cache manager for Screen2Deck.
Handles caching of OCR results, Scryfall data, and job status.
"""

import redis
import json
import hashlib
from typing import Optional, Any, Dict
from datetime import timedelta
from functools import wraps
import pickle
from .config import get_settings
from .telemetry import logger

S = get_settings()

class CacheManager:
    """Centralized cache management with Redis backend."""
    
    def __init__(self):
        """Initialize Redis connection if enabled."""
        self.enabled = S.USE_REDIS
        self.redis_client = None
        
        if self.enabled:
            try:
                self.redis_client = redis.from_url(
                    str(S.REDIS_URL),
                    decode_responses=False,  # Handle binary data
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, falling back to memory cache: {e}")
                self.enabled = False
        
        # Fallback memory cache
        self.memory_cache: Dict[str, Any] = {}
    
    def _make_key(self, prefix: str, *args) -> str:
        """Generate cache key from prefix and arguments."""
        key_parts = [prefix] + [str(arg) for arg in args]
        return ":".join(key_parts)
    
    def _hash_key(self, data: str) -> str:
        """Hash long keys to avoid Redis key length limits."""
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self.enabled and self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    return pickle.loads(data)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = 1800) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default 30 minutes)
        """
        try:
            if self.enabled and self.redis_client:
                serialized = pickle.dumps(value)
                return self.redis_client.setex(key, ttl, serialized)
            else:
                self.memory_cache[key] = value
                # Simple memory cache size limit
                if len(self.memory_cache) > 1000:
                    # Remove oldest entries
                    keys_to_remove = list(self.memory_cache.keys())[:100]
                    for k in keys_to_remove:
                        del self.memory_cache[k]
                return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
        return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if self.enabled and self.redis_client:
                return self.redis_client.delete(key) > 0
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            if self.enabled and self.redis_client:
                return self.redis_client.exists(key) > 0
            else:
                return key in self.memory_cache
        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
        return False
    
    # Specialized cache methods
    
    def cache_ocr_result(self, image_hash: str, result: Dict, ttl: int = 3600) -> bool:
        """Cache OCR processing result."""
        key = self._make_key("ocr", image_hash)
        return self.set(key, result, ttl)
    
    def get_ocr_result(self, image_hash: str) -> Optional[Dict]:
        """Get cached OCR result."""
        key = self._make_key("ocr", image_hash)
        return self.get(key)
    
    def cache_scryfall_card(self, card_name: str, card_data: Dict, ttl: int = 86400) -> bool:
        """Cache Scryfall card data (24 hour TTL)."""
        key = self._make_key("scryfall", self._hash_key(card_name.lower()))
        return self.set(key, card_data, ttl)
    
    def get_scryfall_card(self, card_name: str) -> Optional[Dict]:
        """Get cached Scryfall card data."""
        key = self._make_key("scryfall", self._hash_key(card_name.lower()))
        return self.get(key)
    
    def cache_fuzzy_match(self, query: str, matches: list, ttl: int = 7200) -> bool:
        """Cache fuzzy matching results (2 hour TTL)."""
        key = self._make_key("fuzzy", self._hash_key(query.lower()))
        return self.set(key, matches, ttl)
    
    def get_fuzzy_match(self, query: str) -> Optional[list]:
        """Get cached fuzzy match results."""
        key = self._make_key("fuzzy", self._hash_key(query.lower()))
        return self.get(key)
    
    def set_job_status(self, job_id: str, status: Dict, ttl: int = 3600) -> bool:
        """Set job status in cache."""
        key = self._make_key("job", job_id)
        return self.set(key, status, ttl)
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status from cache."""
        key = self._make_key("job", job_id)
        return self.get(key)
    
    def increment_counter(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        try:
            if self.enabled and self.redis_client:
                return self.redis_client.incrby(key, amount)
            else:
                current = self.memory_cache.get(key, 0)
                self.memory_cache[key] = current + amount
                return self.memory_cache[key]
        except Exception as e:
            logger.error(f"Counter increment error for {key}: {e}")
            return 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        stats = {
            "enabled": self.enabled,
            "backend": "redis" if self.enabled else "memory"
        }
        
        try:
            if self.enabled and self.redis_client:
                info = self.redis_client.info()
                stats.update({
                    "used_memory": info.get("used_memory_human", "N/A"),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_commands": info.get("total_commands_processed", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                })
                
                # Calculate hit rate
                hits = stats["keyspace_hits"]
                misses = stats["keyspace_misses"]
                if hits + misses > 0:
                    stats["hit_rate"] = f"{(hits / (hits + misses)) * 100:.2f}%"
            else:
                stats.update({
                    "cached_items": len(self.memory_cache),
                    "memory_cache_keys": list(self.memory_cache.keys())[:10]  # First 10 keys
                })
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        return stats

# Global cache manager instance
cache_manager = CacheManager()

# Decorator for caching function results
def cached(prefix: str, ttl: int = 1800):
    """
    Decorator to cache function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = cache_manager._make_key(
                prefix,
                func.__name__,
                cache_manager._hash_key(str(args) + str(kwargs))
            )
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            
            return result
        return wrapper
    return decorator