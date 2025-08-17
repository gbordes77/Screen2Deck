"""
Authentication middleware for FastAPI.
Handles JWT and API key authentication with proper security.
"""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

from ..auth import verify_token, verify_api_key, TokenData
from ..telemetry import logger

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    # Export endpoints for testing
    "/api/export/mtga",
    "/api/export/moxfield",
    "/api/export/archidekt",
    "/api/export/tappedout",
}

# Rate-limited public endpoints
RATE_LIMITED_PUBLIC = {
    "/api/ocr/upload": {"requests_per_minute": 10, "burst": 3},
    "/api/ocr/status": {"requests_per_minute": 60, "burst": 10},
}

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware that enforces JWT/API key authentication.
    """
    
    def __init__(self, app, skip_auth_paths: Optional[set] = None):
        super().__init__(app)
        self.skip_auth_paths = skip_auth_paths or PUBLIC_ENDPOINTS
        self.rate_limits = {}  # Track rate limits per IP
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication."""
        path = request.url.path
        
        # Skip auth for public endpoints
        if path in self.skip_auth_paths:
            return await call_next(request)
        
        # Check if endpoint is rate-limited public
        for endpoint, limits in RATE_LIMITED_PUBLIC.items():
            if path.startswith(endpoint):
                if not await self._check_rate_limit(request, limits):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded"
                    )
                # Allow without auth but with rate limiting
                return await call_next(request)
        
        # Extract authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        scheme, credentials = get_authorization_scheme_param(authorization)
        
        # Validate credentials
        token_data = None
        
        if scheme.lower() == "bearer":
            # Try JWT token
            try:
                from jose import jwt, JWTError
                from ..core.config import settings
                
                payload = jwt.decode(
                    credentials, 
                    settings.JWT_SECRET_KEY, 
                    algorithms=[settings.JWT_ALGORITHM]
                )
                token_data = TokenData(
                    job_id=payload.get("job_id"),
                    permissions=payload.get("permissions", [])
                )
            except JWTError as e:
                # Try API key as fallback
                api_key_data = verify_api_key(credentials)
                if api_key_data:
                    token_data = TokenData(permissions=api_key_data.permissions)
                else:
                    logger.warning(f"Invalid token from {request.client.host}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication credentials",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Store token data in request state for use in endpoints
        request.state.token_data = token_data
        
        # Log authenticated request
        logger.info(f"Authenticated request to {path} with permissions: {token_data.permissions}")
        
        # Process request
        response = await call_next(request)
        return response
    
    async def _check_rate_limit(self, request: Request, limits: dict) -> bool:
        """Check if request is within rate limits."""
        client_ip = self._get_client_ip(request)
        now = time.time()
        
        # Initialize rate limit tracking for this IP
        if client_ip not in self.rate_limits:
            self.rate_limits[client_ip] = {
                "requests": [],
                "burst_count": 0,
                "last_reset": now
            }
        
        client_limits = self.rate_limits[client_ip]
        
        # Clean old requests (older than 1 minute)
        cutoff = now - 60
        client_limits["requests"] = [
            req_time for req_time in client_limits["requests"] 
            if req_time > cutoff
        ]
        
        # Check requests per minute
        if len(client_limits["requests"]) >= limits["requests_per_minute"]:
            return False
        
        # Check burst limit (requests in last 5 seconds)
        recent_cutoff = now - 5
        recent_requests = sum(
            1 for req_time in client_limits["requests"] 
            if req_time > recent_cutoff
        )
        if recent_requests >= limits["burst"]:
            return False
        
        # Add current request
        client_limits["requests"].append(now)
        
        # Clean up old IPs to prevent memory leak
        if len(self.rate_limits) > 1000:
            # Remove IPs that haven't made requests in 5 minutes
            old_cutoff = now - 300
            self.rate_limits = {
                ip: data for ip, data in self.rate_limits.items()
                if data["requests"] and data["requests"][-1] > old_cutoff
            }
        
        return True
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP considering proxy headers."""
        # Check proxy headers first
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()
        elif "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"]
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.scryfall.com"
        )
        
        return response