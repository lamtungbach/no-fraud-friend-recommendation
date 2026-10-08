"""
Router phục vụ các chức năng Thẩm định Tín nhiệm & Lọc Gợi ý An toàn (Trust & Fraud API).
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.deps import get_trust_agent, get_trust_service
from src.trust.agent import TrustAgent
from src.trust.schemas import (
    BatchTrustRequest,
    SafeFilterRequest,
    SafeFilterResponse,
    SingleUserRequest,
    TrustProfileResponse,
)
from src.trust.service import TrustService

router = APIRouter(prefix="/api/v1", tags=["Thẩm định Tín nhiệm & Phát hiện Gian lận"])


@router.get(
    "/trust/{user_id}",
    response_model=TrustProfileResponse,
    summary="1. Kiểm tra điểm tín nhiệm qua User ID (Path Parameter)",
)
def get_user_trust_by_path(
    user_id: int = Path(..., ge=0, description="User ID cần kiểm tra trong đồ thị"),
    service: TrustService = Depends(get_trust_service),
):
    profile = service.get_user_profile(user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ cho User ID: {user_id}",
        )
    return profile


@router.post(
    "/trust/check",
    response_model=TrustProfileResponse,
    summary="2. Kiểm tra điểm tín nhiệm qua JSON Request Body",
)
def check_user_trust_by_body(
    req: SingleUserRequest,
    service: TrustService = Depends(get_trust_service),
):
    profile = service.get_user_profile(req.user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy User ID: {req.user_id}",
        )
    return profile


@router.post(
    "/trust/batch",
    response_model=List[TrustProfileResponse],
    summary="3. Kiểm tra hàng loạt nhiều User ID cùng lúc",
)
def check_batch_trust(
    req: BatchTrustRequest,
    service: TrustService = Depends(get_trust_service),
):
    results = []
    for u_id in req.user_ids:
        p = service.get_user_profile(u_id)
        if p is not None:
            results.append(p)
    return results


@router.post(
    "/trust/reason",
    summary="4. Thẩm định chuyên sâu & Giải thích quyết định (Trust Agent Reasoning)",
)
def inspect_and_reason(
    req: SingleUserRequest,
    agent: TrustAgent = Depends(get_trust_agent),
) -> Dict[str, Any]:
    """
    Quy trình Agentic multi-step reasoning:
    Phân tích rủi ro Bot từ R-GCN + Đánh giá 4 trụ cột + Trả về chuỗi suy luận (Reasoning Trace).
    """
    return agent.inspect_and_reason(req.user_id)


@router.post(
    "/recommendations/safe-filter",
    response_model=SafeFilterResponse,
    summary="5. Bộ lọc Bạn bè An toàn cho PYMK Engine (Safe Friend Filter)",
)
def filter_safe_recommendations(
    req: SafeFilterRequest,
    service: TrustService = Depends(get_trust_service),
):
    """
    Nhận danh sách candidate từ PYMK và tự động:
    - Giữ lại: Tier 1 (An toàn tuyệt đối) & Tier 2 (Tín nhiệm tiêu chuẩn).
    - Loại bỏ: Tier 3 (Hạn chế người lạ) & Tier 4 (Cách ly gian lận).
    """
    return service.filter_safe_candidates(req.target_user_id, req.candidate_user_ids)
