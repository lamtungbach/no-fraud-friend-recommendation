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
    "ArtifactBundle",
    "ArtifactStore",
    "CacheUnavailableError",
    "InMemoryRecommendationCache",
    "LatencyBreakdown",
    "LocalArtifactStore",
    "NoOpRecommendationCache",
    "Recommendation",
    "RecommendationCache",
    "RecommendationEngine",
    "RecommendationResult",
    "RedisRecommendationCache",
    "ServingGraphIndex",
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
