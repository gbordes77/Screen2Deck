"""
Monitoring and metrics for Screen2Deck using Prometheus.
Tracks API performance, OCR processing, and system health.
"""

from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
import time
import psutil
from typing import Callable
from functools import wraps
from .telemetry import logger

# Create registry
registry = CollectorRegistry()

# Define metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    registry=registry
)

ocr_processing_duration_seconds = Histogram(
    'ocr_processing_duration_seconds',
    'OCR processing time',
    ['stage'],  # preprocessing, ocr, scryfall
    registry=registry
)

ocr_jobs_total = Counter(
    'ocr_jobs_total',
    'Total number of OCR jobs',
    ['status'],  # completed, failed, timeout
    registry=registry
)

ocr_confidence_score = Histogram(
    'ocr_confidence_score',
    'OCR confidence scores distribution',
    buckets=(0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
    registry=registry
)

cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status'],  # get/set/delete, hit/miss
    registry=registry
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate percentage',
    registry=registry
)

active_jobs = Gauge(
    'active_jobs',
    'Number of active OCR jobs',
    registry=registry
)

system_memory_usage = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes',
    registry=registry
)

system_cpu_usage = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage',
    registry=registry
)

redis_connections = Gauge(
    'redis_connections',
    'Number of Redis connections',
    registry=registry
)

scryfall_api_calls = Counter(
    'scryfall_api_calls_total',
    'Total Scryfall API calls',
    ['type', 'status'],  # online/offline, success/failure
    registry=registry
)

export_operations = Counter(
    'export_operations_total',
    'Total export operations',
    ['format'],  # mtga, moxfield, archidekt, tappedout
    registry=registry
)

rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Number of rate limit hits',
    ['endpoint'],
    registry=registry
)

# Middleware for request metrics
async def metrics_middleware(request: Request, call_next):
    """Middleware to track HTTP metrics."""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Record metrics
    duration = time.time() - start_time
    endpoint = request.url.path
    method = request.method
    status = response.status_code
    
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status=status
    ).inc()
    
    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)
    
    # Track rate limits
    if status == 429:
        rate_limit_hits.labels(endpoint=endpoint).inc()
    
    return response

# Decorator for tracking function execution time
def track_time(metric: Histogram, label_values: dict = None):
    """Decorator to track function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if label_values:
                    metric.labels(**label_values).observe(duration)
                else:
                    metric.observe(duration)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if label_values:
                    metric.labels(**label_values).observe(duration)
                else:
                    metric.observe(duration)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# System metrics collection
def collect_system_metrics():
    """Collect system-level metrics."""
    try:
        # Memory usage
        memory = psutil.virtual_memory()
        system_memory_usage.set(memory.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_cpu_usage.set(cpu_percent)
        
    except Exception as e:
        logger.error(f"Error collecting system metrics: {e}")

# OCR metrics helpers
def track_ocr_job_start():
    """Track OCR job start."""
    active_jobs.inc()

def track_ocr_job_complete(success: bool = True):
    """Track OCR job completion."""
    active_jobs.dec()
    status = "completed" if success else "failed"
    ocr_jobs_total.labels(status=status).inc()

def track_ocr_confidence(confidence: float):
    """Track OCR confidence score."""
    ocr_confidence_score.observe(confidence)

def track_ocr_stage(stage: str, duration: float):
    """Track OCR processing stage duration."""
    ocr_processing_duration_seconds.labels(stage=stage).observe(duration / 1000)  # Convert ms to seconds

# Cache metrics helpers
def track_cache_operation(operation: str, hit: bool):
    """Track cache operation."""
    status = "hit" if hit else "miss"
    cache_operations_total.labels(operation=operation, status=status).inc()
    
    # Update hit rate
    # This is simplified - in production, track over a time window
    if operation == "get":
        update_cache_hit_rate()

def update_cache_hit_rate():
    """Update cache hit rate gauge."""
    try:
        # Get hit and miss counts
        hits = cache_operations_total.labels(operation="get", status="hit")._value.get()
        misses = cache_operations_total.labels(operation="get", status="miss")._value.get()
        
        if hits + misses > 0:
            hit_rate = (hits / (hits + misses)) * 100
            cache_hit_rate.set(hit_rate)
    except:
        pass  # Ignore errors in metric calculation

# Export metrics helpers
def track_export(format: str):
    """Track export operation."""
    export_operations.labels(format=format).inc()

# Scryfall metrics helpers
def track_scryfall_call(online: bool, success: bool):
    """Track Scryfall API call."""
    type_label = "online" if online else "offline"
    status_label = "success" if success else "failure"
    scryfall_api_calls.labels(type=type_label, status=status_label).inc()

# Metrics endpoint
async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    # Collect current system metrics
    collect_system_metrics()
    
    # Generate metrics
    metrics = generate_latest(registry)
    
    return Response(
        content=metrics,
        media_type=CONTENT_TYPE_LATEST
    )

# Health check with metrics
async def health_with_metrics() -> dict:
    """Health check that includes basic metrics."""
    try:
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        
        health = {
            "status": "healthy",
            "metrics": {
                "memory_usage_percent": memory.percent,
                "cpu_usage_percent": cpu,
                "active_jobs": active_jobs._value.get() if hasattr(active_jobs, '_value') else 0
            }
        }
        
        # Add cache hit rate if available
        try:
            health["metrics"]["cache_hit_rate"] = cache_hit_rate._value.get()
        except:
            pass
        
        return health
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {"status": "unhealthy", "error": str(e)}

# Initialize metrics collection
import asyncio

async def start_metrics_collection():
    """Start periodic metrics collection."""
    while True:
        try:
            collect_system_metrics()
            await asyncio.sleep(30)  # Collect every 30 seconds
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
            await asyncio.sleep(60)  # Wait longer on error