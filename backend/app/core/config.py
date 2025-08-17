"""
Enhanced configuration with Pydantic Settings validation.
Provides type-safe environment variable management.
"""

from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pydantic.networks import PostgresDsn, RedisDsn
from functools import lru_cache
import json
import secrets

class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Application
    APP_ENV: str = Field("development", env="APP_ENV")
    PORT: int = Field(8080, env="PORT", ge=1, le=65535)
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    DEBUG: bool = Field(False, env="DEBUG")
    
    # Security
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY", min_length=32)
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    API_KEY_PREFIX: str = Field("s2d_", env="API_KEY_PREFIX")
    
    # Database
    DATABASE_URL: Optional[PostgresDsn] = Field(None, env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    USE_REDIS: bool = Field(True, env="USE_REDIS")
    REDIS_URL: Optional[RedisDsn] = Field("redis://localhost:6379/0", env="REDIS_URL")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    REDIS_POOL_SIZE: int = Field(10, env="REDIS_POOL_SIZE")
    
    # OCR
    ENABLE_VISION_FALLBACK: bool = Field(False, env="ENABLE_VISION_FALLBACK")
    ENABLE_SUPERRES: bool = Field(False, env="ENABLE_SUPERRES")
    OCR_MIN_CONF: float = Field(0.62, env="OCR_MIN_CONF", ge=0.0, le=1.0)
    OCR_MIN_LINES: int = Field(10, env="OCR_MIN_LINES", ge=1)
    MAX_IMAGE_MB: int = Field(8, env="MAX_IMAGE_MB", ge=1, le=50)
    FUZZY_MATCH_TOPK: int = Field(5, env="FUZZY_MATCH_TOPK", ge=1, le=20)
    
    # Scryfall
    ALWAYS_VERIFY_SCRYFALL: bool = Field(True, env="ALWAYS_VERIFY_SCRYFALL")
    ENABLE_SCRYFALL_ONLINE_FALLBACK: bool = Field(True, env="ENABLE_SCRYFALL_ONLINE_FALLBACK")
    SCRYFALL_API_TIMEOUT: int = Field(5, env="SCRYFALL_API_TIMEOUT")
    SCRYFALL_API_RATE_LIMIT_MS: int = Field(120, env="SCRYFALL_API_RATE_LIMIT_MS")
    SCRYFALL_DB: str = Field("./app/data/scryfall_cache.sqlite", env="SCRYFALL_DB")
    SCRYFALL_BULK_PATH: str = Field("./app/data/scryfall-default-cards.json", env="SCRYFALL_BULK_PATH")
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    
    # Monitoring
    ENABLE_METRICS: bool = Field(True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(9090, env="METRICS_PORT")
    ENABLE_TRACING: bool = Field(False, env="ENABLE_TRACING")
    JAEGER_AGENT_HOST: str = Field("localhost", env="JAEGER_AGENT_HOST")
    JAEGER_AGENT_PORT: int = Field(6831, env="JAEGER_AGENT_PORT")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        ["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(True, env="CORS_ALLOW_CREDENTIALS")
    CORS_ALLOW_METHODS: List[str] = Field(["GET", "POST"], env="CORS_ALLOW_METHODS")
    CORS_ALLOW_HEADERS: List[str] = Field(["*"], env="CORS_ALLOW_HEADERS")
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_PER_MINUTE: int = Field(30, env="RATE_LIMIT_PER_MINUTE")
    RATE_LIMIT_PER_HOUR: int = Field(1000, env="RATE_LIMIT_PER_HOUR")
    
    # Feature Flags
    FEATURE_WEBSOCKET: bool = Field(True, env="FEATURE_WEBSOCKET")
    FEATURE_GRAPHQL: bool = Field(False, env="FEATURE_GRAPHQL")
    FEATURE_ASYNC_PROCESSING: bool = Field(True, env="FEATURE_ASYNC_PROCESSING")
    
    @field_validator("JWT_SECRET_KEY", mode='before')
    def validate_jwt_secret(cls, v):
        """Ensure JWT secret is secure."""
        if v == "your-secret-key-min-32-chars-change-in-production":
            # Generate a secure random key if default is used
            return secrets.token_urlsafe(32)
        return v
    
    @field_validator("CORS_ORIGINS", mode='before')
    def parse_cors_origins(cls, v):
        """Parse CORS origins from JSON string."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return [v]
        return v
    
    @field_validator("DATABASE_URL", mode='before')
    def build_database_url(cls, v, values):
        """Build database URL if not provided."""
        if not v and values.get("APP_ENV") != "development":
            raise ValueError("DATABASE_URL is required in production")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.APP_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.APP_ENV == "production"
    
    def get_database_url(self, async_mode: bool = True) -> str:
        """Get database URL with async driver if needed."""
        if not self.DATABASE_URL:
            return ""
        url = str(self.DATABASE_URL)
        if async_mode and url.startswith("postgresql://"):
            # Convert to async driver
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Export for backwards compatibility
settings = get_settings()