"""
Agent Thẩm định Tín nhiệm & Phát hiện Gian lận (Trust & Fraud Detection Agent).
Áp dụng tư duy Agentic: Multi-step reasoning + Tool Calling để giải thích quyết định.
"""

from typing import Any, Dict, List
from src.trust.schemas import RecommendationTier, TrustProfileResponse
from src.trust.service import TrustService


class TrustAgent:
    """
    Agent thực hiện quy trình suy luận đa bước (multi-step reasoning)
    và gọi các tools để thẩm định hồ sơ, đưa ra phán quyết và giải thích lý do.
    """

    def __init__(self, service: TrustService):
        self.service = service

    def tool_get_profile(self, user_id: int) -> Dict[str, Any]:
        """Tool 1: Lấy hồ sơ người dùng."""
        profile = self.service.get_user_profile(user_id)
        if profile is None:
            return {"status": "not_found", "user_id": user_id}
        return {"status": "success", "profile": profile}

    def tool_analyze_bot_risk(self, p_bot: float) -> str:
        """Tool 2: Phân tích rủi ro bot/sybil từ mô hình R-GCN."""
        if p_bot >= 0.75:
            return f"Rủi ro Cực cao: Xác suất Bot = {p_bot:.2%}, vượt ngưỡng báo động 75%."
        elif p_bot >= 0.45:
            return f"Rủi ro Trung bình: Xác suất Bot = {p_bot:.2%}, cần theo dõi thêm tương tác."
        else:
            return f"Rủi ro Thấp: Xác suất Bot = {p_bot:.2%}, hành vi giống người thật."

    def tool_analyze_pillars(self, profile: TrustProfileResponse) -> List[str]:
        """Tool 3: Phân tích 4 trụ cột để phát hiện điểm yếu hoặc bất thường."""
        insights = []
        p = profile.pillars
        if p.identity_auth < 0.20:
            insights.append(f"Cảnh báo Danh tính: S_auth = {p.identity_auth:.2f} (< 0.20), nghi vấn clone/mới tạo.")
        if p.interaction_health < 0.40:
            insights.append(f"Cảnh báo Tương tác: S_interact = {p.interaction_health:.2f}, có dấu hiệu spam mention/link.")
        if p.network_hygiene < 0.40:
            insights.append(f"Cảnh báo Mạng lưới: S_network = {p.network_hygiene:.2f}, kết nối với nhiều node độc hại.")
        if p.content_safety < 0.40:
            insights.append(f"Cảnh báo Nội dung: S_content = {p.content_safety:.2f}, tỷ lệ URL/spam cao.")
        if not insights:
            insights.append("Tất cả các trụ cột tín nhiệm đều ở mức an toàn ổn định.")
        return insights

    def inspect_and_reason(self, user_id: int) -> Dict[str, Any]:
        """
        Quy trình suy luận đa bước (Multi-step Reasoning):
        Bước 1: Gọi Tool 1 tra cứu hồ sơ.
        Bước 2: Gọi Tool 2 phân tích nguy cơ Bot từ R-GCN.
        Bước 3: Gọi Tool 3 đánh giá 4 trụ cột hành vi.
        Bước 4: Tổng hợp lý do và đưa ra quyết định gợi ý.
        """
        # Step 1
        res = self.tool_get_profile(user_id)
        if res["status"] != "success":
            return {
                "user_id": user_id,
                "decision": "REJECT",
                "reasoning": ["Không tìm thấy hồ sơ người dùng trong hệ thống."],
                "is_recommendable": False,
            }

        profile: TrustProfileResponse = res["profile"]

        # Step 2
        bot_risk = self.tool_analyze_bot_risk(profile.p_bot)

        # Step 3
        pillar_insights = self.tool_analyze_pillars(profile)

        # Step 4
        reasoning_trace = [bot_risk] + pillar_insights

        return {
            "user_id": user_id,
            "trust_score": profile.trust_score,
            "recommendation_tier": profile.recommendation_tier.value,
            "is_recommendable": profile.is_recommendable,
            "decision": profile.decision,
            "reasoning_trace": reasoning_trace,
        }
