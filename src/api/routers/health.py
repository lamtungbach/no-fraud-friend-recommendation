"""
Router kiểm tra trạng thái sức khỏe của hệ thống (Health Check Endpoint).
"""

from fastapi import APIRouter, Request, Response, status

from src.api.observability import ACTIVE_GRAPH
from src.api.runtime import ApiRuntime

router = APIRouter(tags=["Hệ thống"])


def _runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


@router.get("/health/live", summary="Liveness của process")
def live_check():
    """Only proves that the ASGI process can answer a request."""
    return {"status": "live"}


@router.get("/health/ready", summary="Readiness graph/index và Trust runtime")
def ready_check(request: Request, response: Response):
    runtime = _runtime(request)
    ready, reasons, graph_version = runtime.readiness()
    if graph_version is not None:
        ACTIVE_GRAPH.labels(graph_version=graph_version).set(1)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "environment": runtime.settings.environment,
        "graph_version": graph_version,
        "trust_provider": runtime.settings.trust_provider,
        "reasons": reasons,
    }


@router.get("/health", summary="Compatibility health check")
def health_check(request: Request):
    """Keep the legacy endpoint available; use ``/health/ready`` for readiness."""
    runtime = _runtime(request)
    ready, reasons, _ = runtime.readiness()
    return {
        "status": "healthy",
        "service": "No-Fraud Friend Recommendation API",
        "cache_loaded": bool(runtime.trust_service and runtime.trust_service.is_loaded),
        "indexed_users": len(runtime.trust_service.cache) if runtime.trust_service else 0,
        "ready": ready,
        "reasons": reasons,
    }
