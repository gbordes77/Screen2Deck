"""
API routers for Screen2Deck.

`routers.metrics` was deleted in v2.4.0 cleanup: its router was never
mounted (the real /metrics endpoint is a sub-app built by
`core.metrics_minimal.create_metrics_app`) and its Prometheus
collectors were dead duplicates.
"""

from .health import router as health_router
from .auth_router import router as auth_router
from .export_router import router as export_router

__all__ = [
    "health_router",
    "auth_router",
    "export_router",
]