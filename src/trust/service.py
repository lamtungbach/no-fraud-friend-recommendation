"""
Dịch vụ Quản lý & Thẩm định Tín nhiệm Người dùng (Trust Evaluation Service).
Hỗ trợ cả tra cứu nhanh In-Memory Cache O(1) và tích hợp Bộ lọc An toàn cho PYMK.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from src.trust.schemas import (
    CandidateFilterItem,
    CandidateReRankInput,
    CandidateReRankItem,
    PillarScores,
    RecommendationTier,
    SafeFilterResponse,
    SafeReRankResponse,
    TrustProfileResponse,
)
from src.trust.scoring import (
    calculate_dyadic_safety_score,
    calculate_final_ranking_score,
    evaluate_candidate_admission,
    get_decision_meta,
)


class TrustService:
    """
    Service quản lý hồ sơ tín nhiệm người dùng và bộ lọc gian lận.
    """

    def __init__(self, profiles_path: Optional[str] = None):
        self.profiles_path = profiles_path or self._default_profiles_path()
        self.cache: Dict[int, TrustProfileResponse] = {}
        self.is_loaded = False
        if self.profiles_path and os.path.exists(self.profiles_path):
            self.load_profiles()

    def _default_profiles_path(self) -> str:
        # Đường dẫn mặc định: data/mgtab_user_trust_profiles_v2.csv
        root = Path(__file__).resolve().parents[2]
        return str(root / "data" / "mgtab_user_trust_profiles_v2.csv")

    def load_profiles(self) -> int:
        """
        Đọc file CSV hồ sơ tín nhiệm và nạp vào in-memory cache để tra cứu O(1).
        """
        if not os.path.exists(self.profiles_path):
            raise FileNotFoundError(f"Không tìm thấy file hồ sơ tại: {self.profiles_path}")

        df = pd.read_csv(self.profiles_path)
        new_cache = {}

        for _, row in df.iterrows():
            u_id = int(row["user_id"])
            raw_tier = str(row["recommendation_tier"])
            tier = RecommendationTier(raw_tier)
            decision, is_rec = get_decision_meta(tier)
            gt_label = "Human (Nguoi that)" if row["ground_truth_label"] == 0 else "Bot (Tai khoan ao)"

            new_cache[u_id] = TrustProfileResponse(
                user_id=u_id,
                ground_truth_label=gt_label,
                p_bot=float(row["p_bot"]),
                trust_score=float(row["trust_score"]),
                recommendation_tier=tier,
                decision=decision,
                is_recommendable=is_rec,
                split_set=str(row.get("split", "unknown")),
                pillars=PillarScores(
                    identity_auth=float(row["identity_auth_score"]),
                    interaction_health=float(row["interaction_health_score"]),
                    network_hygiene=float(row["network_hygiene_score"]),
                    content_safety=float(row["content_safety_score"]),
                ),
            )

        self.cache = new_cache
        self.is_loaded = True
        return len(self.cache)

    def get_user_profile(self, user_id: int) -> Optional[TrustProfileResponse]:
        """
        Lấy thông tin tín nhiệm của 1 user. Trả về None nếu không tồn tại.
        """
        return self.cache.get(user_id)

    def filter_safe_candidates(self, target_user_id: int, candidate_user_ids: List[int]) -> SafeFilterResponse:
        """
        Bộ lọc an toàn: Phân loại danh sách ứng viên thành 2 nhóm:
        - safe_candidates: Thuộc Tier 1 hoặc Tier 2 (đủ điều kiện gợi ý).
        - filtered_out_candidates: Thuộc Tier 3 hoặc Tier 4 (bị chặn/cảnh giác).
        """
        safe_list: List[CandidateFilterItem] = []
        blocked_list: List[CandidateFilterItem] = []

        for c_id in candidate_user_ids:
            cand = self.cache.get(c_id)
            if cand is None:
                # Nếu không có hồ sơ, mặc định đưa vào diện cảnh giác
                blocked_list.append(
                    CandidateFilterItem(
                        user_id=c_id,
                        trust_score=0.0,
                        recommendation_tier=RecommendationTier.TIER_4_FRAUD,
                        reason="[KHONG XAC THUC] - Không tìm thấy hồ sơ tín nhiệm của người dùng.",
                    )
                )
                continue

            item = CandidateFilterItem(
                user_id=cand.user_id,
                trust_score=cand.trust_score,
                recommendation_tier=cand.recommendation_tier,
                reason=cand.decision,
            )

            if cand.is_recommendable:
                safe_list.append(item)
            else:
                blocked_list.append(item)

        return SafeFilterResponse(
            target_user_id=target_user_id,
            total_candidates=len(candidate_user_ids),
            safe_recommendations_count=len(safe_list),
            safe_candidates=safe_list,
            filtered_out_candidates=blocked_list,
        )

    def rerank_candidates(
        self,
        target_user_id: int,
        candidates: List[CandidateReRankInput],
        tier3_threshold: int = 5,
    ) -> SafeReRankResponse:
        """
        Tái xếp hạng an toàn danh sách ứng viên từ PYMK Engine:
        1. Tra cứu điểm tín nhiệm và phân tầng từ cache O(1).
        2. Tính Final_Score = pymk_score * (trust_score / 100) * dyadic_safety.
        3. Áp dụng chính sách can thiệp phân tầng (Tier 1-4, cứu xét Tier 3 nếu mutual_tier1_count >= tier3_threshold).
        4. Sắp xếp tất định: final_ranking_score DESC, candidate_id ASC.
        """
        passed_list: List[CandidateReRankItem] = []
        blocked_list: List[CandidateReRankItem] = []

        for cand_in in candidates:
            c_id = cand_in.candidate_id
            profile = self.cache.get(c_id)

            if profile is None:
                tier = RecommendationTier.TIER_4_FRAUD
                trust_score = 0.0
                dyadic_score = 0.0
                final_score = 0.0
                is_allowed = False
                reason = "[KHONG XAC THUC] - Không tìm thấy hồ sơ tín nhiệm của người dùng trong hệ thống."
            else:
                tier = profile.recommendation_tier
                trust_score = profile.trust_score
                dyadic_score = calculate_dyadic_safety_score(
                    mutual_total_count=cand_in.mutual_total_count,
                    mutual_tier1_count=cand_in.mutual_tier1_count,
                    asymmetry_penalty=cand_in.asymmetry_penalty,
                )
                final_score = calculate_final_ranking_score(
                    cand_in.pymk_score,
                    trust_score,
                    dyadic_score,
                )
                is_allowed, base_reason = evaluate_candidate_admission(
                    tier,
                    cand_in.mutual_tier1_count,
                    tier3_threshold=tier3_threshold,
                )
                if dyadic_score < 1.0 and is_allowed:
                    if cand_in.asymmetry_penalty > 0.0:
                        reason = f"{base_reason} | [CANH BAO SPAM] - Phạt spam một chiều (dyadic={dyadic_score:.2f})"
                    elif cand_in.mutual_total_count > 0 and cand_in.mutual_tier1_count < cand_in.mutual_total_count:
                        reason = f"{base_reason} | [CANH BAO BAY BAN CHUNG] - Chiết khấu bẫy bạn chung: {cand_in.mutual_tier1_count}/{cand_in.mutual_total_count} bạn Tier 1 (dyadic={dyadic_score:.2f})"
                    else:
                        reason = f"{base_reason} | [CANH BAO CAP DOI] - Chiết khấu an toàn cặp đôi (dyadic={dyadic_score:.2f})"
                else:
                    reason = base_reason

            item = CandidateReRankItem(
                candidate_id=c_id,
                trust_score=round(trust_score, 2),
                recommendation_tier=tier,
                pymk_score=round(cand_in.pymk_score, 4),
                dyadic_safety_score=round(dyadic_score, 4),
                final_ranking_score=round(final_score, 4),
                is_allowed=is_allowed,
                reason=reason,
            )

            if is_allowed:
                passed_list.append(item)
            else:
                blocked_list.append(item)

        # Sắp xếp tất định: Điểm cao nhất lên đầu (DESC), nếu bằng điểm thì ID nhỏ trước (ASC)
        passed_list.sort(key=lambda x: (-x.final_ranking_score, x.candidate_id))
        blocked_list.sort(key=lambda x: (-x.final_ranking_score, x.candidate_id))

        return SafeReRankResponse(
            target_user_id=target_user_id,
            total_candidates=len(candidates),
            passed_count=len(passed_list),
            blocked_count=len(blocked_list),
            ranked_candidates=passed_list,
            blocked_candidates=blocked_list,
        )
