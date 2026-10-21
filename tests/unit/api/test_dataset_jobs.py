from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.config import ApiSettings
from src.api.main import create_app
from src.pipeline.models import JobStatus, PipelineJob


def _job(status: JobStatus = JobStatus.PENDING, *, error_code: str | None = None) -> PipelineJob:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    return PipelineJob(
        "job-1",
        "mgtab",
        "mgtab-test-v1",
        "directed",
        {"requested_via": "datasets-jobs-api"},
        status,
        now,
        now,
        error_code,
    )


@dataclass
class FakeJobService:
    current: PipelineJob | None = None
    error: Exception | None = None
    requested: object | None = None

    def create_and_schedule(self, request):
        self.requested = request
        if self.error:
            raise self.error
        return self.current or _job()

    def get_job(self, job_id: str):
        return self.current if job_id == "job-1" else None


def _client(*, enabled: bool = True, service: FakeJobService | None = None) -> TestClient:
    settings = ApiSettings(
        environment="development",
        phase08_admin_enabled=enabled,
        postgres_dsn="postgresql://test",
    )
    runtime = SimpleNamespace(settings=settings, dataset_job_service=service)
    return TestClient(create_app(settings=settings, runtime=runtime))


def test_create_dataset_job_returns_accepted_and_uses_configured_dataset_only():
    service = FakeJobService()
    response = _client(service=service).post("/datasets/jobs", json={"dataset_id": "mgtab"})

    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert service.requested.dataset_id == "mgtab"
    assert service.requested.source_identity == "configured:mgtab"


def test_dataset_job_rejects_an_unknown_dataset_before_scheduling():
    response = _client(service=FakeJobService()).post("/datasets/jobs", json={"dataset_id": "other"})

    assert response.status_code == 422


def test_dataset_job_admin_route_is_disabled_by_default():
    response = _client(enabled=False, service=FakeJobService()).post("/datasets/jobs", json={"dataset_id": "mgtab"})

    assert response.status_code == 403


def test_duplicate_or_conflicting_submission_is_visible_to_client():
    service = FakeJobService(error=ValueError("graph_version is already registered"))
    response = _client(service=service).post(
        "/datasets/jobs", json={"dataset_id": "mgtab", "graph_version": "mgtab-v1"}
    )

    assert response.status_code == 422
    assert "already registered" in response.json()["detail"]


def test_get_dataset_job_returns_persisted_failed_state_and_unknown_is_404():
    service = FakeJobService(current=_job(JobStatus.FAILED, error_code="ValueError"))
    client = _client(service=service)

    response = client.get("/datasets/jobs/job-1")
    assert response.status_code == 200
    assert response.json()["status"] == "FAILED"
    assert response.json()["error_code"] == "ValueError"
    assert client.get("/datasets/jobs/missing").status_code == 404
