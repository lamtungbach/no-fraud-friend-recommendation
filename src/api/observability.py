"""Bounded-cardinality metrics and logging helpers for Phase 07."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Hashable, Mapping, Sequence

from prometheus_client import Counter, Gauge, Histogram

from src.serving.trust_boundary import TrustBatchResult, TrustEligibilityProvider

LOGGER = logging.getLogger("safe_recommendations")

RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total", "Recommendation requests", ("outcome",)
)
RECOMMENDATION_LATENCY = Histogram(
    "recommendation_latency_seconds", "End-to-end safe recommendation latency"
)
RAW_CACHE = Counter("recommendation_raw_cache_total", "Raw PYMK cache outcomes", ("result",))
RETRIEVAL_CANDIDATES = Histogram(
    "retrieval_candidates_count", "Raw candidates retrieved before Trust"
)
RETRIEVAL_TRUNCATED = Counter("retrieval_truncated_total", "Truncated retrievals")
TRUST_LATENCY = Histogram("trust_latency_seconds", "Trust provider latency")
TRUST_ERRORS = Counter("trust_errors_total", "Trust provider errors")
ACTIVE_GRAPH = Gauge(
    "active_graph_version_info", "Active graph artifact version", ("graph_version",)
)


class ObservedTrustEligibilityProvider:
    """Measure the provider fault boundary without changing Trust semantics."""

    def __init__(self, provider: TrustEligibilityProvider):
        self._provider = provider

    def batch_check(
        self,
        user_id: Hashable,
        candidate_ids: Sequence[Hashable],
        *,
        pymk_scores: Mapping[Hashable, float] | None = None,
    ) -> TrustBatchResult:
        started = time.perf_counter()
        try:
            return self._provider.batch_check(user_id, candidate_ids, pymk_scores=pymk_scores)
        except Exception:
            TRUST_ERRORS.inc()
            raise
        finally:
            TRUST_LATENCY.observe(time.perf_counter() - started)


def record_recommendation(result: object, elapsed_seconds: float) -> None:
    """Record metadata available at the transport boundary, never user IDs."""

    RECOMMENDATION_REQUESTS.labels(outcome="success").inc()
    RECOMMENDATION_LATENCY.observe(elapsed_seconds)
    RAW_CACHE.labels(result="hit" if result.raw_cache_hit else "miss").inc()
    ACTIVE_GRAPH.labels(graph_version=result.graph_version).set(1)
    RETRIEVAL_CANDIDATES.observe(result.raw_candidate_count)
    if result.retrieval_truncated:
        RETRIEVAL_TRUNCATED.inc()
    LOGGER.info(
        "%s",
        json.dumps(
            {
                "event": "safe_recommendation_served",
                "graph_version": result.graph_version,
                "trust_version": result.trust_version,
                "raw_cache_hit": result.raw_cache_hit,
                "recommendation_count": len(result.recommendations),
            },
            sort_keys=True,
        ),
    )


def record_recommendation_error() -> None:
    RECOMMENDATION_REQUESTS.labels(outcome="error").inc()
    LOGGER.warning('%s', json.dumps({"event": "safe_recommendation_error"}, sort_keys=True))
