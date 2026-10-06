"""
Dependencies dùng chung cho FastAPI (Dependency Injection).
Khởi tạo Singleton TrustService & TrustAgent để tránh nạp lại dữ liệu nhiều lần.
"""

from functools import lru_cache
from src.trust.service import TrustService
from src.trust.agent import TrustAgent


@lru_cache()
def get_trust_service() -> TrustService:
    """Singleton instance của TrustService."""
    service = TrustService()
    return service


def get_trust_agent() -> TrustAgent:
    """Factory cung cấp TrustAgent từ singleton TrustService."""
    service = get_trust_service()
    return TrustAgent(service)
