"""
Routers Package.
"""
from src.api.routers.dataset_jobs import router as dataset_jobs_router
from src.api.routers.health import router as health_router
from src.api.routers.recommendations import router as recommendations_router
from src.api.routers.trust import router as trust_router

__all__ = ["dataset_jobs_router", "health_router", "recommendations_router", "trust_router"]
