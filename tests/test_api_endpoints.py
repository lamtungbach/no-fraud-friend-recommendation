import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.api.deps import get_trust_service  # noqa: E402
from src.trust.schemas import PillarScores, RecommendationTier, TrustProfileResponse  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_profiles():
    service = get_trust_service()
    if not service.is_loaded:
        service.cache[0] = TrustProfileResponse(
            user_id=0,
            ground_truth_label="Bot (Tai khoan ao)",
            p_bot=0.95,
            trust_score=15.01,
            recommendation_tier=RecommendationTier.TIER_4_FRAUD,
            decision="[CACH LY]",
            is_recommendable=False,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.1,
                interaction_health=0.1,
                network_hygiene=0.1,
                content_safety=0.1,
            ),
        )
        service.cache[1] = TrustProfileResponse(
            user_id=1,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.25,
            trust_score=59.51,
            recommendation_tier=RecommendationTier.TIER_3_RESTRICTED,
            decision="[CANH GIAC]",
            is_recommendable=False,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.5,
                interaction_health=0.6,
                network_hygiene=0.6,
                content_safety=0.6,
            ),
        )
        service.cache[4] = TrustProfileResponse(
            user_id=4,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.15,
            trust_score=72.07,
            recommendation_tier=RecommendationTier.TIER_2_STANDARD,
            decision="[OK]",
            is_recommendable=True,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.7,
                interaction_health=0.75,
                network_hygiene=0.7,
                content_safety=0.7,
            ),
        )
        service.cache[13] = TrustProfileResponse(
            user_id=13,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.03,
            trust_score=84.13,
            recommendation_tier=RecommendationTier.TIER_1_VERIFIED,
            decision="[OK]",
            is_recommendable=True,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.85,
                interaction_health=0.85,
                network_hygiene=0.85,
                content_safety=0.85,
            ),
        )
        service.is_loaded = True



def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "docs" in data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "indexed_users" in data


def test_get_user_trust_by_path():
    # User 0 exists in MGTAB profiles
    response = client.get("/api/v1/trust/0")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 0
    assert "trust_score" in data
    assert "recommendation_tier" in data
    assert "pillars" in data


def test_get_user_trust_not_found():
    response = client.get("/api/v1/trust/999999")
    assert response.status_code == 404


def test_check_user_trust_by_body():
    response = client.post("/api/v1/trust/check", json={"user_id": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 0


def test_check_batch_trust():
    response = client.post("/api/v1/trust/batch", json={"user_ids": [0, 1, 999999]})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # 0 and 1 exist, 999999 does not


def test_agent_reasoning_endpoint():
    response = client.post("/api/v1/trust/reason", json={"user_id": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 0
    assert "reasoning_trace" in data
    assert len(data["reasoning_trace"]) > 0


def test_safe_filter_endpoint():
    response = client.post(
        "/api/v1/recommendations/safe-filter",
        json={
            "target_user_id": 100,
            "candidate_user_ids": [0, 1, 999999],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_user_id"] == 100
    assert data["total_candidates"] == 3
    assert len(data["safe_candidates"]) + len(data["filtered_out_candidates"]) == 3


def test_safe_rerank_endpoint():
    response = client.post(
        "/api/v1/recommendations/safe-rerank",
        json={
            "target_user_id": 100,
            "candidates": [
                {"candidate_id": 13, "pymk_score": 0.8, "mutual_tier1_count": 0},
                {"candidate_id": 4, "pymk_score": 0.8, "mutual_tier1_count": 0},
                {"candidate_id": 1, "pymk_score": 0.8, "mutual_tier1_count": 5},
                {"candidate_id": 0, "pymk_score": 0.9, "mutual_tier1_count": 10},
                {"candidate_id": 999999, "pymk_score": 0.9, "mutual_tier1_count": 0},
            ],
            "tier3_threshold": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_user_id"] == 100
    assert data["total_candidates"] == 5
    assert data["passed_count"] == 3  # 13 (Tier 1), 4 (Tier 2), 1 (Tier 3 rescued)
    assert data["blocked_count"] == 2  # 0 (Tier 4 blocked) and 999999 (unknown blocked)
    assert len(data["ranked_candidates"]) == 3
    # Verify candidate 13 is ranked higher than candidate 4
    assert data["ranked_candidates"][0]["candidate_id"] == 13
    assert data["ranked_candidates"][1]["candidate_id"] == 4
    assert data["ranked_candidates"][2]["candidate_id"] == 1
    assert data["ranked_candidates"][0]["final_ranking_score"] > data["ranked_candidates"][1]["final_ranking_score"]
