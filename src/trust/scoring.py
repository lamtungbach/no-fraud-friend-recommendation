"""
Công thức tính điểm Tín nhiệm 4 Trụ cột và Phân tầng Chính sách (Trust Scoring & Tier Classification).
"""

from typing import Tuple
from src.trust.schemas import RecommendationTier

# Trọng số tối ưu học được từ phân tích độ nhạy KS-statistic trong Sprint 1:
# S_auth: 0.35, S_interact: 0.25, S_network: 0.25, S_content: 0.15
DEFAULT_TRUST_WEIGHTS = [0.35, 0.25, 0.25, 0.15]


def calculate_trust_score(
    s_auth: float,
    s_interact: float,
    s_network: float,
    s_content: float,
    g_auth: float = 1.0,
    weights: list = None
) -> float:
    """
    Tính điểm tín nhiệm toàn diện S_trust (thang điểm 0 - 100).
    S_trust(u) = 100 * G_auth(u) * [w_auth*S_auth + w_interact*S_interact + w_net*S_network + w_content*S_content]
    """
    if weights is None:
        weights = DEFAULT_TRUST_WEIGHTS

    raw_score = 100.0 * (
        weights[0] * s_auth +
        weights[1] * s_interact +
        weights[2] * s_network +
        weights[3] * s_content
    )
    score = g_auth * raw_score
    return max(0.0, min(100.0, float(score)))


def classify_trust_tier(score: float, p_bot: float, s_auth: float) -> RecommendationTier:
    """
    Phân tầng chính sách đề xuất kết bạn dựa trên các ngưỡng tín nhiệm và phòng thủ:
    - TIER_4_QUARANTINE_FRAUD: p_bot >= 0.75 hoặc s_auth < 0.20 hoặc score < 45.0
    - TIER_3_RESTRICTED_CAUTION: score < 65.0
    - TIER_2_STANDARD_TRUST: score < 80.0
    - TIER_1_VERIFIED_SAFE: score >= 80.0
    """
    if p_bot >= 0.75 or s_auth < 0.20 or score < 45.0:
        return RecommendationTier.TIER_4_FRAUD
    elif score < 65.0:
        return RecommendationTier.TIER_3_RESTRICTED
    elif score < 80.0:
        return RecommendationTier.TIER_2_STANDARD
    else:
        return RecommendationTier.TIER_1_VERIFIED


def get_decision_meta(tier: RecommendationTier) -> Tuple[str, bool]:
    """
    Trả về thông điệp quyết định nghiệp vụ và cờ cho phép gợi ý (is_recommendable).
    """
    if tier == RecommendationTier.TIER_1_VERIFIED:
        return "[OK] - Xác thực An toàn Tuyệt đối, ưu tiên gợi ý hàng đầu.", True
    elif tier == RecommendationTier.TIER_2_STANDARD:
        return "[OK] - Tín nhiệm Tiêu chuẩn, đủ điều kiện gợi ý kết bạn.", True
    elif tier == RecommendationTier.TIER_3_RESTRICTED:
        return "[CANH GIAC] - Hạn chế, ẩn khỏi người lạ, cần thêm bạn chung.", False
    else:
        return "[CACH LY] - Nghi vấn gian lận/botnet, chặn hoàn toàn khỏi luồng gợi ý.", False
