"""
Prometheus metrics endpoints for Screen2Deck API.
"""

from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST
)
import time
import psutil

router = APIRouter()

# Define Prometheus metrics
ocr_requests = Counter(
    "screen2deck_ocr_requests_total",
    "Total number of OCR requests",
    ["status"]
)

ocr_duration = Histogram(
    "screen2deck_ocr_duration_seconds",
    "OCR processing duration in seconds",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

active_jobs = Gauge(
    "screen2deck_active_jobs",
    "Number of active OCR jobs"
)

cache_hits = Counter(
    "screen2deck_cache_hits_total",
    "Total number of cache hits",
    ["cache_type"]
)

export_requests = Counter(
    "screen2deck_export_requests_total",
    "Total number of export requests",
    ["format"]
)

error_counter = Counter(
    "screen2deck_errors_total",
    "Total number of errors",
    ["error_type"]
)

# System metrics
cpu_usage = Gauge(
    "screen2deck_cpu_usage_percent",
    "CPU usage percentage"
)

memory_usage = Gauge(
    "screen2deck_memory_usage_bytes",
    "Memory usage in bytes"
)

# Application info
app_info = Info(
    "screen2deck_app",
    "Application information"
)

# Set application info
app_info.info({
    "version": "2.0.0",
    "environment": "production"
})


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Expose metrics in Prometheus format"
)
async def get_metrics() -> Response:
    """
    Expose Prometheus metrics.
    """
    # Update system metrics
    cpu_usage.set(psutil.cpu_percent(interval=0.1))
    memory_usage.set(psutil.virtual_memory().used)
    
    # Update job metrics
    try:
        from ..core.job_storage import job_storage
        stats = await job_storage.get_stats()
        active_jobs.set(stats.get("processing", 0))
    except:
        pass
    
    # Generate metrics
    metrics = generate_latest()
    
    return Response(
        content=metrics,
        media_type=CONTENT_TYPE_LATEST
    )


# Helper functions to update metrics
def record_ocr_request(status: str):
    """Record an OCR request."""
    ocr_requests.labels(status=status).inc()


def record_ocr_duration(duration: float):
    """Record OCR processing duration."""
    ocr_duration.observe(duration)


def record_cache_hit(cache_type: str):
    """Record a cache hit."""
    cache_hits.labels(cache_type=cache_type).inc()


def record_export_request(format: str):
    """Record an export request."""
    export_requests.labels(format=format).inc()


def record_error(error_type: str):
    """Record an error."""
    error_counter.labels(error_type=error_type).inc()