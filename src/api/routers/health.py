"""
Router kiểm tra trạng thái sức khỏe của hệ thống (Health Check Endpoint).
"""

from fastapi import APIRouter, Depends
from src.api.deps import get_trust_service
from src.trust.service import TrustService

router = APIRouter(tags=["Hệ thống"])


@router.get("/health", summary="Kiểm tra trạng thái hệ thống")
def health_check(service: TrustService = Depends(get_trust_service)):
    return {
        "status": "healthy",
        "service": "No-Fraud Friend Recommendation API",
        "cache_loaded": service.is_loaded,
        "indexed_users": len(service.cache),
    }
