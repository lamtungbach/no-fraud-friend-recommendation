"""
Schemas Pydantic cho Trust & Fraud Detection Module.
Định nghĩa Data Contract trao đổi giữa Fraud Engine, PYMK Engine và API Layer.
"""

from enum import Enum
from typing import List
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


class CandidateReRankInput(BaseModel):
    """Ứng viên đầu vào kèm điểm liên quan PYMK và bạn chung uy tín cao."""
    candidate_id: int = Field(..., ge=0, description="User ID của ứng viên")
    pymk_score: float = Field(..., ge=0.0, description="Điểm tương quan PYMK từ mô hình cấu trúc đồ thị")
    mutual_tier1_count: int = Field(0, ge=0, description="Số bạn chung đạt Tier 1 Verified Safe giữa target user và ứng viên")


class CandidateReRankItem(BaseModel):
    """Ứng viên sau khi thẩm định và tái xếp hạng an toàn."""
    candidate_id: int = Field(..., description="User ID ứng viên")
    trust_score: float = Field(..., description="Điểm tín nhiệm toàn diện S_trust (0 - 100)")
    recommendation_tier: RecommendationTier = Field(..., description="Phân tầng chính sách (Tier 1 đến Tier 4)")
    pymk_score: float = Field(..., description="Điểm tương quan gốc từ PYMK")
    dyadic_safety_score: float = Field(1.0, ge=0.0, le=1.0, description="Điểm an toàn tương tác cặp đôi S_safe_pair")
    final_ranking_score: float = Field(..., description="Điểm tái xếp hạng cuối cùng (Final_Score)")
    is_allowed: bool = Field(..., description="Có đủ điều kiện hiển thị trên PYMK hay không")
    reason: str = Field(..., description="Giải thích nguyên nhân hoặc chính sách can thiệp")


class SafeReRankRequest(BaseModel):
    """Yêu cầu tái xếp hạng danh sách ứng viên kết bạn."""
    target_user_id: int = Field(..., ge=0, description="User ID của người nhận gợi ý kết bạn")
    candidates: List[CandidateReRankInput] = Field(..., description="Danh sách ứng viên kèm điểm PYMK từ recommendation engine")
    tier3_threshold: int = Field(5, ge=1, description="Số lượng bạn chung Tier 1 tối thiểu để cho phép hiển thị ứng viên Tier 3")


class SafeReRankResponse(BaseModel):
    """Kết quả tái xếp hạng an toàn cho PYMK Engine."""
    target_user_id: int
    total_candidates: int
    passed_count: int
    blocked_count: int
    ranked_candidates: List[CandidateReRankItem] = Field(..., description="Danh sách ứng viên an toàn đã được tái xếp hạng giảm dần")
    blocked_candidates: List[CandidateReRankItem] = Field(..., description="Danh sách ứng viên bị loại bỏ (Tier 4 hoặc Tier 3 thiếu bảo lãnh)")
