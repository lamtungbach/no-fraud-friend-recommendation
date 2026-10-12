"""Serving-ready graph indexes."""

from .active_registry import ActiveGraphRegistry
from .artifact_store import ArtifactBundle, ArtifactStore, LocalArtifactStore
from .graph_index import ServingGraphIndex
from .recommendation_cache import (
    CacheUnavailableError,
    InMemoryRecommendationCache,
    NoOpRecommendationCache,
    RecommendationCache,
    RedisRecommendationCache,
)

__all__ = [
    "ActiveGraphRegistry",
    "AllowAllTrustProvider",
    "ArtifactBundle",
    "ArtifactStore",
    "CacheUnavailableError",
    "Eligibility",
    "InMemoryRecommendationCache",
    "LatencyBreakdown",
    "LocalArtifactStore",
    "MockTrustProvider",
    "MutualTier1CountProvider",
    "NoOpRecommendationCache",
    "Recommendation",
    "RecommendationCache",
    "RecommendationEngine",
    "RecommendationResult",
    "RedisRecommendationCache",
    "SafeRecommendation",
    "SafeRecommendationResult",
    "SafeTopKMerger",
    "ServingGraphIndex",
    "TrustAction",
    "TrustBatchResult",
    "TrustCandidateResult",
    "TrustEligibilityProvider",
    "TrustPolicy",
    "TrustProviderError",
    "TrustServiceEligibilityProvider",
]


def __getattr__(name: str):
    """Load engine-only exports lazily to avoid a graph/ranking import cycle."""

    engine_exports = {
        "LatencyBreakdown",
        "Recommendation",
        "RecommendationEngine",
        "RecommendationResult",
    }
    if name in engine_exports:
        from . import recommendation_engine

        return getattr(recommendation_engine, name)
    trust_exports = {
        "AllowAllTrustProvider",
        "Eligibility",
        "MockTrustProvider",
        "MutualTier1CountProvider",
        "SafeRecommendation",
        "SafeRecommendationResult",
        "SafeTopKMerger",
        "TrustAction",
        "TrustBatchResult",
        "TrustCandidateResult",
        "TrustEligibilityProvider",
        "TrustPolicy",
        "TrustProviderError",
        "TrustServiceEligibilityProvider",
    }
    if name in trust_exports:
        from . import trust_boundary

        return getattr(trust_boundary, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
