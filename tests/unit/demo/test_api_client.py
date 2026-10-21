from __future__ import annotations

import json

import httpx
import pytest

from demo.api_client import DemoApiError, PymkApiClient


def _client(handler) -> PymkApiClient:
    transport = httpx.MockTransport(handler)
    return PymkApiClient("http://backend.test/", client=httpx.Client(transport=transport))


def _recommendation_payload(**overrides):
    payload = {
        "user_id": 7,
        "recommendations": [
            {
                "candidate_id": 9,
                "score": 0.8,
                "rank": 1,
                "eligibility": "eligible",
            }
        ],
        "graph_version": "graph-v1",
        "trust_version": "trust-v1",
        "trust_policy_version": "policy-v1",
        "raw_cache_hit": False,
    }
    payload.update(overrides)
    return payload


def test_recommendation_request_is_safe_and_parses_actual_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/recommendations"
        assert json.loads(request.content) == {"user_id": 7, "top_k": 3}
        return httpx.Response(200, json=_recommendation_payload())

    client = _client(handler)
    result = client.recommend(7, 3)

    assert result.user_id == 7
    assert result.recommendations[0]["candidate_id"] == 9
    assert result.raw_cache_hit is False


def test_recommendation_opt_in_parses_p0_p1_evidence_without_raw_candidates():
    payload = _recommendation_payload(
        diagnostics={"stage_execution": "computed", "raw_ranked_count": 2},
        explanations=[{"candidate_id": 9, "ranking_method": "cn", "common_neighbors": 2.0}],
        path_summaries=[
            {
                "candidate_id": 9,
                "path_count_total": 2,
                "sampled_path_count": 2,
                "graph_semantics": "directed",
            }
        ],
        empty_result_context=None,
        raw_candidates=[{"candidate_id": 1234}],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "user_id": 7,
            "top_k": 3,
            "include_diagnostics": True,
            "include_explanations": True,
            "include_path_summaries": True,
            "include_empty_result_context": True,
        }
        return httpx.Response(200, json=payload)

    result = _client(handler).recommend(
        7,
        3,
        include_diagnostics=True,
        include_explanations=True,
        include_path_summaries=True,
        include_empty_result_context=True,
    )

    assert result.diagnostics == payload["diagnostics"]
    assert result.explanations == payload["explanations"]
    assert result.path_summaries == payload["path_summaries"]
    assert not hasattr(result, "raw_candidates")


def test_empty_safe_list_is_preserved_without_claiming_a_trust_reason():
    client = _client(
        lambda request: httpx.Response(200, json=_recommendation_payload(recommendations=[]))
    )

    result = client.recommend(7, 3)

    assert result.recommendations == []


def test_raw_unfiltered_candidates_are_not_exposed_by_demo_client():
    payload = _recommendation_payload(
        raw_candidates=[{"candidate_id": 1234}],
        recommendations=[
            {
                "candidate_id": 9,
                "score": 0.8,
                "rank": 1,
                "eligibility": "eligible",
                "unsafe_debug_field": "must-not-render",
            }
        ],
    )
    client = _client(lambda request: httpx.Response(200, json=payload))

    result = client.recommend(7, 3)

    assert not hasattr(result, "raw_candidates")
    assert result.recommendations == [
        {"candidate_id": 9, "score": 0.8, "rank": 1, "eligibility": "eligible"}
    ]


@pytest.mark.parametrize("user_id,top_k", [(-1, 1), (0, 0)])
def test_invalid_recommendation_input_does_not_send_request(user_id, top_k):
    client = _client(lambda request: pytest.fail("request should not be sent"))

    with pytest.raises(ValueError):
        client.recommend(user_id, top_k)


def test_timeout_is_reported_as_safe_ui_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("late", request=request)

    with pytest.raises(DemoApiError, match="quá thời gian"):
        _client(handler).live()


def test_unreachable_api_is_reported_as_safe_ui_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(DemoApiError, match="Không thể kết nối"):
        _client(handler).live()


def test_backend_error_and_missing_optional_item_fields_are_handled():
    error_client = _client(lambda request: httpx.Response(503, json={"detail": "not ready"}))
    with pytest.raises(DemoApiError, match="not ready") as failure:
        error_client.recommend(7, 3)
    assert failure.value.status_code == 503

    payload = _recommendation_payload(
        recommendations=[{"candidate_id": 9, "score": 0.8, "rank": 1, "eligibility": "eligible"}]
    )
    result = _client(lambda request: httpx.Response(200, json=payload)).recommend(7, 3)
    assert "risk_score" not in result.recommendations[0]


def test_invalid_response_is_not_rendered_as_a_recommendation():
    client = _client(lambda request: httpx.Response(200, json={"user_id": 7}))

    with pytest.raises(DemoApiError, match="thiếu trường"):
        client.recommend(7, 3)


def test_trust_profile_and_reasoning_use_existing_trust_api():
    profile = {
        "user_id": 7, "trust_score": 82.5, "p_bot": 0.12,
        "recommendation_tier": "TIER_1_VERIFIED_SAFE", "decision": "safe",
        "pillars": {"identity_auth": 0.9, "interaction_health": 0.8,
                    "network_hygiene": 0.7, "content_safety": 0.6},
    }
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/api/v1/trust/7"
            return httpx.Response(200, json=profile)
        assert request.url.path == "/api/v1/trust/reason"
        assert json.loads(request.content) == {"user_id": 7}
        return httpx.Response(200, json={"user_id": 7, "reasoning_trace": ["low risk"]})

    client = _client(handler)
    assert client.trust_profile(7) == profile
    assert client.trust_reasoning(7)["reasoning_trace"] == ["low risk"]


def test_trust_profile_rejects_bad_data_and_propagates_missing_user():
    malformed = {"user_id": 7, "trust_score": 99, "p_bot": 0.1,
                 "recommendation_tier": "tier", "decision": "ok", "pillars": {}}
    with pytest.raises(DemoApiError, match="định dạng"):
        _client(lambda request: httpx.Response(200, json=malformed)).trust_profile(7)
    with pytest.raises(DemoApiError) as failure:
        _client(lambda request: httpx.Response(404, json={"detail": "not found"})).trust_profile(7)
    assert failure.value.status_code == 404
