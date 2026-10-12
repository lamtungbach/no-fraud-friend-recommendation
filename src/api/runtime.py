"""Composition root for Phase 07 HTTP-serving dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.api.config import ApiSettings
from src.api.observability import ObservedTrustEligibilityProvider
from src.ranking import RankingConfig
from src.serving import (
    ActiveGraphRegistry,
    AllowAllTrustProvider,
    ArtifactStore,
    LocalArtifactStore,
    MockTrustProvider,
    NoOpRecommendationCache,
    RecommendationCache,
    RecommendationEngine,
    RedisRecommendationCache,
    TrustEligibilityProvider,
    TrustPolicy,
    TrustServiceEligibilityProvider,
)
from src.trust.service import TrustService


@dataclass
class ApiRuntime:
    settings: ApiSettings
    artifact_store: ArtifactStore
    active_registry: ActiveGraphRegistry
    cache: RecommendationCache
    engine: RecommendationEngine
    trust_service: TrustService | None
    trust_provider: TrustEligibilityProvider
    trust_policy: TrustPolicy
    trust_error: str | None = None

    def readiness(self) -> tuple[bool, list[str], str | None]:
        """Validate the active artifact/index and Trust runtime at request time."""

        reasons: list[str] = []
        graph_version: str | None = None
        try:
            graph_version = self.active_registry.get_active_version()
            if graph_version is None:
                reasons.append("active_graph_missing")
            else:
                self.artifact_store.validate_version(graph_version)
        except (OSError, RuntimeError, TypeError, ValueError):
            reasons.append("active_graph_invalid")
        if self.settings.trust_provider != "csv" and self.settings.environment != "test":
            reasons.append("non_test_trust_provider")
        if (
            self.settings.trust_provider == "csv"
            and (self.trust_error or self.trust_service is None or not self.trust_service.is_loaded)
        ):
            reasons.append("trust_runtime_unavailable")
        return not reasons, reasons, graph_version


def build_runtime(settings: ApiSettings | None = None) -> ApiRuntime:
    settings = settings or ApiSettings.from_environment()
    store = LocalArtifactStore(Path(settings.artifact_root))
    registry = ActiveGraphRegistry(store, Path(settings.registry_root))
    cache = _build_cache(settings)
    engine = RecommendationEngine(
        store,
        registry,
        ranking_config=RankingConfig(top_m=settings.raw_top_m),
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    policy = TrustPolicy()
    service: TrustService | None = None
    trust_error: str | None = None
    if settings.trust_provider == "csv":
        try:
            service = TrustService(profiles_path=settings.trust_profiles_path)
            if not service.is_loaded:
                service.load_profiles()
            provider: TrustEligibilityProvider = TrustServiceEligibilityProvider(
                service, trust_version=settings.trust_version
            )
        except (FileNotFoundError, OSError, ValueError) as error:
            trust_error = type(error).__name__
            provider = _UnavailableTrustProvider()
    elif settings.trust_provider == "mock":
        provider = MockTrustProvider()
    else:
        provider = AllowAllTrustProvider()
    return ApiRuntime(
        settings=settings,
        artifact_store=store,
        active_registry=registry,
        cache=cache,
        engine=engine,
        trust_service=service,
        trust_provider=ObservedTrustEligibilityProvider(provider),
        trust_policy=policy,
        trust_error=trust_error,
    )


def _build_cache(settings: ApiSettings) -> RecommendationCache:
    if not settings.redis_url:
        return NoOpRecommendationCache()
    return RedisRecommendationCache(settings.redis_url)


class _UnavailableTrustProvider:
    def batch_check(self, user_id, candidate_ids, *, pymk_scores=None):
        del user_id, candidate_ids, pymk_scores
        raise RuntimeError("Trust runtime is unavailable")
