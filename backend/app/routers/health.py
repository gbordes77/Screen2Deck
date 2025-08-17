"""
Health check endpoints for Screen2Deck API.
"""

from fastapi import APIRouter, status, Request, HTTPException, Depends
from typing import Dict, Any, Optional
import psutil
import time

from ..core.config import settings
from ..core.job_storage import job_storage
from ..telemetry import logger

router = APIRouter()


def check_health_access(request: Request) -> bool:
    """Check if client is allowed to access detailed health endpoint."""
    # In development, always allow
    if settings.APP_ENV == "dev" and settings.HEALTH_EXPOSE_INTERNAL:
        return True
    
    # Check IP allowlist
    client_ip = request.client.host
    allowed_ips = [ip.strip() for ip in settings.HEALTH_ALLOWED_IPS.split(",")]
    
    if client_ip not in allowed_ips:
        logger.warning(f"Unauthorized health access attempt from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return True

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Basic health check endpoint"
)
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    Returns 200 if service is healthy.
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0"
    }


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Kubernetes liveness probe endpoint"
)
async def liveness() -> Dict[str, str]:
    """
    Liveness probe for Kubernetes.
    Returns 200 if service is alive.
    """
    return {"status": "alive"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Kubernetes readiness probe endpoint"
)
async def readiness() -> Dict[str, Any]:
    """
    Readiness probe for Kubernetes.
    Checks if all dependencies are ready.
    """
    checks = {
        "redis": False,
        "scryfall": False,
        "system": False
    }
    
    # Check Redis connection
    try:
        await job_storage.connect()
        stats = await job_storage.get_stats()
        checks["redis"] = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Check Scryfall cache
    try:
        from ..matching.scryfall_cache import scryfall_cache
        cache_stats = scryfall_cache.get_stats()
        checks["scryfall"] = cache_stats["total_cards"] > 0
    except Exception as e:
        logger.error(f"Scryfall health check failed: {e}")
    
    # Check system resources
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        checks["system"] = cpu_percent < 90 and memory.percent < 90
    except Exception as e:
        logger.error(f"System health check failed: {e}")
    
    # Determine overall readiness
    all_ready = all(checks.values())
    
    response = {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks
    }
    
    if not all_ready:
        return response  # Still return 200 for K8s compatibility
    
    return response


@router.get(
    "/health/detailed",
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Detailed health information including metrics",
    dependencies=[Depends(check_health_access)]
)
async def detailed_health(request: Request) -> Dict[str, Any]:
    """
    Detailed health check with system metrics.
    Protected endpoint - requires IP allowlist or dev mode.
    """
    
    # Sanitize response based on HEALTH_EXPOSE_INTERNAL flag
    if not settings.HEALTH_EXPOSE_INTERNAL:
        # Return minimal info in production
        return {
            "status": "healthy",
            "version": "2.0.0",
            "environment": settings.APP_ENV,
            "message": "Detailed metrics restricted"
        }
    # System metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    # Job storage stats
    job_stats = {}
    try:
        job_stats = await job_storage.get_stats()
    except Exception as e:
        logger.error(f"Failed to get job stats: {e}")
    
    # Scryfall cache stats
    cache_stats = {}
    try:
        from ..matching.scryfall_cache import scryfall_cache
        cache_stats = scryfall_cache.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": settings.APP_ENV,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": memory.used / (1024**3),
            "memory_total_gb": memory.total / (1024**3),
            "disk_percent": disk.percent,
            "disk_used_gb": disk.used / (1024**3),
            "disk_total_gb": disk.total / (1024**3)
        },
        "jobs": job_stats,
        "cache": cache_stats,
        "features": {
            "vision_fallback": settings.ENABLE_VISION_FALLBACK,
            "websocket": settings.FEATURE_WEBSOCKET,
            "async_processing": settings.FEATURE_ASYNC_PROCESSING,
            "tracing": settings.ENABLE_TRACING
        },
        "gdpr": {
            "enabled": settings.GDPR_ENABLED,
            "data_retention": {
                "images_hours": settings.DATA_RETENTION_IMAGES_HOURS,
                "jobs_hours": settings.DATA_RETENTION_JOBS_HOURS,
                "hashes_days": settings.DATA_RETENTION_HASHES_DAYS,
                "logs_days": settings.DATA_RETENTION_LOGS_DAYS,
                "metrics_days": settings.DATA_RETENTION_METRICS_DAYS
            },
            "ttl_seconds": {
                "images": settings.DATA_RETENTION_IMAGES_HOURS * 3600,
                "jobs": settings.DATA_RETENTION_JOBS_HOURS * 3600,
                "hashes": settings.DATA_RETENTION_HASHES_DAYS * 86400,
                "logs": settings.DATA_RETENTION_LOGS_DAYS * 86400,
                "metrics": settings.DATA_RETENTION_METRICS_DAYS * 86400
            },
            "privacy": {
                "analytics": settings.ENABLE_ANALYTICS,
                "tracking": settings.ENABLE_TRACKING,
                "consent_required": settings.REQUIRE_CONSENT
            }
        },
        "ocr": {
            "engine": "EasyOCR",
            "confidence_threshold": settings.OCR_MIN_CONF,
            "min_lines": settings.OCR_MIN_LINES,
            "always_verify_scryfall": settings.ALWAYS_VERIFY_SCRYFALL,
            "anti_tesseract": "ENFORCED - Tesseract is explicitly blocked"
        },
        "vision_fallback": {
            "enabled": settings.ENABLE_VISION_FALLBACK,
            "confidence_threshold": getattr(settings, "VISION_FALLBACK_CONFIDENCE_THRESHOLD", 0.62),
            "min_lines": getattr(settings, "VISION_FALLBACK_MIN_LINES", 10)
        } if settings.ENABLE_VISION_FALLBACK else None
    }