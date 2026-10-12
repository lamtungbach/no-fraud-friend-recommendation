"""Small, storage-neutral records used by the Phase 08 lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    PERSISTING = "PERSISTING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    source_identity: str
    created_at: datetime


@dataclass(frozen=True)
class PipelineJob:
    job_id: str
    dataset_id: str
    graph_version: str
    graph_semantics: str
    build_config: Mapping[str, object]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


@dataclass(frozen=True)
class GraphVersionRecord:
    graph_version: str
    dataset_id: str
    job_id: str
    graph_semantics: str
    node_count: int
    edge_count: int
    artifact_location: str
    checksum: str
    build_config: Mapping[str, object]
    created_at: datetime
    activated_at: datetime | None = None


@dataclass(frozen=True)
class OutboxRecord:
    event_id: str
    graph_version: str
    payload: Mapping[str, object]
    created_at: datetime
    published_at: datetime | None = None
