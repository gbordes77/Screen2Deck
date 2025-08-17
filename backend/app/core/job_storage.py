"""
Redis-based job storage for Screen2Deck.
Provides persistent job tracking with TTL and atomic operations.
"""

import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from ..core.config import settings
from ..telemetry import logger

class JobStorage:
    """
    Redis-backed job storage with automatic expiration and atomic operations.
    """
    
    def __init__(self, redis_url: str = None, ttl_hours: int = 24):
        """
        Initialize job storage.
        
        Args:
            redis_url: Redis connection URL
            ttl_hours: Time-to-live for jobs in hours
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.ttl = timedelta(hours=ttl_hours)
        self.redis_client = None
        self.key_prefix = "job:"
        self.index_prefix = "idx:"
        
    async def connect(self):
        """Establish Redis connection."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis for job storage")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    def _job_key(self, job_id: str) -> str:
        """Generate Redis key for job."""
        return f"{self.key_prefix}{job_id}"
    
    def _index_key(self, index_type: str, value: str) -> str:
        """Generate Redis key for index."""
        return f"{self.index_prefix}{index_type}:{value}"
    
    async def create_job(
        self, 
        job_id: str, 
        image_hash: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a new job with initial state.
        
        Args:
            job_id: Unique job identifier
            image_hash: SHA256 hash of uploaded image for idempotency
            user_id: Optional user identifier
            metadata: Additional job metadata
            
        Returns:
            True if job created, False if already exists
        """
        await self.connect()
        
        job_data = {
            "id": job_id,
            "state": "queued",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "image_hash": image_hash,
            "user_id": user_id,
            "metadata": metadata or {},
            "result": None,
            "error": None
        }
        
        key = self._job_key(job_id)
        
        # Use SET NX (set if not exists) for atomic creation
        created = await self.redis_client.set(
            key,
            json.dumps(job_data),
            nx=True,  # Only set if not exists
            ex=int(self.ttl.total_seconds())
        )
        
        if created:
            # Add to indexes
            if image_hash:
                await self.redis_client.sadd(
                    self._index_key("hash", image_hash),
                    job_id
                )
                await self.redis_client.expire(
                    self._index_key("hash", image_hash),
                    int(self.ttl.total_seconds())
                )
            
            if user_id:
                await self.redis_client.zadd(
                    self._index_key("user", user_id),
                    {job_id: datetime.utcnow().timestamp()}
                )
                await self.redis_client.expire(
                    self._index_key("user", user_id),
                    int(self.ttl.total_seconds())
                )
            
            logger.info(f"Created job {job_id}")
            return True
        
        logger.warning(f"Job {job_id} already exists")
        return False
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job data by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data dict or None if not found
        """
        await self.connect()
        
        key = self._job_key(job_id)
        data = await self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    async def update_job(
        self,
        job_id: str,
        state: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update job state atomically.
        
        Args:
            job_id: Job identifier
            state: New state (queued, processing, completed, failed)
            progress: Progress percentage (0-100)
            result: Job result data
            error: Error message if failed
            
        Returns:
            True if updated, False if job not found
        """
        await self.connect()
        
        # Get current job data
        job_data = await self.get_job(job_id)
        if not job_data:
            return False
        
        # Update fields
        if state is not None:
            job_data["state"] = state
        if progress is not None:
            job_data["progress"] = progress
        if result is not None:
            job_data["result"] = result
        if error is not None:
            job_data["error"] = error
        
        job_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Save updated data
        key = self._job_key(job_id)
        await self.redis_client.set(
            key,
            json.dumps(job_data),
            ex=int(self.ttl.total_seconds())
        )
        
        logger.info(f"Updated job {job_id}: state={state}, progress={progress}")
        return True
    
    async def find_by_image_hash(self, image_hash: str) -> Optional[str]:
        """
        Find existing job by image hash (for idempotency).
        
        Args:
            image_hash: SHA256 hash of image
            
        Returns:
            Job ID if found, None otherwise
        """
        await self.connect()
        
        # Get all job IDs for this hash
        job_ids = await self.redis_client.smembers(
            self._index_key("hash", image_hash)
        )
        
        # Find most recent completed job
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job and job.get("state") == "completed":
                logger.info(f"Found cached job {job_id} for hash {image_hash}")
                return job_id
        
        return None
    
    async def get_user_jobs(
        self, 
        user_id: str, 
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get recent jobs for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            
        Returns:
            List of job data dicts
        """
        await self.connect()
        
        # Get job IDs sorted by timestamp (newest first)
        job_ids = await self.redis_client.zrevrange(
            self._index_key("user", user_id),
            offset,
            offset + limit - 1
        )
        
        # Fetch job data
        jobs = []
        for job_id in job_ids:
            job = await self.get_job(job_id)
            if job:
                jobs.append(job)
        
        return jobs
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired jobs (called by background task).
        
        Returns:
            Number of jobs cleaned up
        """
        # Redis handles expiration automatically with TTL
        # This method is for compatibility and logging
        await self.connect()
        
        # Get all job keys
        pattern = f"{self.key_prefix}*"
        cursor = 0
        expired_count = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    # Set TTL to prevent infinite storage
                    await self.redis_client.expire(key, int(self.ttl.total_seconds()))
                    expired_count += 1
            
            if cursor == 0:
                break
        
        if expired_count > 0:
            logger.info(f"Set TTL for {expired_count} jobs without expiration")
        
        return expired_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Statistics dictionary
        """
        await self.connect()
        
        # Count jobs by state
        stats = {
            "total": 0,
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        
        pattern = f"{self.key_prefix}*"
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                data = await self.redis_client.get(key)
                if data:
                    job = json.loads(data)
                    state = job.get("state", "unknown")
                    stats["total"] += 1
                    if state in stats:
                        stats[state] += 1
            
            if cursor == 0:
                break
        
        # Get Redis info
        info = await self.redis_client.info("memory")
        stats["memory_used_mb"] = info.get("used_memory", 0) / 1024 / 1024
        
        return stats


# Global job storage instance
job_storage = JobStorage()


# Helper functions for backward compatibility
async def set_job(job_id: str, data: Dict[str, Any]) -> bool:
    """Legacy function for setting job data."""
    state = data.get("state", "queued")
    result = data.get("result")
    error = data.get("error")
    
    # Try to create or update
    job = await job_storage.get_job(job_id)
    if not job:
        await job_storage.create_job(job_id)
    
    return await job_storage.update_job(
        job_id,
        state=state,
        result=result,
        error=error
    )


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Legacy function for getting job data."""
    return await job_storage.get_job(job_id)