"""Phase 07 HTTP contract tests for Safe Top-K serving."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.api.config import ApiSettings
from src.api.main import create_app
from src.api.runtime import build_runtime
from src.serving import Eligibility, SafeRecommendation, SafeRecommendationResult


class _SafeEngine:
    def __init__(self, *, cache_hit: bool = False):
        self.cache_hit = cache_hit
        self.calls = []

    def recommend_safe(self, user_id, top_k, **kwargs):
        self.calls.append((user_id, top_k, kwargs))
        return SafeRecommendationResult(
            user_id=user_id,
            recommendations=(
                SafeRecommendation(
                    candidate_id=9,
                    score=0.9,
                    rank=1,
                    eligibility=Eligibility.ELIGIBLE,
                    risk_score=0.1,
                    trust_score=90.0,
                    reason_code="OK",
                ),
            ),
            graph_version="api-test-graph",
            trust_version="csv-without-manifest",
            trust_policy_version="phase06-fail-safe-v1",
            raw_cache_hit=self.cache_hit,
            raw_candidate_count=2,
        )


class _UnknownUserEngine(_SafeEngine):
    def recommend_safe(self, user_id, top_k, **kwargs):
        del user_id, top_k, kwargs
        raise KeyError("Unknown user_id")


def _client(*, cache_hit: bool = False):
    settings = ApiSettings(environment="test", max_top_k=3, raw_top_m=3)
    runtime = SimpleNamespace(
        settings=settings,
        engine=_SafeEngine(cache_hit=cache_hit),
        trust_provider=object(),
        trust_policy=object(),
        trust_service=SimpleNamespace(is_loaded=True, cache={1: object()}),
        readiness=lambda: (True, [], "api-test-graph"),
    )
    return TestClient(create_app(settings=settings, runtime=runtime)), runtime


def test_recommendations_validate_transport_limits_and_do_not_expose_raw_candidates():
    client, runtime = _client()
    response = client.post("/v1/recommendations", json={"user_id": 1, "top_k": 2})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": 1,
        "recommendations": [
            {
                "candidate_id": 9,
                "score": 0.9,
                "rank": 1,
                "eligibility": "ELIGIBLE",
                "risk_score": 0.1,
                "trust_score": 90.0,
                "reason_code": "OK",
            }
        ],
        "graph_version": "api-test-graph",
        "trust_version": "csv-without-manifest",
        "trust_policy_version": "phase06-fail-safe-v1",
        "raw_cache_hit": False,
    }
    assert runtime.engine.calls[0][2]["top_m"] == 3
    assert runtime.engine.calls[0][2]["trust_provider"] is runtime.trust_provider
    assert client.post("/v1/recommendations", json={"user_id": -1, "top_k": 1}).status_code == 422
    assert client.post("/v1/recommendations", json={"user_id": 1, "top_k": 0}).status_code == 422
    assert client.post("/v1/recommendations", json={"user_id": 1, "top_k": 4}).status_code == 422


@pytest.mark.parametrize("cache_hit", [False, True])
def test_response_reports_raw_cache_state_but_never_a_safe_cache(cache_hit):
    client, runtime = _client(cache_hit=cache_hit)

    response = client.post("/v1/recommendations", json={"user_id": 1, "top_k": 1})

    assert response.status_code == 200
    assert response.json()["raw_cache_hit"] is cache_hit
    assert len(runtime.engine.calls) == 1


def test_health_live_ready_and_metrics_contract():
    client, _ = _client()

    assert client.get("/health/live").json() == {"status": "live"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["graph_version"] == "api-test-graph"
    client.post("/v1/recommendations", json={"user_id": 1, "top_k": 1})
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "recommendation_requests_total" in metrics.text
    assert "trust_latency_seconds" in metrics.text
    assert "active_graph_version_info" in metrics.text


def test_not_ready_prevents_recommendation():
    client, runtime = _client()
    runtime.readiness = lambda: (False, ["trust_runtime_unavailable"], "api-test-graph")

    response = client.post("/v1/recommendations", json={"user_id": 1, "top_k": 1})

    assert response.status_code == 503
    assert response.json()["detail"] == "service not ready"


def test_unknown_user_is_a_clear_not_found_response():
    client, runtime = _client()
    runtime.engine = _UnknownUserEngine()

    response = client.post("/v1/recommendations", json={"user_id": 999999, "top_k": 1})

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown user_id"


def test_csv_runtime_is_explicit_default_and_mock_is_never_a_production_default():
    runtime = build_runtime(ApiSettings(environment="test", max_top_k=2, raw_top_m=2))

    assert runtime.settings.trust_provider == "csv"
    assert runtime.trust_service is not None
    assert runtime.trust_service.is_loaded is True
    assert runtime.settings.trust_version == "unversioned-csv-no-manifest"
    mock_runtime = build_runtime(
        ApiSettings(environment="test", trust_provider="mock", max_top_k=2, raw_top_m=2)
    )
    assert mock_runtime.settings.trust_provider == "mock"
    assert mock_runtime.trust_service is None
    with pytest.raises(ValueError, match="production requires"):
        ApiSettings(environment="production", trust_provider="mock")


@pytest.mark.parametrize("trust_provider", ["mock", "allow-all"])
def test_fake_trust_provider_is_not_ready_outside_test_mode(trust_provider):
    settings = ApiSettings(
        environment="development",
        trust_provider=trust_provider,
        max_top_k=2,
        raw_top_m=2,
    )
    client = TestClient(create_app(settings=settings, runtime=build_runtime(settings)))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert "non_test_trust_provider" in response.json()["reasons"]


@pytest.mark.parametrize("trust_provider", ["mock", "allow-all"])
def test_fake_trust_provider_can_be_ready_only_in_test_mode(trust_provider):
    settings = ApiSettings(
        environment="test",
        trust_provider=trust_provider,
        max_top_k=2,
        raw_top_m=2,
    )
    client = TestClient(create_app(settings=settings, runtime=build_runtime(settings)))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_cors_rejects_wildcard_credentials_combination():
    with pytest.raises(ValueError, match="wildcard"):
        ApiSettings(cors_origins=("*",), cors_allow_credentials=True)
