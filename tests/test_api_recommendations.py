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


class _DetailedSafeEngine(_SafeEngine):
    def __init__(self):
        super().__init__()
        self.detail_calls = []

    def recommend_safe_details(self, user_id, top_k, **kwargs):
        self.detail_calls.append((user_id, top_k, kwargs))
        safe_result = self.recommend_safe(user_id, top_k, **kwargs)
        return SimpleNamespace(
            safe_result=safe_result,
            diagnostics=SimpleNamespace(
                graph_version="api-test-graph",
                requested_top_k=top_k,
                raw_top_m=kwargs["top_m"],
                raw_cache_hit=False,
                stage_execution="computed",
                first_hop_seen=2,
                first_hop_used=2,
                first_hop_capped=False,
                second_hop_expansions=3,
                second_hop_seen=3,
                second_hop_used=3,
                second_hop_capped=False,
                unique_candidates=2,
                candidates_returned=2,
                candidate_capped=False,
                excluded_self=0,
                excluded_existing_connection=0,
                duplicate_candidates=0,
                retrieval_truncated=False,
                scored_candidates=2,
                raw_ranked_count=2,
                returned_safe_count=1,
                first_hop_cap=None,
                second_hop_cap=None,
                candidate_cap=None,
                cache_lookup_ms=0.1,
                retrieval_ms=0.2,
                scoring_ms=0.3,
                total_backend_ms=1.0,
            ),
            explanations=(
                SimpleNamespace(
                    candidate_id=9,
                    rank=1,
                    score=0.9,
                    graph_version="api-test-graph",
                    graph_semantics="directed",
                    ranking_method="cn",
                    common_neighbors=2.0,
                    adamic_adar=1.0,
                    jaccard=0.5,
                    preferential_attachment=4.0,
                    note="Topology signals describe the active graph only; Trust eligibility is a separate gate.",
                ),
            ),
            path_summaries=(
                SimpleNamespace(
                    candidate_id=9,
                    graph_version="api-test-graph",
                    graph_semantics="directed",
                    path_count_total=2,
                    path_count_observed=2,
                    sampled_path_count=2,
                    scan_truncated=False,
                    truncated=False,
                    edge_type_evidence_available=False,
                    note="Paths are aggregate directed graph evidence only; intermediate node IDs and edge types are not public.",
                ),
            ),
            empty_result_context=None,
        )


class _EmptyDetailedSafeEngine(_DetailedSafeEngine):
    def recommend_safe(self, user_id, top_k, **kwargs):
        del top_k, kwargs
        return SafeRecommendationResult(
            user_id=user_id,
            recommendations=(),
            graph_version="api-test-graph",
            trust_version="mock-v1",
            trust_policy_version="phase06-fail-safe-v1",
            raw_cache_hit=False,
            raw_candidate_count=2,
        )

    def recommend_safe_details(self, user_id, top_k, **kwargs):
        details = super().recommend_safe_details(user_id, top_k, **kwargs)
        details.empty_result_context = SimpleNamespace(
            status="SAFE_RESULT_EMPTY_UNSPECIFIED",
            graph_version="api-test-graph",
            evidence="Raw PYMK candidates existed, but none were returned by the unchanged Trust policy.",
        )
        return details


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


def test_opt_in_pymk_details_are_explicit_safe_and_aggregate_only():
    client, runtime = _client()
    runtime.engine = _DetailedSafeEngine()

    response = client.post(
        "/v1/recommendations",
        json={
            "user_id": 1,
            "top_k": 1,
            "include_diagnostics": True,
            "include_explanations": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["diagnostics"]["stage_execution"] == "computed"
    assert payload["diagnostics"]["raw_ranked_count"] == 2
    assert payload["explanations"][0]["candidate_id"] == 9
    assert payload["explanations"][0]["ranking_method"] == "cn"
    assert "raw_candidates" not in payload
    assert "via_node_id" not in payload["explanations"][0]
    assert runtime.engine.detail_calls[0][2]["include_explanations"] is True


def test_p1_path_summaries_are_opt_in_and_do_not_expose_intermediate_ids():
    client, runtime = _client()
    runtime.engine = _DetailedSafeEngine()

    response = client.post(
        "/v1/recommendations",
        json={"user_id": 1, "top_k": 1, "include_path_summaries": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["path_summaries"] == [
        {
            "candidate_id": 9,
            "graph_version": "api-test-graph",
            "graph_semantics": "directed",
            "path_count_total": 2,
            "path_count_observed": 2,
            "sampled_path_count": 2,
            "scan_truncated": False,
            "truncated": False,
            "edge_type_evidence_available": False,
            "note": "Paths are aggregate directed graph evidence only; intermediate node IDs and edge types are not public.",
        }
    ]
    assert "via_node_id" not in payload["path_summaries"][0]
    assert "raw_candidates" not in payload
    assert runtime.engine.detail_calls[0][2]["include_path_summaries"] is True


def test_p1_empty_result_context_is_opt_in_and_neutral():
    client, runtime = _client()
    runtime.engine = _EmptyDetailedSafeEngine()

    response = client.post(
        "/v1/recommendations",
        json={"user_id": 1, "top_k": 1, "include_empty_result_context": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"] == []
    assert payload["empty_result_context"] == {
        "status": "SAFE_RESULT_EMPTY_UNSPECIFIED",
        "graph_version": "api-test-graph",
        "evidence": "Raw PYMK candidates existed, but none were returned by the unchanged Trust policy.",
    }
    assert "TRUST_BLOCKED" not in str(payload["empty_result_context"])


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
