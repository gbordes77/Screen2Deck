"""
Rate limiting implementation for public endpoints.
Uses in-memory storage with Redis fallback.
"""

import time
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
import redis
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from ..config import settings
from ..telemetry import logger

# Redis client for distributed rate limiting
redis_client = None
if settings.USE_REDIS:
    try:
        redis_client = redis.from_url(str(settings.REDIS_URL))
        redis_client.ping()
        logger.info("Rate limiter connected to Redis")
    except Exception as e:
        logger.warning(f"Rate limiter using in-memory storage: {e}")
        redis_client = None

# In-memory fallback storage
memory_storage: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))


class RateLimiter:
    """
    Simple rate limiter with sliding window.
    """
    
    def __init__(
        self, 
        requests_per_minute: int = 20,
        use_redis: bool = True,
        key_prefix: str = "rate_limit"
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per IP
            use_redis: Whether to use Redis (falls back to memory if unavailable)
            key_prefix: Redis key prefix for namespacing
        """
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self.use_redis = use_redis and redis_client is not None
        self.key_prefix = key_prefix
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.
        Handles X-Forwarded-For for proxied requests.
        """
        # Check for forwarded IP (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP if multiple are present
            return forwarded_for.split(",")[0].strip()
        
        # Check for X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _check_redis(self, ip: str) -> tuple[bool, int]:
        """
        Check rate limit using Redis.
        
        Returns:
            (allowed, remaining_requests)
        """
        if not self.use_redis:
            return self._check_memory(ip)
        
        try:
            key = f"{self.key_prefix}:{ip}"
            now = time.time()
            window_start = now - self.window_seconds
            
            # Use Redis sorted set with timestamps as scores
            pipeline = redis_client.pipeline()
            
            # Remove old entries outside the window
            pipeline.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            pipeline.zcard(key)
            
            # Add current request
            pipeline.zadd(key, {str(now): now})
            
            # Set expiry on the key
            pipeline.expire(key, self.window_seconds + 1)
            
            # Execute pipeline
            results = pipeline.execute()
            request_count = results[1]  # Count before adding current request
            
            # Check if limit exceeded
            if request_count >= self.requests_per_minute:
                return False, 0
            
            remaining = self.requests_per_minute - request_count - 1
            return True, max(0, remaining)
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fall back to memory
            return self._check_memory(ip)
    
    def _check_memory(self, ip: str) -> tuple[bool, int]:
        """
        Check rate limit using in-memory storage.
        
        Returns:
            (allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Get or create request history for this IP
        request_times = memory_storage[ip]
        
        # Remove old requests outside the window
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if limit exceeded
        if len(request_times) >= self.requests_per_minute:
            return False, 0
        
        # Add current request
        request_times.append(now)
        
        remaining = self.requests_per_minute - len(request_times)
        return True, max(0, remaining)
    
    async def check_request(self, request: Request) -> Optional[JSONResponse]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            request: FastAPI request object
            
        Returns:
            None if allowed, JSONResponse with 429 if rate limited
        """
        ip = self._get_client_ip(request)
        
        # Check rate limit
        if self.use_redis:
            allowed, remaining = self._check_redis(ip)
        else:
            allowed, remaining = self._check_memory(ip)
        
        # Add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(self.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(time.time()) + self.window_seconds)
        }
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                    "retry_after": self.window_seconds
                },
                headers=headers
            )
        
        # Add headers to request state for response
        request.state.rate_limit_headers = headers
        return None


# Create default rate limiter for export endpoints
export_rate_limiter = RateLimiter(
    requests_per_minute=20,  # 20 requests per minute per IP
    key_prefix="s2d_export"
)


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to add rate limit headers to responses.
    """
    response = await call_next(request)
    
    # Add rate limit headers if they were set
    if hasattr(request.state, "rate_limit_headers"):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value
    
    return response