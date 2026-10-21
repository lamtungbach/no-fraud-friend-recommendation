from __future__ import annotations

import pytest

from scripts.demo_preflight import (
    PreflightError,
    validate_live,
    validate_ready,
    validate_recommendation,
)


def test_preflight_accepts_the_safe_serving_contract():
    validate_live({"status": "live"})
    graph_version, max_top_k = validate_ready(
        {"status": "ready", "graph_version": "demo-v1", "max_top_k": 10, "reasons": []}
    )
    count = validate_recommendation(
        {
            "user_id": 0,
            "recommendations": [
                {"candidate_id": 4, "rank": 2, "score": 0.9, "eligibility": "ELIGIBLE"}
            ],
            "graph_version": "demo-v1",
            "trust_version": "trust-v1",
            "trust_policy_version": "policy-v1",
            "raw_cache_hit": False,
        },
        graph_version=graph_version,
        top_k=5,
    )

    assert max_top_k == 10
    assert count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "not_ready", "graph_version": "demo-v1", "max_top_k": 10, "reasons": ["trust"]},
        {"status": "ready", "graph_version": "", "max_top_k": 10},
        {"status": "ready", "graph_version": "demo-v1", "max_top_k": 0},
    ],
)
def test_preflight_rejects_unready_or_incomplete_readiness(payload):
    with pytest.raises(PreflightError):
        validate_ready(payload)


def test_preflight_rejects_raw_or_non_safe_response():
    response = {
        "user_id": 0,
        "recommendations": [{"candidate_id": 4, "rank": 1, "eligibility": "BLOCKED"}],
        "graph_version": "demo-v1",
        "trust_version": "trust-v1",
        "trust_policy_version": "policy-v1",
        "raw_cache_hit": False,
        "raw_candidates": [{"candidate_id": 99}],
    }

    with pytest.raises(PreflightError):
        validate_recommendation(response, graph_version="demo-v1", top_k=5)
