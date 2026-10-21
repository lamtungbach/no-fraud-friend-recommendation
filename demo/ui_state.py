"""Small, testable session-state transitions for the Command Center."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from demo.api_client import RecommendationResult


def raw_cache_label(result: RecommendationResult | None) -> str:
    """Return a display label from one recommendation snapshot only."""
    if result is None:
        return "N/A"
    return "HIT" if result.raw_cache_hit else "MISS"


def recommendation_snapshot(state: Mapping[str, Any]) -> RecommendationResult | None:
    """Return the one completed response eligible for cache-status rendering."""
    result = state.get("recommendation")
    return result if isinstance(result, RecommendationResult) else None


def begin_recommendation_request(state: MutableMapping[str, Any]) -> None:
    """Remove prior result data before a different submitted request starts."""
    for key in ("recommendation", "recommendation_latency_ms", "selected_candidate_id"):
        state.pop(key, None)


def store_recommendation_result(
    state: MutableMapping[str, Any], result: RecommendationResult, latency_ms: float
) -> None:
    """Commit a completed response as the sole snapshot rendered by the UI."""
    state["recommendation"] = result
    state["recommendation_latency_ms"] = latency_ms
    state["recommendation_query_id"] = state.get("recommendation_query_id", 0) + 1
