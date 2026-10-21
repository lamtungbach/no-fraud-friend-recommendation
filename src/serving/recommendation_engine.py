"""Transport-independent raw PYMK recommendation orchestration."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Hashable
from dataclasses import asdict, dataclass, replace
from typing import TYPE_CHECKING

from src.ranking import (
    RankedCandidate,
    RankingConfig,
    rank_topology_candidates,
    score_topology_candidates,
)
from src.retrieval import (
    RetrievalConfig,
    RetrievalStats,
    retrieve_bounded_two_hop_candidates,
)
from src.serving.active_registry import ActiveGraphRegistry
from src.serving.artifact_store import ArtifactBundle, ArtifactStore
from src.serving.recommendation_cache import (
    CacheUnavailableError,
    NoOpRecommendationCache,
    RecommendationCache,
)

_CACHE_SCHEMA_VERSION = 1

if TYPE_CHECKING:
    from src.serving.trust_boundary import (
        SafeRecommendationResult,
        TrustEligibilityProvider,
        TrustPolicy,
    )


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
    cache_lookup_ms: float | None = None
    cache_write_ms: float | None = None


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
    scored_candidates: int | None = None


@dataclass(frozen=True)
class RetrievalRankingDiagnostics:
    """Aggregate evidence from raw PYMK stages for one safe request.

    Cache hits leave retrieval/scoring fields as ``None`` because those stages
    did not execute for the request. This DTO never contains raw candidate IDs
    or Trust decisions.
    """

    graph_version: str
    requested_top_k: int
    raw_top_m: int
    raw_cache_hit: bool
    stage_execution: str
    first_hop_seen: int | None
    first_hop_used: int | None
    first_hop_capped: bool | None
    second_hop_expansions: int | None
    second_hop_seen: int | None
    second_hop_used: int | None
    second_hop_capped: bool | None
    unique_candidates: int | None
    candidates_returned: int | None
    candidate_capped: bool | None
    excluded_self: int | None
    excluded_existing_connection: int | None
    duplicate_candidates: int | None
    retrieval_truncated: bool | None
    scored_candidates: int | None
    raw_ranked_count: int
    returned_safe_count: int
    first_hop_cap: int | None
    second_hop_cap: int | None
    candidate_cap: int | None
    cache_lookup_ms: float
    retrieval_ms: float | None
    scoring_ms: float | None
    total_backend_ms: float


@dataclass(frozen=True)
class PYMKRecommendationExplanation:
    """Topology-only evidence for a candidate already admitted to Safe Top-K."""

    candidate_id: Hashable
    rank: int
    score: float
    graph_version: str
    graph_semantics: str
    ranking_method: str
    common_neighbors: float
    adamic_adar: float
    jaccard: float
    preferential_attachment: float
    note: str = (
        "Topology signals describe the active graph only; Trust eligibility is a separate gate."
    )


@dataclass(frozen=True)
class PathEvidenceConfig:
    """Bounded public aggregate evidence for one Safe two-hop candidate."""

    max_sampled_paths: int = 5
    first_hop_scan_cap: int = 250

    def __post_init__(self) -> None:
        if not 1 <= self.max_sampled_paths <= 10:
            raise ValueError("max_sampled_paths must be between 1 and 10")
        if self.first_hop_scan_cap < self.max_sampled_paths:
            raise ValueError("first_hop_scan_cap must be at least max_sampled_paths")


@dataclass(frozen=True)
class SafeTwoHopPathSummary:
    """Aggregate path evidence for a Safe candidate; never contains via-node IDs."""

    candidate_id: Hashable
    graph_version: str
    graph_semantics: str
    path_count_total: int | None
    path_count_observed: int
    sampled_path_count: int
    scan_truncated: bool
    truncated: bool
    edge_type_evidence_available: bool = False
    note: str = (
        "Paths are aggregate directed graph evidence only; intermediate node IDs and edge types are not public."
    )


@dataclass(frozen=True)
class EmptyResultContext:
    """Evidence-backed neutral classification for an empty Safe Top-K result."""

    status: str
    graph_version: str
    evidence: str


@dataclass(frozen=True)
class SafeRecommendationDetails:
    """Optional PYMK-only detail produced after the unchanged Trust merge."""

    safe_result: SafeRecommendationResult
    diagnostics: RetrievalRankingDiagnostics
    explanations: tuple[PYMKRecommendationExplanation, ...]
    path_summaries: tuple[SafeTwoHopPathSummary, ...] = ()
    empty_result_context: EmptyResultContext | None = None


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
        active_bundle_getter: Callable[[], ArtifactBundle | None] | None = None,
        path_evidence_config: PathEvidenceConfig | None = None,
    ):
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._artifact_store = artifact_store
        self._active_registry = active_registry
        self._retrieval_config = retrieval_config or RetrievalConfig()
        self._ranking_config = ranking_config or RankingConfig()
        self._cache = cache or NoOpRecommendationCache()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._active_bundle_getter = active_bundle_getter
        self._path_evidence_config = path_evidence_config or PathEvidenceConfig()
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

        active_bundle = self._active_bundle_getter() if self._active_bundle_getter else None
        graph_version = (
            active_bundle.graph_version
            if active_bundle is not None
            else self._active_registry.get_active_version()
        )
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
                    cache_lookup_ms=cache_elapsed_ms,
                ),
            )

        bundle = active_bundle or self._artifact_store.load_version(graph_version)
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
        cache_write_elapsed_ms = self._elapsed_ms(cache_write_started_at)
        cache_elapsed_ms += cache_write_elapsed_ms
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
                cache_lookup_ms=cache_elapsed_ms - cache_write_elapsed_ms,
                cache_write_ms=cache_write_elapsed_ms,
            ),
            scored_candidates=len(retrieval.candidate_ids),
        )

    def recommend_safe(
        self,
        user_id: Hashable,
        top_k: int,
        *,
        trust_provider: TrustEligibilityProvider,
        trust_policy: TrustPolicy | None = None,
        top_m: int | None = None,
    ) -> SafeRecommendationResult:
        """Derive uncached Safe Top-K from cached-or-computed raw PYMK Top-M.

        ``recommend`` remains the Phase-05 raw boundary. This method deliberately
        requests the full Top-M from it, then performs Trust merging in memory; no
        Safe Top-K payload is ever written to the recommendation cache.
        """
        from src.serving.trust_boundary import SafeTopKMerger

        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        effective_top_m = self._effective_top_m(top_k, top_m)
        raw_result = self.recommend(
            user_id,
            top_k=effective_top_m,
            top_m=effective_top_m,
        )
        return SafeTopKMerger(trust_policy).merge(raw_result, top_k, trust_provider)

    def recommend_safe_details(
        self,
        user_id: Hashable,
        top_k: int,
        *,
        trust_provider: TrustEligibilityProvider,
        trust_policy: TrustPolicy | None = None,
        top_m: int | None = None,
        include_explanations: bool = False,
        include_path_summaries: bool = False,
        include_empty_result_context: bool = False,
    ) -> SafeRecommendationDetails:
        """Return opt-in aggregate diagnostics and Safe Top-K explanations.

        Trust is still invoked for every request, including raw-cache hits. The
        extra topology calculation runs only when explanations are requested
        and only for candidates already admitted to Safe Top-K.
        """

        from src.serving.trust_boundary import SafeTopKMerger

        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        started_at = time.perf_counter()
        effective_top_m = self._effective_top_m(top_k, top_m)
        raw_result = self.recommend(
            user_id,
            top_k=effective_top_m,
            top_m=effective_top_m,
        )
        safe_result = SafeTopKMerger(trust_policy).merge(
            raw_result, top_k, trust_provider
        )
        explanations = (
            self._explain_safe_recommendations(raw_result, safe_result)
            if include_explanations
            else ()
        )
        path_summaries = (
            self._summarize_safe_two_hop_paths(raw_result, safe_result)
            if include_path_summaries
            else ()
        )
        empty_result_context = (
            self._classify_empty_safe_result(raw_result, safe_result)
            if include_empty_result_context
            else None
        )
        diagnostics = self._build_diagnostics(
            raw_result,
            safe_result,
            requested_top_k=top_k,
            raw_top_m=effective_top_m,
            total_backend_ms=self._elapsed_ms(started_at),
        )
        return SafeRecommendationDetails(
            safe_result,
            diagnostics,
            explanations,
            path_summaries,
            empty_result_context,
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

    def _explain_safe_recommendations(
        self,
        raw_result: RecommendationResult,
        safe_result: SafeRecommendationResult,
    ) -> tuple[PYMKRecommendationExplanation, ...]:
        """Compute actual topology features against the exact raw graph version."""

        if not safe_result.recommendations:
            return ()
        bundle = self._bundle_for_version(raw_result.graph_version)
        candidate_ids = [item.candidate_id for item in safe_result.recommendations]
        scores = score_topology_candidates(
            raw_result.user_id, candidate_ids, bundle.serving_index
        )
        graph_semantics = str(bundle.manifest.get("graph_semantics", "unknown"))
        return tuple(
            PYMKRecommendationExplanation(
                candidate_id=item.candidate_id,
                rank=item.rank,
                score=item.score,
                graph_version=raw_result.graph_version,
                graph_semantics=graph_semantics,
                ranking_method=raw_result.ranking_method,
                common_neighbors=scores[item.candidate_id].common_neighbors,
                adamic_adar=scores[item.candidate_id].adamic_adar,
                jaccard=scores[item.candidate_id].jaccard,
                preferential_attachment=scores[item.candidate_id].preferential_attachment,
            )
            for item in safe_result.recommendations
        )

    def _bundle_for_version(self, graph_version: str) -> ArtifactBundle:
        active_bundle = self._active_bundle_getter() if self._active_bundle_getter else None
        if active_bundle is not None and active_bundle.graph_version == graph_version:
            return active_bundle
        # Immutable artifacts let an explanation remain pinned to the exact
        # snapshot that produced the raw result even after an active-version swap.
        return self._artifact_store.load_version(graph_version)

    def _summarize_safe_two_hop_paths(
        self,
        raw_result: RecommendationResult,
        safe_result: SafeRecommendationResult,
    ) -> tuple[SafeTwoHopPathSummary, ...]:
        """Return bounded aggregate ``user -> middle -> candidate`` evidence.

        The public endpoint deliberately omits middle-node IDs.  Counting uses
        the exact immutable graph snapshot that supplied the raw result; the
        configurable first-hop scan cap prevents a high-degree query node from
        creating unbounded optional-debug work.
        """

        if not safe_result.recommendations:
            return ()
        bundle = self._bundle_for_version(raw_result.graph_version)
        graph = bundle.serving_index
        all_first_hops = graph.neighbors(raw_result.user_id)
        scan_cap = self._path_evidence_config.first_hop_scan_cap
        scanned_first_hops = all_first_hops[:scan_cap]
        scan_truncated = len(all_first_hops) > len(scanned_first_hops)
        graph_semantics = str(bundle.manifest["graph_semantics"])
        max_sampled_paths = self._path_evidence_config.max_sampled_paths

        summaries: list[SafeTwoHopPathSummary] = []
        for item in safe_result.recommendations:
            observed_count = sum(
                graph.has_edge(middle_id, item.candidate_id)
                for middle_id in scanned_first_hops
            )
            summaries.append(
                SafeTwoHopPathSummary(
                    candidate_id=item.candidate_id,
                    graph_version=raw_result.graph_version,
                    graph_semantics=graph_semantics,
                    path_count_total=None if scan_truncated else observed_count,
                    path_count_observed=observed_count,
                    sampled_path_count=min(observed_count, max_sampled_paths),
                    scan_truncated=scan_truncated,
                    truncated=scan_truncated or observed_count > max_sampled_paths,
                )
            )
        return tuple(summaries)

    @staticmethod
    def _classify_empty_safe_result(
        raw_result: RecommendationResult,
        safe_result: SafeRecommendationResult,
    ) -> EmptyResultContext | None:
        """Classify only facts observable at the PYMK/Trust boundary.

        Unknown users remain an HTTP 404 before a result exists.  The method
        intentionally does not infer that Trust filtered every candidate unless
        the merger reports its explicit unavailable/fail-closed version.
        """

        if safe_result.recommendations:
            return None
        if safe_result.trust_version == "unavailable":
            return EmptyResultContext(
                status="TRUST_UNAVAILABLE_FAIL_CLOSED",
                graph_version=raw_result.graph_version,
                evidence="Trust provider raised an error and the existing policy failed closed.",
            )
        stats = raw_result.retrieval_stats
        if stats is None:
            return EmptyResultContext(
                status="EMPTY_RAW_RESULT_UNSPECIFIED",
                graph_version=raw_result.graph_version,
                evidence="Raw cache contained no ranked candidates; retrieval stages were not rerun.",
            )
        if stats.first_hop_seen == 0:
            return EmptyResultContext(
                status="ISOLATED_USER",
                graph_version=raw_result.graph_version,
                evidence="User exists in the serving index but has no retrieval-semantic neighbors.",
            )
        if stats.candidates_before_cap == 0:
            return EmptyResultContext(
                status="NO_TWO_HOP_CANDIDATES",
                graph_version=raw_result.graph_version,
                evidence="Bounded traversal completed without an eligible two-hop candidate.",
            )
        if not raw_result.recommendations:
            return EmptyResultContext(
                status="NO_RANKED_CANDIDATES",
                graph_version=raw_result.graph_version,
                evidence="Retrieval returned candidates but topology ranking produced no raw result.",
            )
        return EmptyResultContext(
            status="SAFE_RESULT_EMPTY_UNSPECIFIED",
            graph_version=raw_result.graph_version,
            evidence="Raw PYMK candidates existed, but none were returned by the unchanged Trust policy.",
        )

    def _build_diagnostics(
        self,
        raw_result: RecommendationResult,
        safe_result: SafeRecommendationResult,
        *,
        requested_top_k: int,
        raw_top_m: int,
        total_backend_ms: float,
    ) -> RetrievalRankingDiagnostics:
        stats = raw_result.retrieval_stats
        cache_hit = raw_result.cache_hit
        return RetrievalRankingDiagnostics(
            graph_version=raw_result.graph_version,
            requested_top_k=requested_top_k,
            raw_top_m=raw_top_m,
            raw_cache_hit=cache_hit,
            stage_execution="cache_hit" if cache_hit else "computed",
            first_hop_seen=stats.first_hop_seen if stats else None,
            first_hop_used=stats.first_hop_used if stats else None,
            first_hop_capped=stats.first_hop_capped if stats else None,
            second_hop_expansions=stats.second_hop_expansions if stats else None,
            second_hop_seen=stats.second_hop_seen if stats else None,
            second_hop_used=stats.second_hop_used if stats else None,
            second_hop_capped=stats.second_hop_capped if stats else None,
            unique_candidates=stats.candidates_before_cap if stats else None,
            candidates_returned=stats.candidates_returned if stats else None,
            candidate_capped=stats.candidate_capped if stats else None,
            excluded_self=stats.excluded_self if stats else None,
            excluded_existing_connection=(
                stats.excluded_existing_connection if stats else None
            ),
            duplicate_candidates=stats.duplicate_candidates if stats else None,
            retrieval_truncated=stats.truncated if stats else None,
            scored_candidates=raw_result.scored_candidates,
            raw_ranked_count=len(raw_result.recommendations),
            returned_safe_count=len(safe_result.recommendations),
            first_hop_cap=self._retrieval_config.first_hop_cap,
            second_hop_cap=self._retrieval_config.second_hop_cap,
            candidate_cap=self._retrieval_config.candidate_cap,
            cache_lookup_ms=raw_result.latency.cache_lookup_ms or raw_result.latency.cache_ms,
            retrieval_ms=None if cache_hit else raw_result.latency.retrieval_ms,
            scoring_ms=None if cache_hit else raw_result.latency.scoring_ms,
            total_backend_ms=total_backend_ms,
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return (time.perf_counter() - started_at) * 1000.0
