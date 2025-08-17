"""
Prometheus metrics for Screen2Deck
Detailed metrics for OCR pipeline stages and business KPIs
"""

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest
)
from functools import wraps
import time
from typing import Callable, Any

# Create a custom registry to avoid conflicts
REGISTRY = CollectorRegistry()

# ============================================================================
# OCR Pipeline Metrics
# ============================================================================

# Request metrics
ocr_requests_total = Counter(
    'screen2deck_ocr_requests_total',
    'Total number of OCR requests',
    ['status', 'cached'],
    registry=REGISTRY
)

ocr_request_duration_seconds = Histogram(
    'screen2deck_ocr_request_duration_seconds',
    'OCR request duration in seconds',
    ['stage'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY
)

# Stage-specific metrics
ocr_preprocessing_duration_seconds = Histogram(
    'screen2deck_ocr_preprocessing_duration_seconds',
    'Image preprocessing duration in seconds',
    ['variant'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=REGISTRY
)

ocr_easyocr_duration_seconds = Histogram(
    'screen2deck_ocr_easyocr_duration_seconds',
    'EasyOCR processing duration in seconds',
    ['variant', 'early_termination'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0),
    registry=REGISTRY
)

ocr_matching_duration_seconds = Histogram(
    'screen2deck_ocr_matching_duration_seconds',
    'Card matching duration in seconds',
    ['method'],  # fuzzy, scryfall_cache, scryfall_api
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=REGISTRY
)

# Confidence metrics
ocr_confidence_mean = Gauge(
    'screen2deck_ocr_confidence_mean',
    'Mean OCR confidence score',
    registry=REGISTRY
)

ocr_confidence_distribution = Histogram(
    'screen2deck_ocr_confidence_distribution',
    'Distribution of OCR confidence scores',
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99),
    registry=REGISTRY
)

# ============================================================================
# Cache Metrics
# ============================================================================

cache_hit_total = Counter(
    'screen2deck_cache_hit_total',
    'Total cache hits',
    ['cache_type'],  # image_hash, scryfall, redis
    registry=REGISTRY
)

cache_miss_total = Counter(
    'screen2deck_cache_miss_total',
    'Total cache misses',
    ['cache_type'],
    registry=REGISTRY
)

cache_hit_ratio = Gauge(
    'screen2deck_cache_hit_ratio',
    'Cache hit ratio',
    ['cache_type'],
    registry=REGISTRY
)

scryfall_cache_size = Gauge(
    'screen2deck_scryfall_cache_size',
    'Number of cards in Scryfall cache',
    registry=REGISTRY
)

# ============================================================================
# Export Metrics
# ============================================================================

export_requests_total = Counter(
    'screen2deck_export_requests_total',
    'Total export requests',
    ['format', 'status'],
    registry=REGISTRY
)

export_golden_fail_total = Counter(
    'screen2deck_export_golden_fail_total',
    'Export golden test failures',
    ['format'],
    registry=REGISTRY
)

export_duration_seconds = Histogram(
    'screen2deck_export_duration_seconds',
    'Export generation duration',
    ['format'],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25),
    registry=REGISTRY
)

# ============================================================================
# Fallback Metrics
# ============================================================================

vision_fallback_total = Counter(
    'screen2deck_vision_fallback_total',
    'Total Vision API fallback uses',
    ['reason'],  # low_confidence, min_lines, error
    registry=REGISTRY
)

vision_fallback_duration_seconds = Histogram(
    'screen2deck_vision_fallback_duration_seconds',
    'Vision API fallback duration',
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
    registry=REGISTRY
)

# ============================================================================
# Business Metrics
# ============================================================================

cards_processed_total = Counter(
    'screen2deck_cards_processed_total',
    'Total cards processed',
    ['deck_section'],  # main, side
    registry=REGISTRY
)

deck_size_distribution = Histogram(
    'screen2deck_deck_size_distribution',
    'Distribution of deck sizes',
    ['deck_section'],
    buckets=(0, 15, 30, 45, 60, 75, 100, 150, 250),
    registry=REGISTRY
)

accuracy_score = Gauge(
    'screen2deck_accuracy_score',
    'Current accuracy score from validation',
    registry=REGISTRY
)

# ============================================================================
# System Metrics
# ============================================================================

active_jobs = Gauge(
    'screen2deck_active_jobs',
    'Number of active OCR jobs',
    registry=REGISTRY
)

job_queue_size = Gauge(
    'screen2deck_job_queue_size',
    'Size of job queue',
    registry=REGISTRY
)

gpu_available = Gauge(
    'screen2deck_gpu_available',
    'GPU availability (1=available, 0=not available)',
    registry=REGISTRY
)

memory_usage_bytes = Gauge(
    'screen2deck_memory_usage_bytes',
    'Memory usage in bytes',
    ['component'],  # easyocr, cache, redis
    registry=REGISTRY
)

# ============================================================================
# Error Metrics
# ============================================================================

errors_total = Counter(
    'screen2deck_errors_total',
    'Total errors',
    ['error_type', 'component'],
    registry=REGISTRY
)

# ============================================================================
# Authentication Metrics
# ============================================================================

auth_attempts_total = Counter(
    'screen2deck_auth_attempts_total',
    'Total authentication attempts',
    ['method', 'status'],  # jwt, api_key; success, failure
    registry=REGISTRY
)

rate_limit_violations_total = Counter(
    'screen2deck_rate_limit_violations_total',
    'Total rate limit violations',
    ['endpoint'],
    registry=REGISTRY
)

# ============================================================================
# Helper Functions
# ============================================================================

def track_time(metric: Histogram, **labels):
    """Decorator to track execution time"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                metric.labels(**labels).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start
                metric.labels(**labels).observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

def update_cache_ratio(cache_type: str):
    """Update cache hit ratio for a specific cache type"""
    hits = cache_hit_total._metrics.get(
        cache_hit_total._build_full_name((cache_type,)), 0
    )
    misses = cache_miss_total._metrics.get(
        cache_miss_total._build_full_name((cache_type,)), 0
    )
    
    total = hits + misses
    if total > 0:
        ratio = hits / total
        cache_hit_ratio.labels(cache_type=cache_type).set(ratio)

def track_ocr_request(cached: bool = False, status: str = "success"):
    """Track an OCR request"""
    ocr_requests_total.labels(
        status=status,
        cached="true" if cached else "false"
    ).inc()

def track_vision_fallback(reason: str, duration: float):
    """Track Vision API fallback usage"""
    vision_fallback_total.labels(reason=reason).inc()
    vision_fallback_duration_seconds.observe(duration)

def track_export(format: str, status: str, duration: float):
    """Track export request"""
    export_requests_total.labels(format=format, status=status).inc()
    export_duration_seconds.labels(format=format).observe(duration)

def track_auth_attempt(method: str, success: bool):
    """Track authentication attempt"""
    auth_attempts_total.labels(
        method=method,
        status="success" if success else "failure"
    ).inc()

def track_rate_limit_violation(endpoint: str):
    """Track rate limit violation"""
    rate_limit_violations_total.labels(endpoint=endpoint).inc()

def track_error(error_type: str, component: str):
    """Track error occurrence"""
    errors_total.labels(error_type=error_type, component=component).inc()

def update_job_metrics(active: int, queued: int):
    """Update job-related metrics"""
    active_jobs.set(active)
    job_queue_size.set(queued)

def update_gpu_status(available: bool):
    """Update GPU availability status"""
    gpu_available.set(1 if available else 0)

def track_cards_processed(mainboard: int, sideboard: int):
    """Track cards processed"""
    cards_processed_total.labels(deck_section="main").inc(mainboard)
    cards_processed_total.labels(deck_section="side").inc(sideboard)
    
    deck_size_distribution.labels(deck_section="main").observe(mainboard)
    deck_size_distribution.labels(deck_section="side").observe(sideboard)

def update_accuracy_score(score: float):
    """Update accuracy score from validation"""
    accuracy_score.set(score)

def get_metrics() -> bytes:
    """Generate metrics in Prometheus format"""
    return generate_latest(REGISTRY)

# ============================================================================
# Middleware for automatic tracking
# ============================================================================

class MetricsMiddleware:
    """FastAPI middleware for automatic metrics collection"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request, call_next):
        # Track request start time
        start_time = time.perf_counter()
        
        # Get endpoint path
        path = request.url.path
        
        # Process request
        response = await call_next(request)
        
        # Track request duration
        duration = time.perf_counter() - start_time
        
        # Track specific endpoints
        if path.startswith("/api/ocr"):
            ocr_request_duration_seconds.labels(stage="total").observe(duration)
        elif path.startswith("/api/export"):
            # Export tracking handled in export endpoints
            pass
        
        return response