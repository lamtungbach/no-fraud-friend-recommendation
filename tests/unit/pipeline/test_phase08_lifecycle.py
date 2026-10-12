from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest
import torch
from fastapi.testclient import TestClient

from src.api.config import ApiSettings
from src.api.main import create_app
from src.api.runtime import build_runtime
from src.data import CanonicalGraph, DatasetAdapter
from src.pipeline import (
    ActiveIndexHolder,
    BatchOrchestrator,
    DatasetJobRequest,
    GraphIndexReadyConsumer,
    InMemoryEventPublisher,
    InMemoryMetadataRepository,
    JobAlreadyClaimedError,
    JobStatus,
    PostgresMetadataRepository,
    ServingIndexReloader,
)
from src.pipeline.models import GraphVersionRecord, OutboxRecord
from src.serving import LocalArtifactStore


class FixtureAdapter(DatasetAdapter):
    def __init__(self, *, invalid: bool = False):
        self.invalid = invalid

    def load_raw(self):
        return {"not_logged": "raw input stays in adapter"}

    def transform(self) -> CanonicalGraph:
        edge_index = torch.tensor([[0, 1, 2], [1, 2, 0]])
        if self.invalid:
            edge_index = torch.tensor([[0], [8]])
        return CanonicalGraph(
            node_ids=torch.arange(3),
            node_features=None,
            edge_index=edge_index,
            edge_type=torch.ones(edge_index.shape[1], dtype=torch.long),
            edge_weight=None,
            relation_schema={1: {"name": "friend", "directed": True}},
            metadata={"dataset_name": "test-only"},
        )


class FailingStore(LocalArtifactStore):
    def save_version(self, *args, **kwargs):
        raise OSError("storage unavailable")


class FailingActivationRepository(InMemoryMetadataRepository):
    fail_activation = False

    def activate_version(self, graph_version, event):
        if self.fail_activation:
            raise RuntimeError("metadata transaction failed")
        super().activate_version(graph_version, event)


def _pipeline(tmp_path, *, metadata=None, publisher=None, store=None):
    return (
        metadata or InMemoryMetadataRepository(),
        publisher or InMemoryEventPublisher(),
        store or LocalArtifactStore(tmp_path / "artifacts"),
    )


def _request(version: str = "phase08-v1") -> DatasetJobRequest:
    return DatasetJobRequest("dataset-a", "fixture:dataset-a", version, build_config={"seed": 9})


def test_lifecycle_persists_before_ready_activates_and_emits(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    job = pipeline.create_dataset_or_index_job(_request())

    result = pipeline.run_job(job.job_id, FixtureAdapter())

    assert result.status is JobStatus.READY
    assert metadata.active_version() == "phase08-v1"
    assert store.validate_version("phase08-v1").manifest["checksum"]
    assert len(publisher.events) == 1
    assert publisher.events[0].version == "phase08-v1"
    assert metadata.pending_events() == ()
    assert metadata.versions["phase08-v1"].activated_at is not None


def test_adapter_or_validation_failure_never_creates_ready_version(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    job = pipeline.create_dataset_or_index_job(_request())

    with pytest.raises(ValueError, match="num_nodes"):
        pipeline.run_job(job.job_id, FixtureAdapter(invalid=True))

    assert pipeline.get_job(job.job_id).status is JobStatus.FAILED
    assert metadata.active_version() is None
    assert store.list_versions() == ()
    assert publisher.events == []


def test_artifact_or_activation_failure_preserves_healthy_active_version(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    first = pipeline.create_dataset_or_index_job(_request("healthy-v1"))
    pipeline.run_job(first.job_id, FixtureAdapter())
    assert metadata.active_version() == "healthy-v1"

    failing = BatchOrchestrator(metadata, FailingStore(tmp_path / "unavailable"), publisher)
    failed = failing.create_dataset_or_index_job(_request("bad-storage-v2"))
    with pytest.raises(OSError):
        failing.run_job(failed.job_id, FixtureAdapter())
    assert metadata.active_version() == "healthy-v1"
    assert failing.get_job(failed.job_id).status is JobStatus.FAILED

    activation_metadata = FailingActivationRepository()
    activation_pipeline = BatchOrchestrator(activation_metadata, store, publisher)
    healthy_activation = activation_pipeline.create_dataset_or_index_job(_request("metadata-healthy-v3"))
    activation_pipeline.run_job(healthy_activation.job_id, FixtureAdapter())
    activation_metadata.fail_activation = True
    activation = activation_pipeline.create_dataset_or_index_job(_request("activation-fails-v4"))
    with pytest.raises(RuntimeError, match="transaction"):
        activation_pipeline.run_job(activation.job_id, FixtureAdapter())
    assert activation_metadata.active_version() == "metadata-healthy-v3"
    assert activation_pipeline.get_job(activation.job_id).status is JobStatus.FAILED


def test_publish_failure_is_retained_in_outbox_and_retry_is_idempotent(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    publisher.fail_next = True
    pipeline = BatchOrchestrator(metadata, store, publisher)
    job = pipeline.create_dataset_or_index_job(_request())

    assert pipeline.run_job(job.job_id, FixtureAdapter()).status is JobStatus.READY
    assert metadata.active_version() == "phase08-v1"
    assert len(metadata.pending_events()) == 1
    assert publisher.events == []

    assert pipeline.retry_pending_events() == 1
    assert pipeline.retry_pending_events() == 0
    assert len(publisher.events) == 1
    assert metadata.pending_events() == ()


def test_serving_reloader_deduplicates_and_keeps_previous_index_on_corruption(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    first = pipeline.create_dataset_or_index_job(_request("serving-v1"))
    pipeline.run_job(first.job_id, FixtureAdapter())
    holder = ActiveIndexHolder()
    consumer = GraphIndexReadyConsumer(ServingIndexReloader(store, holder).reload)

    assert consumer.consume(publisher.events[0]) is True
    assert holder.get().graph_version == "serving-v1"
    assert consumer.consume(publisher.events[0]) is False

    second = pipeline.create_dataset_or_index_job(_request("corrupt-v2"))
    pipeline.run_job(second.job_id, FixtureAdapter())
    (store.version_path("corrupt-v2") / "canonical" / "tensors.pt").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="size mismatch|checksum"):
        consumer.consume(publisher.events[1])
    assert holder.get().graph_version == "serving-v1"


def test_stale_distinct_event_cannot_roll_back_the_serving_holder(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    first = pipeline.create_dataset_or_index_job(_request("ordered-v1"))
    second = pipeline.create_dataset_or_index_job(_request("ordered-v2"))
    pipeline.run_job(first.job_id, FixtureAdapter())
    pipeline.run_job(second.job_id, FixtureAdapter())
    holder = ActiveIndexHolder()
    consumer = GraphIndexReadyConsumer(ServingIndexReloader(store, holder).reload)

    assert consumer.consume(publisher.events[1]) is True
    assert consumer.consume(publisher.events[0]) is False
    assert holder.get().graph_version == "ordered-v2"


def test_duplicate_worker_cannot_fail_the_owner_job(tmp_path):
    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    job = pipeline.create_dataset_or_index_job(_request("claimed-v1"))

    metadata.claim_job(job.job_id)
    with pytest.raises(JobAlreadyClaimedError):
        pipeline.run_job(job.job_id, FixtureAdapter())

    assert pipeline.get_job(job.job_id).status is JobStatus.RUNNING
    assert store.list_versions() == ()
    assert publisher.events == []


def test_concurrent_duplicate_worker_leaves_the_owner_job_healthy(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class BlockingAdapter(FixtureAdapter):
        def transform(self) -> CanonicalGraph:
            entered.set()
            assert release.wait(timeout=5)
            return super().transform()

    metadata, publisher, store = _pipeline(tmp_path)
    pipeline = BatchOrchestrator(metadata, store, publisher)
    job = pipeline.create_dataset_or_index_job(_request("concurrent-v1"))
    outcome: list[object] = []

    def run_owner() -> None:
        try:
            outcome.append(pipeline.run_job(job.job_id, BlockingAdapter()))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            outcome.append(error)

    owner = threading.Thread(target=run_owner)
    owner.start()
    assert entered.wait(timeout=5)
    with pytest.raises(JobAlreadyClaimedError):
        pipeline.run_job(job.job_id, FixtureAdapter())
    release.set()
    owner.join(timeout=5)

    assert not owner.is_alive()
    assert outcome[0].status is JobStatus.READY
    assert metadata.active_version() == "concurrent-v1"


class TopologyAdapter(DatasetAdapter):
    def __init__(self, terminal: int):
        self.terminal = terminal

    def load_raw(self):
        return None

    def transform(self) -> CanonicalGraph:
        return CanonicalGraph(
            node_ids=torch.arange(4),
            node_features=None,
            edge_index=torch.tensor([[0, 1], [1, self.terminal]]),
            edge_type=torch.ones(2, dtype=torch.long),
            edge_weight=None,
            relation_schema={1: {"name": "friend", "directed": True}},
        )


def test_event_consumer_swaps_the_actual_recommendation_runtime(tmp_path):
    root = tmp_path / "artifacts"
    settings = ApiSettings(
        environment="test",
        trust_provider="mock",
        artifact_root=root,
        registry_root=tmp_path / "registry",
        max_top_k=3,
        raw_top_m=3,
    )
    metadata = InMemoryMetadataRepository()
    runtime = build_runtime(settings, active_version_provider=metadata.active_version)
    _, publisher, store = _pipeline(
        tmp_path,
        metadata=metadata,
        store=runtime.artifact_store,
    )
    publisher.subscribe(runtime.consume_graph_index_ready)
    pipeline = BatchOrchestrator(metadata, store, publisher)

    first = pipeline.create_dataset_or_index_job(_request("runtime-v1"))
    pipeline.run_job(first.job_id, TopologyAdapter(2))
    first_result = runtime.engine.recommend(0, 3)
    client = TestClient(create_app(settings=settings, runtime=runtime))
    first_http = client.post("/v1/recommendations", json={"user_id": 0, "top_k": 3})
    second = pipeline.create_dataset_or_index_job(_request("runtime-v2"))
    pipeline.run_job(second.job_id, TopologyAdapter(3))
    second_result = runtime.engine.recommend(0, 3)
    second_http = client.post("/v1/recommendations", json={"user_id": 0, "top_k": 3})

    assert runtime.active_registry.get_active_version() == "runtime-v2"
    assert runtime.active_index_holder.get().graph_version == "runtime-v2"
    assert first_result.graph_version == "runtime-v1"
    assert [item.candidate_id for item in first_result.recommendations] == [2]
    assert second_result.graph_version == "runtime-v2"
    assert [item.candidate_id for item in second_result.recommendations] == [3]
    assert first_http.status_code == 200
    assert first_http.json()["graph_version"] == "runtime-v1"
    assert [item["candidate_id"] for item in first_http.json()["recommendations"]] == [2]
    assert second_http.status_code == 200
    assert second_http.json()["graph_version"] == "runtime-v2"
    assert [item["candidate_id"] for item in second_http.json()["recommendations"]] == [3]
    assert runtime.consume_graph_index_ready(publisher.events[0]) is False
    assert runtime.active_index_holder.get().graph_version == "runtime-v2"


def test_job_state_machine_rejects_skips_and_safe_error_text(tmp_path):
    metadata, _, _ = _pipeline(tmp_path)
    metadata.create_dataset("dataset-a", "fixture:a")
    job = metadata.create_job("dataset-a", "version-a", "directed", {})

    with pytest.raises(ValueError, match="invalid job transition"):
        metadata.transition_job(job.job_id, JobStatus.READY)
    metadata.transition_job(job.job_id, JobStatus.RUNNING)
    metadata.transition_job(job.job_id, JobStatus.FAILED, error=ValueError("private source path"))
    assert metadata.get_job(job.job_id).error_code == "ValueError"


class _ScriptedPostgresState:
    """Minimal DB-API script exercising the adapter without a live database."""

    def __init__(self):
        self.now = datetime(2026, 10, 12, tzinfo=UTC)
        self.statements: list[str] = []

    def job_row(self, status: JobStatus) -> tuple[object, ...]:
        return (
            "job-1",
            "dataset-a",
            "pg-v1",
            "directed",
            '{"seed":9}',
            status,
            self.now,
            self.now,
            None,
        )


class _ScriptedCursor:
    def __init__(self, state: _ScriptedPostgresState):
        self._state = state
        self._one: tuple[object, ...] | None = None
        self._all: list[tuple[object, ...]] = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        compact = " ".join(query.split())
        self._state.statements.append(compact)
        self._one, self._all, self.rowcount = None, [], 1
        if "INSERT INTO datasets" in compact:
            self._one = ("dataset-a", "fixture:dataset-a", self._state.now)
        elif compact.startswith(
            ("INSERT INTO pipeline_jobs", "SELECT job_id,dataset_id")
        ):
            self._one = self._state.job_row(JobStatus.PENDING)
        elif compact.startswith("UPDATE pipeline_jobs SET status=%s,updated_at"):
            self._one = self._state.job_row(JobStatus.RUNNING)
        elif compact.startswith("UPDATE pipeline_jobs SET status=%s,error_code"):
            self._one = self._state.job_row(params[0])
        elif compact.startswith("SELECT job_id FROM graph_versions"):
            self._one = ("job-1",)
        elif compact.startswith("SELECT event_id,graph_version,payload"):
            self._all = [
                ("event-1", "pg-v1", '{"version":"pg-v1"}', self._state.now, None)
            ]
        elif compact.startswith("SELECT graph_version FROM active_versions"):
            self._one = ("pg-v1",)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class _ScriptedConnection:
    def __init__(self, state: _ScriptedPostgresState):
        self._state = state
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _ScriptedCursor(self._state)

    def commit(self):
        self.commits += 1


def test_postgres_metadata_adapter_executes_full_happy_path_without_raw_graph_data():
    state = _ScriptedPostgresState()
    repository = PostgresMetadataRepository(lambda: _ScriptedConnection(state))
    now = state.now

    dataset = repository.create_dataset("dataset-a", "fixture:dataset-a")
    pending = repository.create_job("dataset-a", "pg-v1", "directed", {"seed": 9})
    loaded = repository.get_job("job-1")
    running = repository.claim_job("job-1")
    validating = repository.transition_job("job-1", JobStatus.VALIDATING)
    version = GraphVersionRecord(
        "pg-v1",
        "dataset-a",
        "job-1",
        "directed",
        3,
        2,
        "artifacts/graph/pg-v1",
        "checksum",
        {"seed": 9},
        now,
    )
    repository.record_graph_version(version)
    repository.activate_version(
        "pg-v1", OutboxRecord("event-1", "pg-v1", {"version": "pg-v1"}, now)
    )
    events = repository.pending_events()
    repository.mark_event_published("event-1")

    assert dataset.dataset_id == "dataset-a"
    assert pending.status is JobStatus.PENDING
    assert loaded is not None and loaded.build_config == {"seed": 9}
    assert running.status is JobStatus.RUNNING
    assert validating.status is JobStatus.VALIDATING
    assert events[0].payload == {"version": "pg-v1"}
    assert repository.active_version() == "pg-v1"
    assert any("FOR UPDATE" in statement for statement in state.statements)
    assert all("adjacency" not in statement.lower() for statement in state.statements)
