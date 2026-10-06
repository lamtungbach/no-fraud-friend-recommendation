import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.deps import get_trust_service
from src.trust.schemas import PillarScores, RecommendationTier, TrustProfileResponse

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_profiles():
    service = get_trust_service()
    if not service.is_loaded:
        service.cache[0] = TrustProfileResponse(
            user_id=0,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.05,
            trust_score=88.5,
            recommendation_tier=RecommendationTier.TIER_1_VERIFIED,
            decision="[OK] TIER_1_VERIFIED",
            is_recommendable=True,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.9,
                interaction_health=0.85,
                network_hygiene=0.8,
                content_safety=0.9,
            ),
        )
        service.cache[1] = TrustProfileResponse(
            user_id=1,
            ground_truth_label="Human (Nguoi that)",
            p_bot=0.15,
            trust_score=72.0,
            recommendation_tier=RecommendationTier.TIER_2_STANDARD,
            decision="[OK] TIER_2_STANDARD",
            is_recommendable=True,
            split_set="test",
            pillars=PillarScores(
                identity_auth=0.7,
                interaction_health=0.75,
                network_hygiene=0.7,
                content_safety=0.7,
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
