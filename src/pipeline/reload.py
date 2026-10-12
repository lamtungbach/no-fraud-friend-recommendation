"""Safe serving reload: validate, warm, then atomically exchange in-memory index."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime

from src.serving.active_registry import ActiveGraphRegistry
from src.serving.artifact_store import ArtifactBundle, ArtifactStore

from .events import GraphIndexReadyEvent
from .observability import GRAPH_INDEX_RELOADS


class ActiveIndexHolder:
    def __init__(self, initial: ArtifactBundle | None = None):
        self._lock = threading.RLock()
        self._bundle = initial
        self._last_event_at: datetime | None = None

    def get(self) -> ArtifactBundle | None:
        with self._lock:
            return self._bundle

    def swap(self, bundle: ArtifactBundle) -> None:
        with self._lock:
            self._bundle = bundle

    def swap_if_newer(
        self,
        bundle: ArtifactBundle,
        event_created_at: datetime,
        *,
        before_swap: Callable[[], None],
    ) -> bool:
        """Prevent a late, distinct event from replacing a newer loaded index."""

        timestamp = event_created_at.astimezone(UTC)
        with self._lock:
            if self._last_event_at is not None and timestamp <= self._last_event_at:
                return False
            before_swap()
            self._bundle = bundle
            self._last_event_at = timestamp
            return True


class ServingIndexReloader:
    def __init__(
        self,
        store: ArtifactStore,
        holder: ActiveIndexHolder,
        *,
        registry: ActiveGraphRegistry | None = None,
    ):
        self._store = store
        self._holder = holder
        self._registry = registry

    def warm_active_version(self, graph_version: str) -> None:
        """Load a validated persisted pointer during API startup."""

        bundle = self._load_and_warm(graph_version, checksum=None)
        self._holder.swap(bundle)

    def reload(self, event: GraphIndexReadyEvent) -> bool:
        try:
            bundle = self._load_and_warm(event.version, checksum=event.checksum)
            swapped = self._holder.swap_if_newer(
                bundle,
                event.created_at,
                before_swap=self._activate_registry(event.version),
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            GRAPH_INDEX_RELOADS.labels(outcome="failure").inc()
            raise
        GRAPH_INDEX_RELOADS.labels(outcome="success" if swapped else "stale").inc()
        return swapped

    def _activate_registry(self, graph_version: str) -> Callable[[], None]:
        if self._registry is None:
            return lambda: None
        return lambda: self._registry.activate(graph_version)

    def _load_and_warm(self, graph_version: str, *, checksum: str | None) -> ArtifactBundle:
        bundle = self._store.load_version(graph_version)  # validates checksums + schema
        manifest = bundle.manifest
        if checksum is not None and manifest.get("checksum") != checksum:
            raise ValueError("event checksum does not match artifact")
        if str(manifest.get("graph_version")) != graph_version:
            raise ValueError("event version does not match artifact")
        # Warm/smoke before a visible swap. This never logs graph IDs or adjacency.
        if bundle.serving_index.num_nodes() > 0:
            node = bundle.graph_view.node_ids[0].item()
            bundle.serving_index.degree(node)
            bundle.serving_index.neighbors(node)
        return bundle
