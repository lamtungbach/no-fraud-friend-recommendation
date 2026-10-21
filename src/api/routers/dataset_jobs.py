"""Local-development administrative endpoints for Phase 08 dataset jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from src.api.runtime import ApiRuntime
from src.api.schemas import DatasetJobCreateRequest, DatasetJobResponse
from src.pipeline import DatasetJobRequest
from src.pipeline.models import PipelineJob

router = APIRouter(prefix="/datasets", tags=["dataset jobs"])


def _runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


def _service(runtime: ApiRuntime):
    if not runtime.settings.phase08_admin_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="dataset job administration is disabled",
        )
    if runtime.dataset_job_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dataset job service is unavailable",
        )
    return runtime.dataset_job_service


@router.post("/jobs", response_model=DatasetJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_dataset_job(payload: DatasetJobCreateRequest, request: Request) -> DatasetJobResponse:
    """Create a durable MGTAB job and schedule local development execution."""

    runtime = _runtime(request)
    service = _service(runtime)
    graph_version = payload.graph_version or _new_graph_version(payload.dataset_id)
    job_request = DatasetJobRequest(
        dataset_id=payload.dataset_id,
        source_identity=f"configured:{payload.dataset_id}",
        graph_version=graph_version,
        graph_semantics=payload.graph_semantics,
        build_config={"requested_via": "datasets-jobs-api", **payload.build_config},
    )
    try:
        job = service.create_and_schedule(job_request)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return _response(job)


@router.get("/jobs/{job_id}", response_model=DatasetJobResponse)
def get_dataset_job(job_id: str, request: Request) -> DatasetJobResponse:
    """Return the persisted lifecycle state without exposing storage internals."""

    job = _service(_runtime(request)).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset job not found")
    return _response(job)


def _new_graph_version(dataset_id: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{dataset_id}-{timestamp}-{uuid.uuid4().hex[:8]}"


def _response(job: PipelineJob) -> DatasetJobResponse:
    return DatasetJobResponse(
        job_id=job.job_id,
        dataset_id=job.dataset_id,
        graph_version=job.graph_version,
        graph_semantics=job.graph_semantics,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_code=job.error_code,
    )
