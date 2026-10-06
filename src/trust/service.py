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
    PillarScores,
    RecommendationTier,
    SafeFilterResponse,
    TrustProfileResponse,
)
from src.trust.scoring import classify_trust_tier, get_decision_meta


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
