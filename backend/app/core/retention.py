"""
GDPR-compliant data retention and cleanup tasks.

This module implements automatic data deletion to comply with GDPR requirements.
All retention periods are configurable via environment variables.
"""

from datetime import datetime, timedelta
from typing import Optional
import os
import logging
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
import redis

from app.config import settings
from app.core.telemetry import logger

# Initialize Celery
celery_app = Celery(
    'retention',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Redis client for cache cleanup
redis_client = redis.from_url(settings.REDIS_URL)

# Retention periods from settings
RETENTION_PERIODS = {
    'images': timedelta(hours=settings.DATA_RETENTION_IMAGES_HOURS),
    'jobs': timedelta(hours=settings.DATA_RETENTION_JOBS_HOURS),
    'hashes': timedelta(days=settings.DATA_RETENTION_HASHES_DAYS),
    'logs': timedelta(days=settings.DATA_RETENTION_LOGS_DAYS),
    'metrics': timedelta(days=settings.DATA_RETENTION_METRICS_DAYS),
}


@celery_app.task(name='cleanup_expired_images')
def cleanup_expired_images() -> dict:
    """
    Delete uploaded images older than retention period.
    
    Returns:
        dict: Cleanup statistics
    """
    stats = {'deleted_files': 0, 'deleted_records': 0, 'errors': 0}
    
    try:
        cutoff = datetime.utcnow() - RETENTION_PERIODS['images']
        
        # Clean up file system
        upload_dir = Path('/tmp/uploads')
        if upload_dir.exists():
            for image_file in upload_dir.glob('*.{jpg,jpeg,png,gif,bmp}'):
                try:
                    file_age = datetime.fromtimestamp(image_file.stat().st_mtime)
                    if file_age < cutoff:
                        image_file.unlink()
                        stats['deleted_files'] += 1
                        logger.info(f"Deleted expired image: {image_file.name}")
                except Exception as e:
                    logger.error(f"Error deleting image {image_file}: {e}")
                    stats['errors'] += 1
        
        # Clean up Redis keys
        for key in redis_client.scan_iter(match='image:*'):
            try:
                ttl = redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    redis_client.expire(key, int(RETENTION_PERIODS['images'].total_seconds()))
                stats['deleted_records'] += 1
            except Exception as e:
                logger.error(f"Error processing Redis key {key}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Image cleanup completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Image cleanup failed: {e}")
        stats['errors'] += 1
        return stats


@celery_app.task(name='cleanup_job_metadata')
def cleanup_job_metadata() -> dict:
    """
    Delete OCR job metadata older than retention period.
    
    Returns:
        dict: Cleanup statistics
    """
    stats = {'deleted_jobs': 0, 'deleted_results': 0, 'errors': 0}
    
    try:
        cutoff = datetime.utcnow() - RETENTION_PERIODS['jobs']
        cutoff_timestamp = int(cutoff.timestamp())
        
        # Clean up job keys
        for key in redis_client.scan_iter(match='job:*'):
            try:
                job_data = redis_client.hgetall(key)
                if job_data and b'completed_at' in job_data:
                    completed_at = int(job_data[b'completed_at'])
                    if completed_at < cutoff_timestamp:
                        redis_client.delete(key)
                        stats['deleted_jobs'] += 1
            except Exception as e:
                logger.error(f"Error processing job {key}: {e}")
                stats['errors'] += 1
        
        # Clean up result keys
        for key in redis_client.scan_iter(match='result:*'):
            try:
                # Check if associated job exists
                job_id = key.decode().split(':')[1]
                if not redis_client.exists(f'job:{job_id}'):
                    redis_client.delete(key)
                    stats['deleted_results'] += 1
            except Exception as e:
                logger.error(f"Error processing result {key}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Job cleanup completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Job cleanup failed: {e}")
        stats['errors'] += 1
        return stats


@celery_app.task(name='cleanup_image_hashes')
def cleanup_image_hashes() -> dict:
    """
    Delete image hashes older than retention period.
    
    Returns:
        dict: Cleanup statistics
    """
    stats = {'deleted_hashes': 0, 'errors': 0}
    
    try:
        # Redis keys with TTL auto-expire, but check for any without TTL
        for key in redis_client.scan_iter(match='hash:*'):
            try:
                ttl = redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    redis_client.expire(key, int(RETENTION_PERIODS['hashes'].total_seconds()))
                    stats['deleted_hashes'] += 1
            except Exception as e:
                logger.error(f"Error processing hash {key}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Hash cleanup completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Hash cleanup failed: {e}")
        stats['errors'] += 1
        return stats


@celery_app.task(name='rotate_logs')
def rotate_logs() -> dict:
    """
    Rotate and delete old log files.
    
    Returns:
        dict: Cleanup statistics
    """
    stats = {'deleted_logs': 0, 'compressed': 0, 'errors': 0}
    
    try:
        log_dir = Path('/app/logs')
        if not log_dir.exists():
            log_dir = Path('./logs')
        
        if log_dir.exists():
            cutoff = datetime.utcnow() - RETENTION_PERIODS['logs']
            
            for log_file in log_dir.glob('*.log*'):
                try:
                    file_age = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_age < cutoff:
                        log_file.unlink()
                        stats['deleted_logs'] += 1
                        logger.info(f"Deleted old log: {log_file.name}")
                except Exception as e:
                    logger.error(f"Error processing log {log_file}: {e}")
                    stats['errors'] += 1
        
        logger.info(f"Log rotation completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Log rotation failed: {e}")
        stats['errors'] += 1
        return stats


@celery_app.task(name='cleanup_metrics')
def cleanup_metrics() -> dict:
    """
    Clean up old metrics data.
    
    Returns:
        dict: Cleanup statistics
    """
    stats = {'deleted_metrics': 0, 'errors': 0}
    
    try:
        # Metrics are typically handled by Prometheus with its own retention
        # This is for any application-level metrics in Redis
        
        cutoff = datetime.utcnow() - RETENTION_PERIODS['metrics']
        cutoff_timestamp = int(cutoff.timestamp())
        
        for key in redis_client.scan_iter(match='metric:*'):
            try:
                # Assuming metrics have timestamp in sorted set
                redis_client.zremrangebyscore(key, 0, cutoff_timestamp)
                stats['deleted_metrics'] += 1
            except Exception as e:
                logger.error(f"Error processing metric {key}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Metrics cleanup completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Metrics cleanup failed: {e}")
        stats['errors'] += 1
        return stats


@celery_app.task(name='gdpr_user_data_export')
def export_user_data(user_id: str) -> dict:
    """
    Export all user data for GDPR Article 20 compliance.
    
    Args:
        user_id: User identifier
        
    Returns:
        dict: All user data in portable format
    """
    user_data = {
        'user_id': user_id,
        'export_date': datetime.utcnow().isoformat(),
        'jobs': [],
        'images': [],
        'metrics': []
    }
    
    try:
        # Collect job data
        for key in redis_client.scan_iter(match=f'job:*:user:{user_id}'):
            job_data = redis_client.hgetall(key)
            if job_data:
                user_data['jobs'].append({
                    k.decode(): v.decode() for k, v in job_data.items()
                })
        
        # Collect image hashes
        for key in redis_client.scan_iter(match=f'hash:*:user:{user_id}'):
            hash_data = redis_client.get(key)
            if hash_data:
                user_data['images'].append({
                    'hash': key.decode().split(':')[1],
                    'data': hash_data.decode()
                })
        
        logger.info(f"Exported data for user {user_id}")
        return user_data
        
    except Exception as e:
        logger.error(f"User data export failed for {user_id}: {e}")
        return user_data


@celery_app.task(name='gdpr_user_data_delete')
def delete_user_data(user_id: str) -> dict:
    """
    Delete all user data for GDPR Article 17 compliance.
    
    Args:
        user_id: User identifier
        
    Returns:
        dict: Deletion statistics
    """
    stats = {'deleted_jobs': 0, 'deleted_images': 0, 'deleted_keys': 0, 'errors': 0}
    
    try:
        # Delete all user-related keys
        patterns = [
            f'job:*:user:{user_id}',
            f'result:*:user:{user_id}',
            f'hash:*:user:{user_id}',
            f'session:{user_id}:*',
            f'rate_limit:{user_id}'
        ]
        
        for pattern in patterns:
            for key in redis_client.scan_iter(match=pattern):
                try:
                    redis_client.delete(key)
                    stats['deleted_keys'] += 1
                except Exception as e:
                    logger.error(f"Error deleting key {key}: {e}")
                    stats['errors'] += 1
        
        logger.info(f"Deleted all data for user {user_id}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"User data deletion failed for {user_id}: {e}")
        stats['errors'] += 1
        return stats


# Configure Celery beat schedule for automatic cleanup
celery_app.conf.beat_schedule = {
    'cleanup-images-hourly': {
        'task': 'cleanup_expired_images',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-jobs-frequently': {
        'task': 'cleanup_job_metadata',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-hashes-daily': {
        'task': 'cleanup_image_hashes',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'rotate-logs-daily': {
        'task': 'rotate_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-metrics-weekly': {
        'task': 'cleanup_metrics',
        'schedule': crontab(day_of_week=0, hour=4, minute=0),  # Weekly on Sunday at 4 AM
    },
}

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
)