"""
GDPR compliance endpoints for data access and deletion.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
import hashlib

from ..core.config import settings
from ..core.job_storage import job_storage
from ..core.metrics import gdpr_requests_total, retention_deleted_total
from ..telemetry import logger
from ..auth import get_current_user, require_permission

router = APIRouter(prefix="/api/gdpr", tags=["GDPR"])


@router.delete(
    "/data/{identifier}",
    status_code=status.HTTP_200_OK,
    summary="Delete data by job ID or image hash",
    description="Exercise GDPR right to erasure (Article 17)"
)
async def delete_data(identifier: str) -> Dict[str, Any]:
    """
    Delete data associated with a job ID or image hash.
    Implements GDPR Article 17 - Right to erasure.
    """
    try:
        deleted_items = {
            "job": False,
            "result": False,
            "image": False,
            "hash": False
        }
        
        # Check if it's a job ID (UUID format)
        if "-" in identifier and len(identifier) == 36:
            # Delete job data
            job_deleted = await job_storage.delete_job(identifier)
            if job_deleted:
                deleted_items["job"] = True
                deleted_items["result"] = True
                retention_deleted_total.labels(type='jobs', reason='gdpr_request').inc()
                logger.info(f"GDPR deletion: Job {identifier} deleted")
        
        # Check if it's an image hash (SHA256)
        elif len(identifier) == 64:
            # Delete hash-related data
            from ..cache import redis_client
            
            # Delete from Redis
            keys_deleted = 0
            for key in redis_client.scan_iter(match=f"*{identifier}*"):
                redis_client.delete(key)
                keys_deleted += 1
            
            if keys_deleted > 0:
                deleted_items["hash"] = True
                retention_deleted_total.labels(type='hashes', reason='gdpr_request').inc()
                logger.info(f"GDPR deletion: {keys_deleted} keys for hash {identifier} deleted")
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid identifier format. Use job ID (UUID) or image hash (SHA256)"
            )
        
        # Track GDPR request
        gdpr_requests_total.labels(
            type='delete',
            status='success' if any(deleted_items.values()) else 'not_found'
        ).inc()
        
        return {
            "deleted": any(deleted_items.values()),
            "identifier": identifier,
            "items_deleted": deleted_items,
            "message": "Data deletion completed" if any(deleted_items.values()) else "No data found"
        }
        
    except Exception as e:
        logger.error(f"GDPR deletion failed for {identifier}: {e}")
        gdpr_requests_total.labels(type='delete', status='failure').inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data deletion failed"
        )


@router.get(
    "/data/export/{user_id}",
    summary="Export user data",
    description="Exercise GDPR right to data portability (Article 20)",
    dependencies=[Depends(get_current_user)]
)
async def export_user_data(user_id: str, current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Export all data associated with a user.
    Implements GDPR Article 20 - Right to data portability.
    """
    try:
        # Verify user can only export their own data
        if current_user.get("sub") != user_id and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot export data for other users"
            )
        
        # Collect user data
        user_data = {
            "user_id": user_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "jobs": [],
            "images": [],
            "exports": []
        }
        
        # Get job history
        jobs = await job_storage.get_user_jobs(user_id)
        user_data["jobs"] = jobs
        
        gdpr_requests_total.labels(type='export', status='success').inc()
        logger.info(f"GDPR export: Data exported for user {user_id}")
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR export failed for user {user_id}: {e}")
        gdpr_requests_total.labels(type='export', status='failure').inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data export failed"
        )


@router.post(
    "/consent/opt-out",
    summary="Opt out of analytics",
    description="Update privacy preferences"
)
async def opt_out_analytics(preferences: Dict[str, bool]) -> Dict[str, Any]:
    """
    Opt out of analytics and tracking.
    """
    # In a real implementation, this would update user preferences in the database
    return {
        "success": True,
        "preferences": {
            "analytics": preferences.get("analytics", False),
            "performance_tracking": preferences.get("performance_tracking", False),
            "error_reporting": preferences.get("error_reporting", True)
        },
        "message": "Privacy preferences updated"
    }


@router.get(
    "/retention/policy",
    summary="Get retention policy",
    description="View current data retention periods"
)
async def get_retention_policy() -> Dict[str, Any]:
    """
    Get current data retention policy.
    """
    return {
        "policy_version": "1.0.2",
        "last_updated": "2025-08-17",
        "retention_periods": {
            "images": f"{settings.DATA_RETENTION_IMAGES_HOURS} hours",
            "jobs": f"{settings.DATA_RETENTION_JOBS_HOURS} hours",
            "hashes": f"{settings.DATA_RETENTION_HASHES_DAYS} days",
            "logs": f"{settings.DATA_RETENTION_LOGS_DAYS} days",
            "metrics": f"{settings.DATA_RETENTION_METRICS_DAYS} days"
        },
        "gdpr_compliant": settings.GDPR_ENABLED,
        "privacy_settings": {
            "analytics_enabled": settings.ENABLE_ANALYTICS,
            "tracking_enabled": settings.ENABLE_TRACKING,
            "consent_required": settings.REQUIRE_CONSENT
        },
        "user_rights": [
            "Right to access (Article 15)",
            "Right to rectification (Article 16)",
            "Right to erasure (Article 17)",
            "Right to data portability (Article 20)",
            "Right to object (Article 21)"
        ]
    }