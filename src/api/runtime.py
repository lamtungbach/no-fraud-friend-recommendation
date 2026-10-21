"""Composition root for API dependencies; no route owns core construction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.api.config import ApiSettings
from src.api.observability import ObservedTrustEligibilityProvider
from src.data.adapters import MGTABAdapter
from src.pipeline import (
    ActiveIndexHolder,
    BatchOrchestrator,
    GraphIndexReadyConsumer,
    GraphIndexReadyEvent,
    InMemoryEventPublisher,
    LocalDatasetJobService,
    PostgresMetadataRepository,
    ServingIndexReloader,
)
from src.ranking import RankingConfig
from src.serving import (
    ActiveGraphRegistry,
    AllowAllTrustProvider,
    ArtifactStore,
    LocalArtifactStore,
    MockTrustProvider,
    NoOpRecommendationCache,
    PathEvidenceConfig,
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
    active_index_holder: ActiveIndexHolder
    graph_index_consumer: GraphIndexReadyConsumer
    graph_index_reloader: ServingIndexReloader
    trust_error: str | None = None
    active_index_error: str | None = None
    dataset_job_service: LocalDatasetJobService | None = None

    def warm_active_index(self) -> None:
        """Hydrate the in-memory serving snapshot from the durable registry."""

        graph_version = self.active_registry.get_active_version()
        if graph_version is None:
            return
        self.graph_index_reloader.warm_active_version(graph_version)
        self.active_index_error = None

    def consume_graph_index_ready(self, event: GraphIndexReadyEvent) -> bool:
        """Entry point for a broker adapter to safely apply one lifecycle event."""

        return self.graph_index_consumer.consume(event)

    def set_active_version_provider(
        self, active_version_provider: Callable[[], str | None] | None
    ) -> None:
        """Bind the metadata authority used to reject stale broker events."""

        self.graph_index_consumer = GraphIndexReadyConsumer(
            self.graph_index_reloader.reload,
            active_version_provider=active_version_provider,
        )

    def retry_pending_dataset_events(self) -> int:
        """Retry durable local outbox records after process startup."""

        if self.dataset_job_service is None:
            return 0
        return self.dataset_job_service.retry_pending_events()

    def shutdown(self) -> None:
        if self.dataset_job_service is not None:
            self.dataset_job_service.shutdown()

    def readiness(self) -> tuple[bool, list[str], str | None]:
        """Validate the active artifact/index and Trust runtime at request time."""

        reasons: list[str] = []
        graph_version: str | None = None
        try:
            graph_version = self.active_registry.get_active_version()
            if graph_version is None and not _allows_graphless_test_runtime(self.settings):
                reasons.append("active_graph_missing")
            else:
                bundle = self.active_index_holder.get()
                if bundle is None or bundle.graph_version != graph_version:
                    self.artifact_store.validate_version(graph_version)
                    if self.active_index_holder.get() is None:
                        reasons.append("active_index_unavailable")
        except (OSError, RuntimeError, TypeError, ValueError):
            if not _allows_graphless_test_runtime(self.settings):
                reasons.append("active_graph_invalid")
        if self.active_index_error:
            reasons.append("active_index_invalid")
        # Mock and allow-all exist only for explicit test injection. A local
        # developer may construct them, but readiness must never advertise
        # such a process as safe to an operator or deployment controller.
        if self.settings.trust_provider != "csv" and self.settings.environment != "test":
            reasons.append("non_test_trust_provider")
        if (
            self.settings.trust_provider == "csv"
            and (self.trust_error or self.trust_service is None or not self.trust_service.is_loaded)
        ):
            reasons.append("trust_runtime_unavailable")
        return not reasons, reasons, graph_version


def build_runtime(
    settings: ApiSettings | None = None,
    *,
    active_version_provider: Callable[[], str | None] | None = None,
) -> ApiRuntime:
    settings = settings or ApiSettings.from_environment()
    store = LocalArtifactStore(Path(settings.artifact_root))
    registry = ActiveGraphRegistry(store, Path(settings.registry_root))
    cache = _build_cache(settings)
    holder = ActiveIndexHolder()
    reloader = ServingIndexReloader(store, holder, registry=registry)
    engine = RecommendationEngine(
        store,
        registry,
        ranking_config=RankingConfig(top_m=settings.raw_top_m),
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        active_bundle_getter=holder.get,
        path_evidence_config=PathEvidenceConfig(
            max_sampled_paths=settings.path_evidence_max_paths,
            first_hop_scan_cap=settings.path_evidence_scan_cap,
        ),
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
            # Keep liveness available, but readiness and requests fail closed.
            trust_error = type(error).__name__
            provider = _UnavailableTrustProvider()
    elif settings.trust_provider == "mock":
        provider = MockTrustProvider()
    else:
        provider = AllowAllTrustProvider()
    runtime = ApiRuntime(
        settings=settings,
        artifact_store=store,
        active_registry=registry,
        cache=cache,
        engine=engine,
        trust_service=service,
        trust_provider=ObservedTrustEligibilityProvider(provider),
        trust_policy=policy,
        active_index_holder=holder,
        graph_index_consumer=GraphIndexReadyConsumer(
            reloader.reload,
            active_version_provider=active_version_provider,
        ),
        graph_index_reloader=reloader,
        trust_error=trust_error,
    )
    if settings.phase08_admin_enabled:
        runtime.dataset_job_service = _build_dataset_job_service(settings, runtime)
    try:
        runtime.warm_active_index()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        # Preserve liveness and make readiness fail rather than silently serving
        # a registry pointer whose index could not be loaded.
        runtime.active_index_error = type(error).__name__
    return runtime


def _build_dataset_job_service(settings: ApiSettings, runtime: ApiRuntime) -> LocalDatasetJobService:
    """Compose the opt-in local admin path with persistent metadata/outbox."""

    if settings.postgres_dsn is None:  # guarded by ApiSettings, defensive for injected settings
        raise ValueError("POSTGRES_DSN is required for Phase 08 dataset jobs")
    metadata = PostgresMetadataRepository.from_dsn(settings.postgres_dsn)
    # PostgreSQL is the lifecycle authority.  The in-process reloader refuses
    # an event that no longer matches the durable active version.
    runtime.set_active_version_provider(metadata.active_version)
    publisher = InMemoryEventPublisher()
    publisher.subscribe(runtime.consume_graph_index_ready)
    orchestrator = BatchOrchestrator(metadata, runtime.artifact_store, publisher)
    return LocalDatasetJobService(
        orchestrator,
        {"mgtab": lambda: MGTABAdapter(settings.mgtab_dataset_dir)},
    )


def _build_cache(settings: ApiSettings) -> RecommendationCache:
    if not settings.redis_url:
        return NoOpRecommendationCache()
    return RedisRecommendationCache(settings.redis_url)


def _allows_graphless_test_runtime(settings: ApiSettings) -> bool:
    """Permit explicit fake Trust providers in isolated HTTP contract tests."""

    return settings.environment == "test" and settings.trust_provider in {"mock", "allow-all"}


class _UnavailableTrustProvider:
    def batch_check(self, user_id, candidate_ids, *, pymk_scores=None):
        del user_id, candidate_ids, pymk_scores
        raise RuntimeError("Trust runtime is unavailable")
