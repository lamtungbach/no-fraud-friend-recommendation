"""Opt-in smoke test for a migrated PostgreSQL metadata database."""

from __future__ import annotations

import os
import uuid

import pytest
import torch

from src.data import CanonicalGraph, DatasetAdapter
from src.pipeline import (
    BatchOrchestrator,
    DatasetJobRequest,
    InMemoryEventPublisher,
    JobAlreadyClaimedError,
    JobStatus,
    PostgresMetadataRepository,
)
from src.serving import LocalArtifactStore

if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(
        reason="set RUN_POSTGRES_INTEGRATION=1 and POSTGRES_DSN after applying the Phase 08 migration"
    )


def test_postgres_metadata_job_round_trip():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN is not configured")
    pytest.importorskip("psycopg")
    repository = PostgresMetadataRepository.from_dsn(dsn)
    suffix = uuid.uuid4().hex
    dataset_id = f"phase08-it-{suffix}"
    graph_version = f"phase08-it-{suffix}"

    repository.create_dataset(dataset_id, "integration:synthetic")
    job = repository.create_job(dataset_id, graph_version, "directed", {"test": True})
    updated = repository.transition_job(job.job_id, JobStatus.RUNNING)

    assert updated.status is JobStatus.RUNNING
    assert repository.get_job(job.job_id).graph_version == graph_version


class _TinyGraphAdapter(DatasetAdapter):
    """No raw-data logging; sufficient topology for a two-hop artifact smoke test."""

    def load_raw(self):
        return None

    def transform(self) -> CanonicalGraph:
        return CanonicalGraph(
            node_ids=torch.arange(3),
            node_features=None,
            edge_index=torch.tensor([[0, 1], [1, 2]]),
            edge_type=torch.ones(2, dtype=torch.long),
            edge_weight=None,
            relation_schema={1: {"name": "friend", "directed": True}},
            metadata={"dataset_name": "postgres-integration"},
        )


def test_postgres_metadata_supports_the_full_batch_outbox_lifecycle(tmp_path):
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN is not configured")
    pytest.importorskip("psycopg")
    suffix = uuid.uuid4().hex
    repository = PostgresMetadataRepository.from_dsn(dsn)
    publisher = InMemoryEventPublisher()
    pipeline = BatchOrchestrator(
        repository,
        LocalArtifactStore(tmp_path / "artifacts"),
        publisher,
    )
    request = DatasetJobRequest(
        dataset_id=f"phase08-e2e-{suffix}",
        source_identity="integration:synthetic",
        graph_version=f"phase08-e2e-{suffix}",
        build_config={"test": True},
    )
    job = pipeline.create_dataset_or_index_job(request)

    result = pipeline.run_job(job.job_id, _TinyGraphAdapter())

    assert result.status is JobStatus.READY
    assert repository.active_version() == request.graph_version
    assert repository.get_job(job.job_id).status is JobStatus.READY
    assert len(publisher.events) == 1
    assert publisher.events[0].version == request.graph_version
    assert repository.pending_events() == ()
    with pytest.raises(JobAlreadyClaimedError):
        repository.claim_job(job.job_id)
