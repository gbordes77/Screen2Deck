"""
Minimal Prometheus metrics for Screen2Deck.
Core metrics only, no bloat.
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, make_asgi_app
import time
from contextlib import contextmanager
from typing import Optional

# Create a custom registry (avoid default registry conflicts)
registry = CollectorRegistry()

# Core metrics
OCR_REQUESTS = Counter(
    "s2d_ocr_requests_total",
    "Total OCR requests",
    registry=registry
)

OCR_ERRORS = Counter(
    "s2d_ocr_errors_total",
    "Total OCR errors",
    ["error_type"],
    registry=registry
)

OCR_DURATION = Histogram(
    "s2d_ocr_request_duration_seconds",
    "OCR request duration in seconds",
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0),
    registry=registry
)

CACHE_HITS = Counter(
    "s2d_cache_hits_total",
    "Cache hits by layer",
    ["layer"],  # ocr, fuzzy, scryfall
    registry=registry
)

CACHE_MISSES = Counter(
    "s2d_cache_misses_total",
    "Cache misses by layer",
    ["layer"],
    registry=registry
)

JOBS_INFLIGHT = Gauge(
    "s2d_jobs_inflight",
    "Number of jobs currently processing",
    registry=registry
)

EXPORT_REQUESTS = Counter(
    "s2d_export_requests_total",
    "Export requests by format",
    ["format"],  # mtga, moxfield, archidekt, tappedout
    registry=registry
)

# Helper functions
def record_cache_access(layer: str, hit: bool):
    """Record cache hit or miss."""
    if hit:
        CACHE_HITS.labels(layer=layer).inc()
    else:
        CACHE_MISSES.labels(layer=layer).inc()

def record_export(format_type: str):
    """Record export request."""
    EXPORT_REQUESTS.labels(format=format_type).inc()

def record_error(error_type: str = "unknown"):
    """Record OCR error."""
    OCR_ERRORS.labels(error_type=error_type).inc()

@contextmanager
def track_ocr_request():
    """Context manager to track OCR request metrics."""
    OCR_REQUESTS.inc()
    JOBS_INFLIGHT.inc()
    start_time = time.time()
    
    try:
        yield
    except Exception as e:
        # Record error
        error_type = type(e).__name__
        record_error(error_type)
        raise
    finally:
        # Record duration and decrement inflight
        duration = time.time() - start_time
        OCR_DURATION.observe(duration)
        JOBS_INFLIGHT.dec()

@contextmanager
def track_duration(histogram: Histogram):
    """Generic duration tracking context manager."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        histogram.observe(duration)

def create_metrics_app():
    """Create ASGI app for metrics endpoint."""
    return make_asgi_app(registry=registry)

def get_metrics_summary() -> dict:
    """Get current metrics as dict (for logging/debugging)."""
    # Collect current values
    from prometheus_client import generate_latest
    from prometheus_client.parser import text_string_to_metric_families
    
    metrics_text = generate_latest(registry).decode('utf-8')
    
    summary = {}
    for family in text_string_to_metric_families(metrics_text):
        for sample in family.samples:
            if sample.name.startswith('s2d_'):
                # Skip histogram buckets and info
                if not any(suffix in sample.name for suffix in ['_bucket', '_info', '_created']):
                    summary[sample.name] = sample.value
    
    return summary

# Example instrumentation:
"""
# In your OCR endpoint:
from app.core.metrics_minimal import track_ocr_request, record_cache_access

@router.post("/api/ocr/upload")
async def upload_image(file: UploadFile):
    with track_ocr_request():
        # Check cache
        cached = check_cache(file)
        record_cache_access("ocr", cached is not None)
        
        if cached:
            return cached
        
        # Process OCR
        result = process_ocr(file)
        return result

# Mount metrics endpoint in main.py:
from app.core.metrics_minimal import create_metrics_app

metrics_app = create_metrics_app()
app.mount("/metrics", metrics_app)
"""