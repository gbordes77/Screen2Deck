"""
Stub telemetry module when OpenTelemetry is disabled.
"""

import logging
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any

# Setup basic logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Stub tracer
class StubTracer:
    def start_as_current_span(self, name: str):
        return nullcontext()

tracer = StubTracer()

# Stub meter
class StubMeter:
    def create_counter(self, name: str, **kwargs):
        return StubCounter()
    
    def create_histogram(self, name: str, **kwargs):
        return StubHistogram()

class StubCounter:
    def add(self, value: int, attributes: Dict = None):
        pass

class StubHistogram:
    def record(self, value: float, attributes: Dict = None):
        pass

meter = StubMeter()

# Stub span
class StubSpan:
    """Stub span object."""
    def set_attribute(self, key: str, value: Any):
        """No-op set_attribute."""
        pass
    
    def add_event(self, name: str, attributes: Dict = None):
        """No-op add_event."""
        pass
    
    def set_status(self, status: Any):
        """No-op set_status."""
        pass
    
    def record_exception(self, exc: Exception):
        """No-op record_exception."""
        pass

# Stub context manager
@contextmanager
def nullcontext():
    """Context manager that does nothing."""
    yield StubSpan()

# Initialize function (no-op)
def initialize_telemetry(service_name: str = "screen2deck", otlp_endpoint: str = None):
    """No-op when telemetry is disabled."""
    logger.info(f"Telemetry disabled for service: {service_name}")

# Trace ID generation
def generate_trace_id() -> str:
    """Generate a unique trace ID."""
    return str(uuid.uuid4())

# Span recording
@contextmanager
def record_span(name: str, attributes: Dict[str, Any] = None):
    """No-op span recording."""
    yield None

# Metrics recording
def record_metric(name: str, value: float, attributes: Dict[str, Any] = None):
    """No-op metric recording."""
    pass

# Error recording
def record_error(error: Exception, span_name: str = None):
    """Log error when telemetry is disabled."""
    logger.error(f"Error in {span_name or 'unknown'}: {error}")

# Exception recording
def record_exception(exc: Exception, attributes: Dict[str, Any] | None = None):
    """Record exception with attributes."""
    try:
        logger.exception("exception", extra={"attrs": attributes or {}})
    except Exception:
        pass

# Success recording  
def record_success(span_name: str = None):
    """No-op success recording."""
    pass

# New trace function
def new_trace(name: str = None):
    """No-op trace creation."""
    return generate_trace_id()

# Get current trace
def get_current_trace():
    """Return a dummy trace ID."""
    return generate_trace_id()

# Telemetry object (stub)
class TelemetryStub:
    """Stub telemetry object."""
    def __init__(self):
        self.tracer = tracer
        self.meter = meter
        self.logger = logger
    
    def initialize(self, service_name: str = "screen2deck"):
        """No-op initialization."""
        logger.info(f"Telemetry stub initialized for: {service_name}")
    
    @contextmanager
    def span(self, name: str):
        """Stub span context manager."""
        yield StubSpan()

telemetry = TelemetryStub()