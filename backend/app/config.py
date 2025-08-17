import os
from functools import lru_cache

class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    PORT: int = int(os.getenv("PORT", 8080))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # OCR & fallbacks
    ENABLE_VISION_FALLBACK: bool = os.getenv("ENABLE_VISION_FALLBACK","false").lower()=="true"
    ENABLE_SUPERRES: bool = os.getenv("ENABLE_SUPERRES","false").lower()=="true"
    OCR_MIN_CONF: float = float(os.getenv("OCR_MIN_CONF", 0.62))
    OCR_MIN_LINES: int = int(os.getenv("OCR_MIN_LINES", 10))

    # Scryfall check (toujours)
    ALWAYS_VERIFY_SCRYFALL: bool = os.getenv("ALWAYS_VERIFY_SCRYFALL","true").lower()=="true"
    ENABLE_SCRYFALL_ONLINE_FALLBACK: bool = os.getenv("ENABLE_SCRYFALL_ONLINE_FALLBACK","true").lower()=="true"
    SCRYFALL_API_TIMEOUT: int = int(os.getenv("SCRYFALL_API_TIMEOUT", 5))
    SCRYFALL_API_RATE_LIMIT_MS: int = int(os.getenv("SCRYFALL_API_RATE_LIMIT_MS", 120))

    # Cache files
    SCRYFALL_DB: str = os.getenv("SCRYFALL_DB","./app/data/scryfall_cache.sqlite")
    SCRYFALL_BULK_PATH: str = os.getenv("SCRYFALL_BULK_PATH","./app/data/scryfall-default-cards.json")
    SCRYFALL_TIMEOUT: int = int(os.getenv("SCRYFALL_TIMEOUT", 5))

    # General
    MAX_IMAGE_MB: int = int(os.getenv("MAX_IMAGE_MB", 8))
    FUZZY_MATCH_TOPK: int = int(os.getenv("FUZZY_MATCH_TOPK", 5))

    # Redis (optionnel)
    USE_REDIS: bool = os.getenv("USE_REDIS","false").lower()=="true"
    REDIS_URL: str = os.getenv("REDIS_URL","redis://localhost:6379/0")
    
    # GDPR & Data Retention
    GDPR_ENABLED: bool = os.getenv("GDPR_ENABLED", "true").lower() == "true"
    DATA_RETENTION_IMAGES_HOURS: int = int(os.getenv("DATA_RETENTION_IMAGES_HOURS", 24))
    DATA_RETENTION_JOBS_HOURS: int = int(os.getenv("DATA_RETENTION_JOBS_HOURS", 1))
    DATA_RETENTION_HASHES_DAYS: int = int(os.getenv("DATA_RETENTION_HASHES_DAYS", 7))
    DATA_RETENTION_LOGS_DAYS: int = int(os.getenv("DATA_RETENTION_LOGS_DAYS", 7))
    DATA_RETENTION_METRICS_DAYS: int = int(os.getenv("DATA_RETENTION_METRICS_DAYS", 30))
    
    # Privacy Settings
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "false").lower() == "true"
    ENABLE_TRACKING: bool = os.getenv("ENABLE_TRACKING", "false").lower() == "true"
    REQUIRE_CONSENT: bool = os.getenv("REQUIRE_CONSENT", "true").lower() == "true"
    
    # Health endpoint security
    HEALTH_EXPOSE_INTERNAL: bool = os.getenv("HEALTH_EXPOSE_INTERNAL", "false").lower() == "true"
    HEALTH_ALLOWED_IPS: str = os.getenv("HEALTH_ALLOWED_IPS", "127.0.0.1,::1")  # Comma-separated
    HEALTH_REQUIRE_AUTH: bool = os.getenv("HEALTH_REQUIRE_AUTH", "true").lower() == "true"

@lru_cache
def get_settings():
    return Settings()