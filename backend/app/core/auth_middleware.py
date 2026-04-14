"""
Authentication + rate-limit middleware for FastAPI.

Responsibilities:
- Always populate `request.state.token_data` (Optional[TokenData]) so
  every downstream dependency can decide whether it requires auth.
- Apply IP-based rate limiting on public OCR endpoints.
- NEVER silently bypass authentication: if a valid bearer token is
  present it is validated and the caller identity is captured; if not,
  the request flows with `token_data = None` and endpoint-level
  dependencies decide whether that is acceptable.

The IDOR fix: the previous version short-circuited on rate-limited
paths and on /api/export/* with `return await call_next(request)`,
which meant the middleware never parsed the Authorization header,
`request.state.token_data` was never set, and the ownership check in
`get_job_status` (`if job.get("user_id") and token_data:`) was dead
code — any caller holding a job UUID could read any user's deck.
"""

from typing import Callable, Optional

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

from ..auth import TokenData, verify_api_key
from ..telemetry import logger


def _parse_bearer(authorization: str) -> Optional[TokenData]:
    """Parse an Authorization header, returning TokenData or None.

    Returns None for both "no header" and "invalid token" — the caller
    decides whether to 401 at the endpoint layer via
    `Depends(get_current_token)` or to allow anonymous via
    `Depends(get_optional_token)`.
    """
    scheme, credentials = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not credentials:
        return None

    try:
        from jose import jwt, JWTError

        from ..core.config import settings

        payload = jwt.decode(
            credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            job_id=payload.get("job_id"),
            permissions=payload.get("permissions", []),
        )
    except Exception:
        api_key_data = verify_api_key(credentials)
        if api_key_data:
            return TokenData(permissions=api_key_data.permissions)
    return None

# Public endpoints that skip both auth parsing and rate limiting entirely.
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Anonymous-friendly endpoints that still get IP rate-limited.
RATE_LIMITED_PUBLIC = {
    "/api/ocr/upload": {"requests_per_minute": 10, "burst": 3},
    "/api/ocr/status": {"requests_per_minute": 60, "burst": 10},
    "/api/export/": {"requests_per_minute": 20, "burst": 5},
}


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional-auth middleware: populates state, rate-limits, never 401s.

    Endpoint-level `Depends(get_optional_token)` or `Depends(get_current_token)`
    is responsible for deciding whether the (possibly absent) token is
    acceptable for the operation.
    """

    def __init__(self, app, skip_auth_paths: Optional[set] = None):
        super().__init__(app)
        self.skip_auth_paths = skip_auth_paths or PUBLIC_ENDPOINTS
        self.rate_limits: dict = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        request.state.token_data = None

        if path in self.skip_auth_paths:
            return await call_next(request)

        for endpoint, limits in RATE_LIMITED_PUBLIC.items():
            if path.startswith(endpoint):
                if not await self._check_rate_limit(request, limits):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded",
                    )
                break

        authorization = request.headers.get("Authorization")
        if authorization:
            request.state.token_data = _parse_bearer(authorization)
            if request.state.token_data is not None:
                logger.info(
                    "Authenticated request to %s with permissions: %s",
                    path,
                    request.state.token_data.permissions,
                )
            else:
                logger.warning(
                    "Invalid bearer token on %s; proceeding anonymously",
                    path,
                )

        return await call_next(request)

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