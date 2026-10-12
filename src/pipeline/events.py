"""Transport-neutral graph-index-ready contract and idempotent consumer."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class GraphIndexReadyEvent:
    event_id: str
    version: str
    created_at: datetime
    artifact_location: str
    checksum: str
    artifact_metadata: Mapping[str, object]
    event_type: str = "graph-index-ready"

    def payload(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "version": self.version,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "artifact_location": self.artifact_location,
            "checksum": self.checksum,
            "artifact_metadata": dict(self.artifact_metadata),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> GraphIndexReadyEvent:
        required = {
            "event_id",
            "event_type",
            "version",
            "created_at",
            "artifact_location",
            "checksum",
            "artifact_metadata",
        }
        if set(payload) != required or payload["event_type"] != "graph-index-ready":
            raise ValueError("invalid graph-index-ready event")
        if not all(
            isinstance(payload[key], str) and payload[key]
            for key in required - {"artifact_metadata"}
        ):
            raise ValueError("event scalar fields must be non-empty strings")
        if not isinstance(payload["artifact_metadata"], Mapping):
            raise TypeError("artifact_metadata must be an object")
        return cls(
            str(payload["event_id"]),
            str(payload["version"]),
            datetime.fromisoformat(str(payload["created_at"])),
            str(payload["artifact_location"]),
            str(payload["checksum"]),
            dict(payload["artifact_metadata"]),
        )


class EventPublisher:
    def publish(self, event: GraphIndexReadyEvent) -> None:
        raise NotImplementedError


class InMemoryEventPublisher(EventPublisher):
    """Explicit test/local adapter.  It accepts at-least-once delivery."""

    def __init__(self):
        self.events: list[GraphIndexReadyEvent] = []
        self.fail_next = False
        self._subscribers: list[Callable[[GraphIndexReadyEvent], object]] = []

    def subscribe(self, consumer: Callable[[GraphIndexReadyEvent], object]) -> None:
        """Attach an explicit local/test consumer; production uses a broker adapter."""

        self._subscribers.append(consumer)

    def publish(self, event):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("event backend unavailable")
        self.events.append(event)
        for consumer in self._subscribers:
            consumer(event)


class GraphIndexReadyConsumer:
    """Deduplicates events only after the reload handler fully succeeds."""

    def __init__(
        self,
        reload_handler: Callable[[GraphIndexReadyEvent], object],
        *,
        active_version_provider: Callable[[], str | None] | None = None,
    ):
        self._reload_handler = reload_handler
        self._active_version_provider = active_version_provider
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def consume(self, event: GraphIndexReadyEvent) -> bool:
        with self._lock:
            if event.event_id in self._seen:
                return False
            if (
                self._active_version_provider is not None
                and self._active_version_provider() != event.version
            ):
                self._seen.add(event.event_id)
                return False
            applied = self._reload_handler(event)
            self._seen.add(event.event_id)
            return bool(applied) if isinstance(applied, bool) else True
