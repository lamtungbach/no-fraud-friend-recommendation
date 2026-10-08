"""Transport-independent raw PYMK recommendation orchestration."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Hashable
from dataclasses import asdict, dataclass, replace

from src.ranking import RankedCandidate, RankingConfig, rank_topology_candidates
from src.retrieval import (
    RetrievalConfig,
    RetrievalStats,
    retrieve_bounded_two_hop_candidates,
)
from src.serving.active_registry import ActiveGraphRegistry
from src.serving.artifact_store import ArtifactStore
from src.serving.recommendation_cache import (
    CacheUnavailableError,
    NoOpRecommendationCache,
    RecommendationCache,
)

_CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Recommendation:
    """One raw PYMK candidate in deterministic final-rank order."""

    candidate_id: Hashable
    score: float
    rank: int


@dataclass(frozen=True)
class LatencyBreakdown:
    """Per-request timings collected at the engine boundary in milliseconds."""

    cache_ms: float
    retrieval_ms: float
    scoring_ms: float
    total_ms: float


@dataclass(frozen=True)
class RecommendationResult:
    """Domain result that contains no HTTP, FastAPI, or Trust/Fraud concerns."""

    user_id: Hashable
    recommendations: tuple[Recommendation, ...]
    graph_version: str
    ranking_method: str
    retrieval_config_hash: str
    ranking_config_hash: str
    cache_hit: bool
    retrieval_stats: RetrievalStats | None
    latency: LatencyBreakdown


class RecommendationEngine:
    """Resolve an active graph, retrieve, rank, and cache raw PYMK Top-M.

    Cache entries contain graph and immutable configuration identities.  An
    active-version switch naturally uses different keys, leaving old entries to
    expire rather than deleting global Redis state.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore,
        active_registry: ActiveGraphRegistry,
        *,
        retrieval_config: RetrievalConfig | None = None,
        ranking_config: RankingConfig | None = None,
        cache: RecommendationCache | None = None,
        cache_ttl_seconds: float = 300.0,
    ):
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._artifact_store = artifact_store
        self._active_registry = active_registry
        self._retrieval_config = retrieval_config or RetrievalConfig()
        self._ranking_config = ranking_config or RankingConfig()
        self._cache = cache or NoOpRecommendationCache()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._retrieval_config_hash = self._config_hash(asdict(self._retrieval_config))

    def recommend(
        self,
        user_id: Hashable,
        top_k: int,
        *,
        top_m: int | None = None,
    ) -> RecommendationResult:
        """Return up to ``top_k`` deterministic raw PYMK recommendations.

        ``top_m`` controls the cacheable raw result size.  If omitted, the
        configured Top-M is raised to ``top_k`` when necessary so a caller can
        always receive the requested number when enough candidates exist.
        """

        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        effective_top_m = self._effective_top_m(top_k, top_m)
        effective_ranking = replace(self._ranking_config, top_m=effective_top_m)
        ranking_config_hash = self._config_hash(asdict(effective_ranking))
        started_at = time.perf_counter()

        graph_version = self._active_registry.get_active_version()
        if graph_version is None:
            raise RuntimeError("No active graph version is registered")
        cache_key = self.build_cache_key(
            graph_version,
            user_id,
            effective_top_m,
            ranking_config_hash=ranking_config_hash,
        )

        cache_started_at = time.perf_counter()
        cached_payload = self._cache_get(cache_key)
        cached_recommendations = self._decode_cache_payload(
            cached_payload,
            graph_version=graph_version,
            user_id=user_id,
            top_m=effective_top_m,
            ranking_method=effective_ranking.ranking_method,
            ranking_config_hash=ranking_config_hash,
        )
        cache_elapsed_ms = self._elapsed_ms(cache_started_at)
        if cached_recommendations is not None:
            return RecommendationResult(
                user_id=user_id,
                recommendations=cached_recommendations[:top_k],
                graph_version=graph_version,
                ranking_method=effective_ranking.ranking_method,
                retrieval_config_hash=self._retrieval_config_hash,
                ranking_config_hash=ranking_config_hash,
                cache_hit=True,
                retrieval_stats=None,
                latency=LatencyBreakdown(
                    cache_ms=cache_elapsed_ms,
                    retrieval_ms=0.0,
                    scoring_ms=0.0,
                    total_ms=self._elapsed_ms(started_at),
                ),
            )

        bundle = self._artifact_store.load_version(graph_version)
        retrieval_started_at = time.perf_counter()
        retrieval = retrieve_bounded_two_hop_candidates(
            user_id, bundle.serving_index, self._retrieval_config
        )
        retrieval_elapsed_ms = self._elapsed_ms(retrieval_started_at)

        scoring_started_at = time.perf_counter()
        ranked = rank_topology_candidates(
            user_id, retrieval.candidate_ids, bundle.serving_index, effective_ranking
        )
        recommendations = self._to_recommendations(ranked)
        scoring_elapsed_ms = self._elapsed_ms(scoring_started_at)

        cache_write_started_at = time.perf_counter()
        payload = self._encode_cache_payload(
            recommendations,
            graph_version=graph_version,
            user_id=user_id,
            top_m=effective_top_m,
            ranking_method=effective_ranking.ranking_method,
            ranking_config_hash=ranking_config_hash,
        )
        self._cache_set(cache_key, payload)
        cache_elapsed_ms += self._elapsed_ms(cache_write_started_at)
        return RecommendationResult(
            user_id=user_id,
            recommendations=recommendations[:top_k],
            graph_version=graph_version,
            ranking_method=effective_ranking.ranking_method,
            retrieval_config_hash=self._retrieval_config_hash,
            ranking_config_hash=ranking_config_hash,
            cache_hit=False,
            retrieval_stats=retrieval.stats,
            latency=LatencyBreakdown(
                cache_ms=cache_elapsed_ms,
                retrieval_ms=retrieval_elapsed_ms,
                scoring_ms=scoring_elapsed_ms,
                total_ms=self._elapsed_ms(started_at),
            ),
        )

    def build_cache_key(
        self,
        graph_version: str,
        user_id: Hashable,
        top_m: int,
        *,
        ranking_config_hash: str | None = None,
    ) -> str:
        """Build the version/config/user-specific raw PYMK Top-M cache key."""

        if top_m < 0:
            raise ValueError("top_m must be non-negative")
        try:
            user_token = json.dumps(user_id, sort_keys=True, separators=(",", ":"))
        except TypeError as error:
            raise ValueError("user_id must be JSON-serializable for cache identity") from error
        ranking_hash = ranking_config_hash or self._config_hash(
            asdict(replace(self._ranking_config, top_m=top_m))
        )
        return (
            f"pymk:{graph_version}:{self._retrieval_config_hash}:{ranking_hash}:"
            f"{user_token}:topm:{top_m}"
        )

    def _effective_top_m(self, top_k: int, top_m: int | None) -> int:
        if top_m is None:
            return max(top_k, self._ranking_config.top_m)
        if top_m < top_k:
            raise ValueError("top_m must be greater than or equal to top_k")
        return top_m

    def _cache_get(self, cache_key: str) -> str | None:
        try:
            return self._cache.get(cache_key)
        except CacheUnavailableError:
            return None

    def _cache_set(self, cache_key: str, payload: str) -> None:
        try:
            self._cache.set(cache_key, payload, self._cache_ttl_seconds)
        except CacheUnavailableError:
            pass

    def _encode_cache_payload(
        self,
        recommendations: tuple[Recommendation, ...],
        *,
        graph_version: str,
        user_id: Hashable,
        top_m: int,
        ranking_method: str,
        ranking_config_hash: str,
    ) -> str:
        value = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "graph_version": graph_version,
            "retrieval_config_hash": self._retrieval_config_hash,
            "ranking_config_hash": ranking_config_hash,
            "user_id": user_id,
            "top_m": top_m,
            "ranking_method": ranking_method,
            "recommendations": [
                {
                    "candidate_id": recommendation.candidate_id,
                    "score": recommendation.score,
                    "rank": recommendation.rank,
                }
                for recommendation in recommendations
            ],
        }
        try:
            return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Recommendations must be safely JSON-serializable") from error

    def _decode_cache_payload(
        self,
        payload: str | None,
        *,
        graph_version: str,
        user_id: Hashable,
        top_m: int,
        ranking_method: str,
        ranking_config_hash: str,
    ) -> tuple[Recommendation, ...] | None:
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        expected = {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "graph_version": graph_version,
            "retrieval_config_hash": self._retrieval_config_hash,
            "ranking_config_hash": ranking_config_hash,
            "user_id": user_id,
            "top_m": top_m,
            "ranking_method": ranking_method,
        }
        if any(value.get(key) != expected_value for key, expected_value in expected.items()):
            return None
        raw_recommendations = value.get("recommendations")
        if not isinstance(raw_recommendations, list) or len(raw_recommendations) > top_m:
            return None
        recommendations: list[Recommendation] = []
        for expected_rank, raw in enumerate(raw_recommendations, start=1):
            if not isinstance(raw, dict):
                return None
            candidate_id = raw.get("candidate_id")
            rank = raw.get("rank")
            score = raw.get("score")
            if isinstance(rank, bool) or not isinstance(rank, int) or rank != expected_rank:
                return None
            try:
                hash(candidate_id)
                score_value = float(score)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(score_value):
                return None
            recommendations.append(
                Recommendation(candidate_id=candidate_id, score=score_value, rank=rank)
            )
        return tuple(recommendations)

    @staticmethod
    def _config_hash(config: dict[str, object]) -> str:
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_recommendations(ranked: tuple[RankedCandidate, ...]) -> tuple[Recommendation, ...]:
        return tuple(
            Recommendation(candidate_id=item.candidate_id, score=item.score, rank=rank)
            for rank, item in enumerate(ranked, start=1)
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (time.perf_counter() - started_at) * 1000.0
