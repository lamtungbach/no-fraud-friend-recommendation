"""Metadata-only repositories for graph lifecycle state.

The PostgreSQL implementation persists no adjacency or tensor payload.  Tests
use :class:`InMemoryMetadataRepository` by explicit injection; production code
must explicitly construct ``PostgresMetadataRepository``.
"""

from __future__ import annotations

import json
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from .models import (
    DatasetRecord,
    GraphVersionRecord,
    JobStatus,
    OutboxRecord,
    PipelineJob,
)

_ALLOWED_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.VALIDATING, JobStatus.FAILED},
    JobStatus.VALIDATING: {JobStatus.PERSISTING, JobStatus.FAILED},
    JobStatus.PERSISTING: {JobStatus.READY, JobStatus.FAILED},
    JobStatus.READY: set(),
    JobStatus.FAILED: set(),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _safe_error(error: BaseException) -> str:
    """Store a stable code only; exception text may include private raw input."""

    return type(error).__name__


class MetadataRepository(ABC):
    """State required to resume publishing after a successful activation."""

    @abstractmethod
    def create_dataset(
        self, dataset_id: str, source_identity: str
    ) -> DatasetRecord: ...

    @abstractmethod
    def create_job(
        self,
        dataset_id: str,
        graph_version: str,
        graph_semantics: str,
        build_config: Mapping[str, object],
    ) -> PipelineJob: ...

    @abstractmethod
    def get_job(self, job_id: str) -> PipelineJob | None: ...

    @abstractmethod
    def claim_job(self, job_id: str) -> PipelineJob: ...

    @abstractmethod
    def transition_job(
        self, job_id: str, status: JobStatus, *, error: BaseException | None = None
    ) -> PipelineJob: ...

    @abstractmethod
    def record_graph_version(self, version: GraphVersionRecord) -> None: ...

    @abstractmethod
    def activate_version(self, graph_version: str, event: OutboxRecord) -> None: ...

    @abstractmethod
    def pending_events(self) -> tuple[OutboxRecord, ...]: ...

    @abstractmethod
    def mark_event_published(self, event_id: str) -> None: ...

    @abstractmethod
    def active_version(self) -> str | None: ...


class InMemoryMetadataRepository(MetadataRepository):
    """Thread-safe test double.  It is never selected implicitly by production."""

    def __init__(self):
        self._lock = threading.RLock()
        self.datasets: dict[str, DatasetRecord] = {}
        self.jobs: dict[str, PipelineJob] = {}
        self.versions: dict[str, GraphVersionRecord] = {}
        self.events: dict[str, OutboxRecord] = {}
        self._active_version: str | None = None

    def create_dataset(self, dataset_id: str, source_identity: str) -> DatasetRecord:
        if not dataset_id or not source_identity:
            raise ValueError("dataset_id and source_identity are required")
        with self._lock:
            existing = self.datasets.get(dataset_id)
            if existing:
                if existing.source_identity != source_identity:
                    raise ValueError("dataset_id already belongs to another source")
                return existing
            value = DatasetRecord(dataset_id, source_identity, _utcnow())
            self.datasets[dataset_id] = value
            return value

    def create_job(
        self, dataset_id, graph_version, graph_semantics, build_config
    ) -> PipelineJob:
        if graph_semantics not in {"directed", "mutual"}:
            raise ValueError("graph_semantics must be directed or mutual")
        with self._lock:
            if dataset_id not in self.datasets:
                raise KeyError("dataset must be created before its job")
            if graph_version in self.versions or any(
                item.graph_version == graph_version for item in self.jobs.values()
            ):
                raise ValueError("graph_version is already registered")
            now = _utcnow()
            job = PipelineJob(
                uuid.uuid4().hex,
                dataset_id,
                graph_version,
                graph_semantics,
                dict(build_config),
                JobStatus.PENDING,
                now,
                now,
            )
            self.jobs[job.job_id] = job
            return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        with self._lock:
            return self.jobs.get(job_id)

    def claim_job(self, job_id: str) -> PipelineJob:
        """Atomically assign a pending job to exactly one worker."""

        with self._lock:
            current = self.jobs.get(job_id)
            if current is None:
                raise KeyError(job_id)
            if current.status is not JobStatus.PENDING:
                raise JobAlreadyClaimedError(job_id, current.status)
            updated = PipelineJob(
                **{
                    **current.__dict__,
                    "status": JobStatus.RUNNING,
                    "updated_at": _utcnow(),
                }
            )
            self.jobs[job_id] = updated
            return updated

    def transition_job(self, job_id, status, *, error=None) -> PipelineJob:
        with self._lock:
            current = self.jobs[job_id]
            if status not in _ALLOWED_TRANSITIONS[current.status]:
                raise ValueError(f"invalid job transition {current.status} -> {status}")
            if status is JobStatus.FAILED and error is None:
                raise ValueError("FAILED requires an error")
            if status is not JobStatus.FAILED and error is not None:
                raise ValueError("only FAILED may include an error")
            updated = PipelineJob(
                **{
                    **current.__dict__,
                    "status": status,
                    "updated_at": _utcnow(),
                    "error_code": _safe_error(error) if error else None,
                }
            )
            self.jobs[job_id] = updated
            return updated

    def record_graph_version(self, version: GraphVersionRecord) -> None:
        with self._lock:
            job = self.jobs.get(version.job_id)
            if job is None or job.status is not JobStatus.PERSISTING:
                raise ValueError("graph metadata may only be recorded while PERSISTING")
            if (
                version.graph_version != job.graph_version
                or version.dataset_id != job.dataset_id
            ):
                raise ValueError("graph metadata does not match its job")
            if version.graph_version in self.versions:
                raise ValueError("graph version is immutable")
            self.versions[version.graph_version] = version

    def activate_version(self, graph_version: str, event: OutboxRecord) -> None:
        with self._lock:
            version = self.versions.get(graph_version)
            if version is None:
                raise KeyError("graph version metadata is missing")
            job = self.jobs[version.job_id]
            if job.status is not JobStatus.PERSISTING:
                raise ValueError("only a persisting job may activate a graph")
            if event.graph_version != graph_version or event.event_id in self.events:
                raise ValueError("outbox event is invalid or already exists")
            # One lock constitutes one transaction: old active pointer remains
            # untouched unless both the new pointer and durable outbox are stored.
            now = _utcnow()
            self._active_version = graph_version
            self.versions[graph_version] = GraphVersionRecord(
                **{**version.__dict__, "activated_at": now}
            )
            self.events[event.event_id] = event
            self.jobs[job.job_id] = PipelineJob(
                **{**job.__dict__, "status": JobStatus.READY, "updated_at": now}
            )

    def pending_events(self) -> tuple[OutboxRecord, ...]:
        with self._lock:
            return tuple(
                item for item in self.events.values() if item.published_at is None
            )

    def mark_event_published(self, event_id: str) -> None:
        with self._lock:
            event = self.events[event_id]
            if event.published_at is None:
                self.events[event_id] = OutboxRecord(
                    **{**event.__dict__, "published_at": _utcnow()}
                )

    def active_version(self) -> str | None:
        with self._lock:
            return self._active_version


class PostgresMetadataRepository(MetadataRepository):
    """PostgreSQL metadata adapter using DB-API connections and transactions.

    Apply ``migrations/0001_phase08_metadata.sql`` before constructing this
    class. ``connection_factory`` is injectable for integration tests.
    """

    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str) -> PostgresMetadataRepository:
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - depends on deployment extra
            raise RuntimeError("PostgreSQL requires the psycopg package") from error
        return cls(lambda: psycopg.connect(dsn))

    def _execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
        *,
        fetchone=False,
        fetchall=False,
    ):
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            result = (
                cursor.fetchone()
                if fetchone
                else cursor.fetchall()
                if fetchall
                else None
            )
            connection.commit()
            return result

    def create_dataset(self, dataset_id, source_identity):
        row = self._execute(
            """INSERT INTO datasets(dataset_id, source_identity) VALUES (%s, %s)
            ON CONFLICT (dataset_id) DO UPDATE SET dataset_id = EXCLUDED.dataset_id
            RETURNING dataset_id, source_identity, created_at""",
            (dataset_id, source_identity),
            fetchone=True,
        )
        if row[1] != source_identity:
            raise ValueError("dataset_id already belongs to another source")
        return DatasetRecord(*row)

    def create_job(self, dataset_id, graph_version, graph_semantics, build_config):
        job_id, now = uuid.uuid4().hex, _utcnow()
        row = self._execute(
            """INSERT INTO pipeline_jobs(job_id, dataset_id, graph_version, graph_semantics, build_config, status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING job_id,dataset_id,graph_version,graph_semantics,build_config,status,created_at,updated_at,error_code""",
            (
                job_id,
                dataset_id,
                graph_version,
                graph_semantics,
                json.dumps(dict(build_config)),
                JobStatus.PENDING,
                now,
                now,
            ),
            fetchone=True,
        )
        return self._job(row)

    def get_job(self, job_id):
        row = self._execute(
            "SELECT job_id,dataset_id,graph_version,graph_semantics,build_config,status,created_at,updated_at,error_code FROM pipeline_jobs WHERE job_id=%s",
            (job_id,),
            fetchone=True,
        )
        return self._job(row) if row else None

    def claim_job(self, job_id):
        now = _utcnow()
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE pipeline_jobs SET status=%s,updated_at=%s WHERE job_id=%s AND status=%s
                RETURNING job_id,dataset_id,graph_version,graph_semantics,build_config,status,created_at,updated_at,error_code""",
                (JobStatus.RUNNING, now, job_id, JobStatus.PENDING),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT status FROM pipeline_jobs WHERE job_id=%s", (job_id,))
                existing = cursor.fetchone()
                if existing is None:
                    raise KeyError(job_id)
                raise JobAlreadyClaimedError(job_id, JobStatus(existing[0]))
            connection.commit()
            return self._job(row)

    def transition_job(self, job_id, status, *, error=None):
        expected = _predecessor_statuses(status)
        error_code = _safe_error(error) if error else None
        if len(expected) == 1:
            query = """UPDATE pipeline_jobs SET status=%s,error_code=%s,updated_at=%s
                WHERE job_id=%s AND status=%s
                RETURNING job_id,dataset_id,graph_version,graph_semantics,build_config,status,created_at,updated_at,error_code"""
        else:
            query = """UPDATE pipeline_jobs SET status=%s,error_code=%s,updated_at=%s
                WHERE job_id=%s AND status IN (%s,%s,%s,%s)
                RETURNING job_id,dataset_id,graph_version,graph_semantics,build_config,status,created_at,updated_at,error_code"""
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                query,
                (status, error_code, _utcnow(), job_id, *expected),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT status FROM pipeline_jobs WHERE job_id=%s", (job_id,))
                existing = cursor.fetchone()
                if existing is None:
                    raise KeyError(job_id)
                raise ValueError(f"invalid job transition {existing[0]} -> {status}")
            connection.commit()
            return self._job(row)

    def record_graph_version(self, version):
        self._execute(
            """INSERT INTO graph_versions(graph_version,dataset_id,job_id,graph_semantics,node_count,edge_count,artifact_location,checksum,build_config,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                version.graph_version,
                version.dataset_id,
                version.job_id,
                version.graph_semantics,
                version.node_count,
                version.edge_count,
                version.artifact_location,
                version.checksum,
                json.dumps(dict(version.build_config)),
                version.created_at,
            ),
        )

    def activate_version(self, graph_version, event):
        # Active pointer and outbox are committed together; failed publication
        # is retried later from graph_index_outbox.
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT job_id FROM graph_versions WHERE graph_version=%s FOR UPDATE",
                (graph_version,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError("graph version metadata is missing")
            now = _utcnow()
            cursor.execute(
                "UPDATE active_versions SET graph_version=%s, activated_at=%s WHERE singleton=true",
                (graph_version, now),
            )
            cursor.execute(
                "UPDATE graph_versions SET activated_at=%s WHERE graph_version=%s",
                (now, graph_version),
            )
            cursor.execute(
                "UPDATE pipeline_jobs SET status=%s,updated_at=%s WHERE job_id=%s AND status=%s",
                (JobStatus.READY, now, row[0], JobStatus.PERSISTING),
            )
            if cursor.rowcount != 1:
                raise ValueError("only a persisting job may activate a graph")
            cursor.execute(
                "INSERT INTO graph_index_outbox(event_id,graph_version,payload,created_at) VALUES (%s,%s,%s,%s)",
                (
                    event.event_id,
                    graph_version,
                    json.dumps(dict(event.payload)),
                    event.created_at,
                ),
            )
            connection.commit()

    def pending_events(self):
        rows = self._execute(
            "SELECT event_id,graph_version,payload,created_at,published_at FROM graph_index_outbox WHERE published_at IS NULL ORDER BY created_at",
            fetchall=True,
        )
        return tuple(
            OutboxRecord(
                row[0],
                row[1],
                row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                row[3],
                row[4],
            )
            for row in rows
        )

    def mark_event_published(self, event_id):
        self._execute(
            "UPDATE graph_index_outbox SET published_at=%s WHERE event_id=%s AND published_at IS NULL",
            (_utcnow(), event_id),
        )

    def active_version(self):
        row = self._execute(
            "SELECT graph_version FROM active_versions WHERE singleton=true",
            fetchone=True,
        )
        return row[0] if row and row[0] else None

    @staticmethod
    def _job(row: tuple[object, ...]) -> PipelineJob:
        build_config = row[4] if isinstance(row[4], dict) else json.loads(row[4])
        return PipelineJob(*row[:4], build_config, JobStatus(row[5]), *row[6:])


class JobAlreadyClaimedError(RuntimeError):
    """A non-owner worker attempted to execute a job already claimed elsewhere."""

    def __init__(self, job_id: str, status: JobStatus):
        super().__init__(f"job is not pending: {job_id}")
        self.job_id = job_id
        self.status = status


def _predecessor_statuses(status: JobStatus) -> tuple[JobStatus, ...]:
    return tuple(
        current for current, allowed in _ALLOWED_TRANSITIONS.items() if status in allowed
    )
