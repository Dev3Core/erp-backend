"""Insights: read-only dashboard metrics and CSV/PDF exports. Consumer-only
module: nothing else depends on it."""

from app.modules.insights.routers.exports import router as exports_router
from app.modules.insights.routers.metrics import router as metrics_router

__all__ = ["exports_router", "metrics_router"]
