"""
Routers Package.
"""
from src.api.routers.health import router as health_router
from src.api.routers.trust import router as trust_router

__all__ = ["health_router", "trust_router"]
