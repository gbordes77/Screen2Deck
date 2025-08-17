"""
Distributed tracing and observability with OpenTelemetry.
Provides comprehensive tracing across all services.
"""

import json
import time
import uuid
import logging
import sys
from typing import Optional, Dict, Any
from contextlib import contextmanager

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import Status, StatusCode
from opentelemetry.metrics import get_meter_provider, set_meter_provider

# Keep the original JSON formatter for backward compatibility
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        # Add trace context if available
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            payload["span_id"] = record.span_id
        return json.dumps(payload, ensure_ascii=False)

# Configure basic logger
basic_logger = logging.getLogger("app")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
basic_logger.addHandler(handler)
basic_logger.setLevel(logging.INFO)

def new_trace():
    """Generate new trace ID for backward compatibility."""
    return str(uuid.uuid4())

class TelemetryManager:
    """Manages distributed tracing and metrics."""
    
    def __init__(self):
        """Initialize telemetry components."""
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        self._initialized = False
        
        # Metrics
        self.request_counter = None
        self.request_duration = None
        self.ocr_counter = None
        self.ocr_duration = None
        self.cache_hits = None
        self.cache_misses = None
        self.error_counter = None
    
    def initialize(self, otlp_endpoint: str = None, app_env: str = "development"):
        """
        Initialize OpenTelemetry tracing and metrics.
        
        Args:
            otlp_endpoint: OTLP collector endpoint
            app_env: Application environment
        """
        if self._initialized:
            return
        
        endpoint = otlp_endpoint or "localhost:4317"
        
        # Service resource
        resource = Resource.create({
            "service.name": "screen2deck",
            "service.version": "1.0.0",
            "deployment.environment": app_env
        })
        
        try:
            # Setup tracing
            self._setup_tracing(endpoint, resource)
            
            # Setup metrics
            self._setup_metrics(endpoint, resource)
            
            # Setup propagator
            set_global_textmap(TraceContextTextMapPropagator())
            
            # Auto-instrument libraries
            self._setup_instrumentation()
            
            self._initialized = True
            basic_logger.info(f"Telemetry initialized with endpoint: {endpoint}")
            
        except Exception as e:
            basic_logger.error(f"Failed to initialize telemetry: {e}")
    
    def _setup_tracing(self, endpoint: str, resource: Resource):
        """Setup distributed tracing."""
        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True  # Use TLS in production
        )
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Add batch processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        self.tracer_provider.add_span_processor(span_processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer("screen2deck.backend")
    
    def _setup_metrics(self, endpoint: str, resource: Resource):
        """Setup metrics collection."""
        # Create OTLP metric exporter
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=endpoint,
            insecure=True
        )
        
        # Create metric reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_metric_exporter,
            export_interval_millis=10000  # Export every 10 seconds
        )
        
        # Create meter provider
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        
        # Set global meter provider
        set_meter_provider(self.meter_provider)
        
        # Get meter
        self.meter = metrics.get_meter("screen2deck.backend")
        
        # Create metrics
        self._create_metrics()
    
    def _create_metrics(self):
        """Create application metrics."""
        # Request metrics
        self.request_counter = self.meter.create_counter(
            "http_requests_total",
            description="Total HTTP requests",
            unit="1"
        )
        
        self.request_duration = self.meter.create_histogram(
            "http_request_duration_seconds",
            description="HTTP request duration",
            unit="s"
        )
        
        # OCR metrics
        self.ocr_counter = self.meter.create_counter(
            "ocr_requests_total",
            description="Total OCR requests",
            unit="1"
        )
        
        self.ocr_duration = self.meter.create_histogram(
            "ocr_processing_duration_seconds",
            description="OCR processing duration",
            unit="s"
        )
        
        # Cache metrics
        self.cache_hits = self.meter.create_counter(
            "cache_hits_total",
            description="Total cache hits",
            unit="1"
        )
        
        self.cache_misses = self.meter.create_counter(
            "cache_misses_total",
            description="Total cache misses",
            unit="1"
        )
        
        # Error metrics
        self.error_counter = self.meter.create_counter(
            "errors_total",
            description="Total errors",
            unit="1"
        )
    
    def _setup_instrumentation(self):
        """Setup automatic instrumentation for libraries."""
        try:
            # FastAPI
            FastAPIInstrumentor.instrument(tracer_provider=self.tracer_provider)
            
            # Redis
            RedisInstrumentor().instrument(tracer_provider=self.tracer_provider)
            
            # Celery
            CeleryInstrumentor().instrument(tracer_provider=self.tracer_provider)
            
            # Logging
            LoggingInstrumentor().instrument(tracer_provider=self.tracer_provider)
        except Exception as e:
            basic_logger.warning(f"Failed to setup instrumentation: {e}")
    
    @contextmanager
    def span(self, name: str, attributes: Dict[str, Any] = None):
        """
        Create a traced span.
        
        Args:
            name: Span name
            attributes: Span attributes
        """
        if not self.tracer:
            yield None
            return
        
        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def record_request(self, method: str, path: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        if not self.request_counter:
            return
        
        labels = {
            "method": method,
            "path": path,
            "status": str(status_code)
        }
        
        self.request_counter.add(1, labels)
        self.request_duration.record(duration, labels)
    
    def record_ocr(self, status: str, duration: float):
        """Record OCR processing metrics."""
        if not self.ocr_counter:
            return
        
        labels = {"status": status}
        self.ocr_counter.add(1, labels)
        self.ocr_duration.record(duration, labels)
    
    def record_cache(self, hit: bool, operation: str = "get"):
        """Record cache metrics."""
        if hit and self.cache_hits:
            self.cache_hits.add(1, {"operation": operation})
        elif not hit and self.cache_misses:
            self.cache_misses.add(1, {"operation": operation})
    
    def record_error(self, error_type: str, endpoint: str = None):
        """Record error metrics."""
        if not self.error_counter:
            return
        
        labels = {"type": error_type}
        if endpoint:
            labels["endpoint"] = endpoint
        
        self.error_counter.add(1, labels)
    
    def get_current_trace_id(self) -> Optional[str]:
        """Get current trace ID."""
        span = trace.get_current_span()
        if span and span.is_recording():
            context = span.get_span_context()
            return format(context.trace_id, "032x")
        return None
    
    def shutdown(self):
        """Shutdown telemetry providers."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()
        if self.meter_provider:
            self.meter_provider.shutdown()
        self._initialized = False

# Global telemetry manager
telemetry = TelemetryManager()

def trace_async(name: str):
    """Decorator for tracing async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with telemetry.span(name):
                return await func(*args, **kwargs)
        return wrapper
    return decorator

def trace_sync(name: str):
    """Decorator for tracing sync functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with telemetry.span(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator

class TracedLogger:
    """Logger that includes trace context."""
    
    def __init__(self, name: str):
        """Initialize traced logger."""
        self.logger = logging.getLogger(name)
        # Ensure it has the JSON formatter
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def _add_trace_context(self, extra: dict = None) -> dict:
        """Add trace context to log extra."""
        if extra is None:
            extra = {}
        
        trace_id = telemetry.get_current_trace_id()
        if trace_id:
            extra["trace_id"] = trace_id
        
        span = trace.get_current_span()
        if span and span.is_recording():
            extra["span_id"] = format(span.get_span_context().span_id, "016x")
        
        return extra
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug with trace context."""
        kwargs["extra"] = self._add_trace_context(kwargs.get("extra"))
        self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log info with trace context."""
        kwargs["extra"] = self._add_trace_context(kwargs.get("extra"))
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning with trace context."""
        kwargs["extra"] = self._add_trace_context(kwargs.get("extra"))
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error with trace context."""
        kwargs["extra"] = self._add_trace_context(kwargs.get("extra"))
        self.logger.error(msg, *args, **kwargs)
        
        # Record error metric
        telemetry.record_error("application_error")
    
    def critical(self, msg: str, *args, **kwargs):
        """Log critical with trace context."""
        kwargs["extra"] = self._add_trace_context(kwargs.get("extra"))
        self.logger.critical(msg, *args, **kwargs)
        
        # Record error metric
        telemetry.record_error("critical_error")

# Export traced logger as default (backward compatible)
logger = TracedLogger(__name__)