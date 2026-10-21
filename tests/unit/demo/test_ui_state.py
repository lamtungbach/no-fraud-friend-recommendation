from __future__ import annotations

from demo.api_client import RecommendationResult
from demo.ui_state import (
    begin_recommendation_request,
    raw_cache_label,
    recommendation_snapshot,
    store_recommendation_result,
)


def _result(user_id: int, *, cache_hit: bool) -> RecommendationResult:
    return RecommendationResult(
        user_id=user_id,
        recommendations=[],
        graph_version="graph-v1",
        trust_version="trust-v1",
        trust_policy_version="policy-v1",
        raw_cache_hit=cache_hit,
    )


def _rendered_cache_labels(state: dict[str, object]) -> tuple[str, str]:
    """The health strip and Safe results must use this exact same snapshot."""
    snapshot = recommendation_snapshot(state)
    return raw_cache_label(snapshot), raw_cache_label(snapshot)


def test_miss_then_hit_uses_one_snapshot_for_health_and_safe_results():
    state: dict[str, object] = {}

    begin_recommendation_request(state)
    assert _rendered_cache_labels(state) == ("N/A", "N/A")

    store_recommendation_result(state, _result(11, cache_hit=False), 12.5)
    assert _rendered_cache_labels(state) == ("MISS", "MISS")

    begin_recommendation_request(state)
    store_recommendation_result(state, _result(11, cache_hit=True), 4.0)
    assert _rendered_cache_labels(state) == ("HIT", "HIT")


def test_switching_user_clears_old_cache_status_until_new_response_commits():
    state: dict[str, object] = {}

    store_recommendation_result(state, _result(13, cache_hit=True), 5.0)
    assert _rendered_cache_labels(state) == ("HIT", "HIT")

    begin_recommendation_request(state)
    assert "recommendation" not in state
    assert _rendered_cache_labels(state) == ("N/A", "N/A")

    store_recommendation_result(state, _result(11, cache_hit=False), 17.0)
    current = state["recommendation"]
    assert isinstance(current, RecommendationResult)
    assert current.user_id == 11
    assert _rendered_cache_labels(state) == ("MISS", "MISS")

    begin_recommendation_request(state)
    store_recommendation_result(state, _result(11, cache_hit=True), 3.0)
    assert _rendered_cache_labels(state) == ("HIT", "HIT")
