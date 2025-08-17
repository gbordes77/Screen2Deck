"""
Authentication endpoints for Screen2Deck API.
"""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from ..core.config import settings
from ..auth import (
    create_access_token, create_api_key, hash_api_key,
    pwd_context, Token, ApiKey
)
from ..telemetry import logger

router = APIRouter()

# Request/Response models
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ApiKeyRequest(BaseModel):
    name: str
    permissions: Optional[list[str]] = ["ocr:read", "ocr:write", "export:read"]

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str


# Mock user storage (replace with database in production)
mock_users = {
    "demo": {
        "id": "user-123",
        "username": "demo",
        "email": "demo@screen2deck.com",
        "hashed_password": pwd_context.hash("demo123"),
        "created_at": "2024-01-01T00:00:00Z"
    }
}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account"
)
async def register(request: RegisterRequest):
    """
    Register a new user.
    """
    # Check if user exists
    if request.username in mock_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    
    # Create user (in production, save to database)
    user_id = f"user-{len(mock_users) + 1}"
    mock_users[request.username] = {
        "id": user_id,
        "username": request.username,
        "email": request.email,
        "hashed_password": pwd_context.hash(request.password),
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    logger.info(f"Registered new user: {request.username}")
    
    return UserResponse(
        id=user_id,
        username=request.username,
        email=request.email,
        created_at="2024-01-01T00:00:00Z"
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="Login with username and password"
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login and receive access token.
    """
    # Verify user (in production, check database)
    user = mock_users.get(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Verify password
    if not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "permissions": ["ocr:read", "ocr:write", "export:read"]
        },
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_access_token(
        data={
            "sub": user["username"],
            "user_id": user["id"],
            "type": "refresh"
        },
        expires_delta=refresh_token_expires
    )
    
    logger.info(f"User logged in: {form_data.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh token",
    description="Get new access token using refresh token"
)
async def refresh_token(request: RefreshRequest):
    """
    Refresh access token using refresh token.
    """
    try:
        from jose import jwt, JWTError
        
        # Decode refresh token
        payload = jwt.decode(
            request.refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": payload["sub"],
                "user_id": payload["user_id"],
                "permissions": ["ocr:read", "ocr:write", "export:read"]
            },
            expires_delta=access_token_expires
        )
        
        logger.info(f"Token refreshed for user: {payload['sub']}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=request.refresh_token  # Return same refresh token
        )
        
    except JWTError as e:
        logger.warning(f"Invalid refresh token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post(
    "/api-key",
    response_model=ApiKey,
    summary="Generate API key",
    description="Generate a new API key for programmatic access"
)
async def generate_api_key(request: ApiKeyRequest):
    """
    Generate a new API key.
    """
    # Create API key
    api_key = create_api_key(request.name)
    
    # In production, save to database with hashed key
    key_hash = hash_api_key(api_key.key)
    logger.info(f"Generated API key: {request.name} (hash: {key_hash[:8]}...)")
    
    # Return key (only shown once)
    return api_key


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Logout and invalidate token"
)
async def logout():
    """
    Logout user.
    
    In production, this would invalidate the token by adding it to a blacklist.
    """
    # In production, add token to blacklist
    logger.info("User logged out")
    return None