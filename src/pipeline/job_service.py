"""Local administrative runner for persistent Phase 08 dataset jobs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from src.data import DatasetAdapter

from .models import PipelineJob
from .orchestrator import BatchOrchestrator, DatasetJobRequest

LOGGER = logging.getLogger(__name__)


class LocalDatasetJobService:
    """Schedules a configured adapter through the canonical orchestrator.

    The database remains the authority for the job record and outbox.  The
    executor is intentionally a development convenience, not a durable worker
    system; a process restart leaves a durable record for inspection/retry.
    """

    def __init__(
        self,
        orchestrator: BatchOrchestrator,
        adapters: dict[str, Callable[[], DatasetAdapter]],
        *,
        executor: ThreadPoolExecutor | None = None,
    ):
        self._orchestrator = orchestrator
        self._adapters = dict(adapters)
        self._executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="pymk-batch")
        self._owns_executor = executor is None
        self._futures: dict[str, Future[PipelineJob]] = {}

    def create_and_schedule(self, request: DatasetJobRequest) -> PipelineJob:
        if request.dataset_id not in self._adapters:
            raise ValueError("dataset is not enabled for local jobs")
        job = self._orchestrator.create_dataset_or_index_job(request)
        self._futures[job.job_id] = self._executor.submit(self._run, job.job_id, request.dataset_id)
        return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        return self._orchestrator.get_job(job_id)

    def retry_pending_events(self) -> int:
        return self._orchestrator.retry_pending_events()

    def shutdown(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=False)

    def _run(self, job_id: str, dataset_id: str) -> PipelineJob:
        try:
            return self._orchestrator.run_job(job_id, self._adapters[dataset_id]())
        except Exception:  # The orchestrator records a sanitized FAILED state.
            LOGGER.exception("dataset_job_execution_failed job_id=%s", job_id)
            raise
