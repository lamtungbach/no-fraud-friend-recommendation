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


def calculate_dyadic_safety_score(
    mutual_total_count: int = 0,
    mutual_tier1_count: int = 0,
    asymmetry_penalty: float = 0.0,
    alpha: float = 0.20,
) -> float:
    """
    Tính điểm an toàn tương tác cặp đôi S_safe_pair(u, v) in [0.0, 1.0].

    Phòng thủ 2 lớp:
    1. Khử độc bẫy bạn chung (Anti-Triadic Infiltration):
       - Đánh giá tỷ lệ bạn chung đạt chuẩn Tier 1 Verified Safe bảo chứng.
       - Purity_ratio = min(mutual_tier1, mutual_total) / mutual_total.
       - Purity_score = alpha + (1.0 - alpha) * Purity_ratio.
       - Nếu mutual_total == 0 (gợi ý không qua topo bạn chung): Purity_score = 1.0.
    2. Phạt spam tương tác một chiều bất đối xứng (Directional Spam / Asymmetry):
       - Asymmetry_score = 1.0 - asymmetry_penalty.

    S_safe_pair(u, v) = Purity_score * Asymmetry_score in [0.0, 1.0].
    """
    safe_alpha = max(0.0, min(1.0, float(alpha)))
    safe_asym = max(0.0, min(1.0, float(asymmetry_penalty)))

    if mutual_total_count <= 0:
        purity_score = 1.0
    else:
        valid_tier1 = min(max(0, int(mutual_tier1_count)), int(mutual_total_count))
        purity_ratio = float(valid_tier1) / float(mutual_total_count)
        purity_score = safe_alpha + (1.0 - safe_alpha) * purity_ratio

    asym_score = 1.0 - safe_asym
    raw_score = purity_score * asym_score
    return max(0.0, min(1.0, float(raw_score)))


def calculate_final_ranking_score(
    pymk_relevance: float,
    trust_score: float,
    dyadic_safety: float = 1.0,
) -> float:
    """
    Tính điểm tái xếp hạng hợp nhất Final_Score:
    Final_Score(u, v) = PYMK_Relevance(u, v) * (S_trust(v) / 100.0) * S_safe_pair(u, v)
    """
    safe_pymk = max(0.0, float(pymk_relevance))
    safe_trust = max(0.0, min(100.0, float(trust_score))) / 100.0
    safe_dyadic = max(0.0, min(1.0, float(dyadic_safety)))
    return float(safe_pymk * safe_trust * safe_dyadic)


def evaluate_candidate_admission(
    tier: RecommendationTier,
    mutual_tier1_count: int = 0,
    tier3_threshold: int = 5,
) -> Tuple[bool, str]:
    """
    Đánh giá điều kiện cho phép hiển thị ứng viên theo chính sách can thiệp phân tầng:
    - Tier 1 (Verified Safe): Cho phép hiển thị, ưu tiên top đầu.
    - Tier 2 (Standard Trust): Cho phép hiển thị tiêu chuẩn.
    - Tier 3 (Restricted Caution): Chỉ cho phép hiển thị nếu có >= tier3_threshold bạn chung Tier 1 bảo lãnh.
    - Tier 4 (Quarantine Fraud): Cách ly tuyệt đối 100%.
    """
    if tier == RecommendationTier.TIER_1_VERIFIED:
        return True, "[CHO PHEP] - Ưu tiên đề xuất (Tier 1 Verified Safe)"
    elif tier == RecommendationTier.TIER_2_STANDARD:
        return True, "[CHO PHEP] - Đủ điều kiện đề xuất tiêu chuẩn (Tier 2 Standard Trust)"
    elif tier == RecommendationTier.TIER_3_RESTRICTED:
        if mutual_tier1_count >= tier3_threshold:
            return (
                True,
                f"[CUU XET] - Cho phép đề xuất: có {mutual_tier1_count} bạn chung Tier 1 bảo lãnh (ngưỡng >= {tier3_threshold})",
            )
        else:
            return (
                False,
                f"[AN] - Ẩn khỏi danh sách gợi ý: chỉ có {mutual_tier1_count} bạn chung Tier 1 (yêu cầu tối thiểu >= {tier3_threshold})",
            )
    else:
        return False, "[CACH LY] - Loại bỏ 100%: tài khoản bị gắn cờ gian lận / botnet (Tier 4 Fraud)"
