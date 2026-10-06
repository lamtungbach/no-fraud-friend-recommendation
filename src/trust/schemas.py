"""
Schemas Pydantic cho Trust & Fraud Detection Module.
Định nghĩa Data Contract trao đổi giữa Fraud Engine, PYMK Engine và API Layer.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RecommendationTier(str, Enum):
    """Phân tầng chính sách đề xuất kết bạn."""
    TIER_1_VERIFIED = "TIER_1_VERIFIED_SAFE"
    TIER_2_STANDARD = "TIER_2_STANDARD_TRUST"
    TIER_3_RESTRICTED = "TIER_3_RESTRICTED_CAUTION"
    TIER_4_FRAUD = "TIER_4_QUARANTINE_FRAUD"


class PillarScores(BaseModel):
    """Điểm số 4 trụ cột tín nhiệm người dùng."""
    identity_auth: float = Field(..., description="Trụ cột 1: Độ Xác thực Danh tính (S_auth)")
    interaction_health: float = Field(..., description="Trụ cột 2: Độ Lành mạnh Tương tác (S_interact)")
    network_hygiene: float = Field(..., description="Trụ cột 3: Độ Trong sạch Mạng lưới (S_network)")
    content_safety: float = Field(..., description="Trụ cột 4: Độ An toàn Nội dung (S_content)")


class TrustProfileResponse(BaseModel):
    """Hồ sơ thẩm định tín nhiệm đầy đủ của một người dùng."""
    user_id: int = Field(..., description="User ID trong đồ thị (0 - 10,198)")
    ground_truth_label: str = Field(..., description="Nhãn thực tế (Human hoặc Bot)")
    p_bot: float = Field(..., description="Xác suất Bot do R-GCN dự đoán (0.0 - 1.0)")
    trust_score: float = Field(..., description="Điểm Tín nhiệm Toàn diện S_trust (0.0 - 100.0)")
    recommendation_tier: RecommendationTier = Field(..., description="Phân tầng Chính sách (Tier 1 đến Tier 4)")
    decision: str = Field(..., description="Quyết định nghiệp vụ gợi ý kết bạn")
    is_recommendable: bool = Field(..., description="Có đủ điều kiện gợi ý an toàn hay không (True nếu Tier 1 hoặc Tier 2)")
    split_set: str = Field("unknown", description="Tập dữ liệu phân chia (train / val / test)")
    pillars: PillarScores = Field(..., description="Chi tiết điểm 4 trụ cột thành phần")


class SingleUserRequest(BaseModel):
    """Yêu cầu thẩm định cho 1 User ID."""
    user_id: int = Field(..., ge=0, description="User ID cần kiểm tra")


class BatchTrustRequest(BaseModel):
    """Yêu cầu thẩm định cho một danh sách User ID."""
    user_ids: List[int] = Field(..., description="Danh sách các User ID cần kiểm tra điểm số")


class SafeFilterRequest(BaseModel):
    """Yêu cầu lọc danh sách ứng viên kết bạn từ PYMK Engine."""
    target_user_id: int = Field(..., description="User ID của người nhận gợi ý kết bạn")
    candidate_user_ids: List[int] = Field(..., description="Danh sách candidate do PYMK đề xuất")


class CandidateFilterItem(BaseModel):
    """Thông tin ứng viên sau khi qua bộ lọc thẩm định tín nhiệm."""
    user_id: int
    trust_score: float
    recommendation_tier: RecommendationTier
    reason: str


class SafeFilterResponse(BaseModel):
    """Kết quả lọc an toàn trả về cho PYMK Engine."""
    target_user_id: int
    total_candidates: int
    safe_recommendations_count: int
    safe_candidates: List[CandidateFilterItem] = Field(..., description="Ứng viên an toàn được phép gợi ý (Tier 1 & Tier 2)")
    filtered_out_candidates: List[CandidateFilterItem] = Field(..., description="Ứng viên bị chặn/cảnh giác (Tier 3 & Tier 4)")
