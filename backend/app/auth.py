"""
Authentication and authorization module for Screen2Deck API.
Implements JWT-based authentication with API key support.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import secrets
from pydantic import BaseModel

from .core.config import settings

# Use settings for configuration
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
API_KEY_PREFIX = settings.API_KEY_PREFIX

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

class ApiKey(BaseModel):
    key: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    permissions: list[str] = ["ocr:read", "ocr:write", "export:read"]

class TokenData(BaseModel):
    job_id: Optional[str] = None
    permissions: list[str] = []
    exp: Optional[datetime] = None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_api_key(name: str) -> ApiKey:
    """Generate a new API key."""
    raw_key = secrets.token_urlsafe(32)
    key = f"{API_KEY_PREFIX}{raw_key}"
    
    return ApiKey(
        key=key,
        name=name,
        created_at=datetime.utcnow()
    )

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Verify and decode JWT token."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        job_id: str = payload.get("job_id")
        permissions: list = payload.get("permissions", [])
        
        return TokenData(job_id=job_id, permissions=permissions)
    except JWTError:
        raise credentials_exception

def verify_api_key(api_key: str) -> Optional[ApiKey]:
    """Verify API key and return associated permissions."""
    if not api_key.startswith(API_KEY_PREFIX):
        return None
    
    # In production, lookup from database
    # For now, validate format and return default permissions
    if len(api_key) > len(API_KEY_PREFIX) + 20:
        return ApiKey(
            key=api_key,
            name="default",
            created_at=datetime.utcnow(),
            permissions=["ocr:read", "ocr:write", "export:read"]
        )
    return None

def hash_api_key(api_key: str) -> str:
    """Hash API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()

def check_permission(token_data: TokenData, required_permission: str) -> bool:
    """Check if token has required permission."""
    return required_permission in token_data.permissions

# Dependency for protected routes
async def get_current_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """Dependency to get current authenticated token."""
    # Try JWT first
    try:
        return verify_token(credentials)
    except:
        # Try API key
        api_key_data = verify_api_key(credentials.credentials)
        if api_key_data:
            return TokenData(permissions=api_key_data.permissions)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_permission(permission: str):
    """Decorator to require specific permission."""
    async def permission_checker(token_data: TokenData = Depends(get_current_token)):
        if not check_permission(token_data, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return token_data
    return permission_checker