"""Ordered offline graph/index pipeline with transactional activation and outbox."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.data import DatasetAdapter
from src.graph import build_pymk_graph_view
from src.serving.artifact_store import ArtifactStore, LocalArtifactStore
from src.serving.graph_index import ServingGraphIndex

from .events import EventPublisher, GraphIndexReadyEvent
from .metadata import JobAlreadyClaimedError, MetadataRepository
from .models import GraphVersionRecord, JobStatus, OutboxRecord, PipelineJob
from .observability import PIPELINE_JOB_TRANSITIONS

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatasetJobRequest:
    dataset_id: str
    source_identity: str
    graph_version: str
    graph_semantics: str = "directed"
    build_config: Mapping[str, object] = field(default_factory=dict)


class BatchOrchestrator:
    """Build and activate only fully validated, immutable graph versions."""

    def __init__(
        self,
        metadata: MetadataRepository,
        artifacts: ArtifactStore,
        publisher: EventPublisher,
    ):
        self._metadata, self._artifacts, self._publisher = (
            metadata,
            artifacts,
            publisher,
        )

    def create_dataset_or_index_job(self, request: DatasetJobRequest) -> PipelineJob:
        self._metadata.create_dataset(request.dataset_id, request.source_identity)
        job = self._metadata.create_job(
            request.dataset_id,
            request.graph_version,
            request.graph_semantics,
            request.build_config,
        )
        LOGGER.info(
            "pipeline_job_created job_id=%s graph_version=%s",
            job.job_id,
            job.graph_version,
        )
        return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        return self._metadata.get_job(job_id)

    def run_job(self, job_id: str, adapter: DatasetAdapter) -> PipelineJob:
        try:
            job = self._metadata.claim_job(job_id)
        except JobAlreadyClaimedError:
            LOGGER.info("pipeline_job_already_claimed job_id=%s", job_id)
            raise
        PIPELINE_JOB_TRANSITIONS.labels(status=JobStatus.RUNNING).inc()
        LOGGER.info("pipeline_job_transition job_id=%s status=%s", job_id, JobStatus.RUNNING)
        try:
            graph = adapter.transform()
            self._transition(job_id, JobStatus.VALIDATING)
            adapter.validate(graph)
            view = build_pymk_graph_view(graph, mode=job.graph_semantics)
            index = ServingGraphIndex.from_graph_view(view)
            self._transition(job_id, JobStatus.PERSISTING)
            bundle = self._artifacts.save_version(
                job.graph_version,
                graph,
                view,
                index,
                dataset_id=job.dataset_id,
                build_config=job.build_config,
            )
            manifest = bundle.manifest
            version = GraphVersionRecord(
                graph_version=job.graph_version,
                dataset_id=job.dataset_id,
                job_id=job_id,
                graph_semantics=str(manifest["graph_semantics"]),
                node_count=int(manifest["num_nodes"]),
                edge_count=int(manifest["num_edges"]),
                artifact_location=self._artifact_location(job.graph_version),
                checksum=str(manifest["checksum"]),
                build_config=job.build_config,
                created_at=datetime.now(UTC),
            )
            self._metadata.record_graph_version(version)
            event = GraphIndexReadyEvent(
                uuid.uuid4().hex,
                job.graph_version,
                datetime.now(UTC),
                version.artifact_location,
                version.checksum,
                {
                    "graph_semantics": version.graph_semantics,
                    "node_count": version.node_count,
                    "edge_count": version.edge_count,
                },
            )
            self._metadata.activate_version(
                job.graph_version,
                OutboxRecord(
                    event.event_id, job.graph_version, event.payload(), event.created_at
                ),
            )
            # Local registry is a serving compatibility pointer.  Metadata is the
            # authority for lifecycle state; if this fails, retry/publish can resume.
            self.retry_pending_events()
            LOGGER.info(
                "pipeline_job_ready job_id=%s graph_version=%s",
                job_id,
                job.graph_version,
            )
            return self._require_job(job_id)
        except Exception as error:
            current = self._require_job(job_id)
            if current.status not in {JobStatus.READY, JobStatus.FAILED}:
                self._transition(job_id, JobStatus.FAILED, error=error)
            LOGGER.warning(
                "pipeline_job_failed job_id=%s error_type=%s",
                job_id,
                type(error).__name__,
            )
            raise

    def retry_pending_events(self) -> int:
        published = 0
        for record in self._metadata.pending_events():
            event = GraphIndexReadyEvent.from_payload(record.payload)
            try:
                self._publisher.publish(event)
            except (OSError, RuntimeError, TimeoutError, ValueError):
                LOGGER.warning(
                    "graph_index_event_publish_failed event_id=%s", event.event_id
                )
                continue
            self._metadata.mark_event_published(event.event_id)
            published += 1
        return published

    def _require_job(self, job_id: str) -> PipelineJob:
        job = self._metadata.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def _transition(
        self, job_id: str, status: JobStatus, *, error: BaseException | None = None
    ) -> PipelineJob:
        job = self._metadata.transition_job(job_id, status, error=error)
        PIPELINE_JOB_TRANSITIONS.labels(status=status).inc()
        LOGGER.info("pipeline_job_transition job_id=%s status=%s", job_id, status)
        return job

    def _artifact_location(self, graph_version: str) -> str:
        if isinstance(self._artifacts, LocalArtifactStore):
            return str(self._artifacts.version_path(graph_version))
        return f"graph/{graph_version}"
