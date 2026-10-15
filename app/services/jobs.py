"""Background batch jobs: submit -> 202 + job_id, a worker scores them, the client polls.

Jobs live in process memory and are processed by a single asyncio worker that runs
inference in a thread, so the event loop keeps serving other requests. Run the API with a
single Uvicorn worker (or swap the store for Redis) so polls hit the process that owns
the job.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from starlette.concurrency import run_in_threadpool

from app.services import metrics

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"


@dataclass
class Job:
    id: str
    texts: list[str]
    return_probabilities: bool = False
    status: JobStatus = JobStatus.queued
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    processed: int = 0
    results: list | None = None
    error: str | None = None
    created_monotonic: float = field(default_factory=time.monotonic)

    @property
    def total(self) -> int:
        return len(self.texts)


class JobManager:
    def __init__(self, inference, drift=None, ttl_seconds: int = 3600, chunk_size: int = 32):
        self._inference = inference
        self._drift = drift
        self._ttl = ttl_seconds
        self._chunk = chunk_size
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    # --- lifecycle ---
    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="batch-job-worker")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    # --- API ---
    def submit(self, texts: list[str], return_probabilities: bool = False) -> Job:
        self._evict_expired()
        job = Job(id=uuid.uuid4().hex, texts=texts, return_probabilities=return_probabilities)
        self._jobs[job.id] = job
        self._queue.put_nowait(job.id)
        self._update_gauges()
        logger.info("job queued", extra={"job_id": job.id, "texts": job.total})
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    # --- worker ---
    async def _run(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if job is None:
                continue
            await self._process(job)
            self._queue.task_done()

    async def _process(self, job: Job) -> None:
        job.status = JobStatus.running
        job.started_at = datetime.now(UTC)
        self._update_gauges()
        results = []
        try:
            # Score chunk by chunk so progress is visible to pollers.
            for i in range(0, job.total, self._chunk):
                chunk = job.texts[i : i + self._chunk]
                preds = await run_in_threadpool(self._inference.predict, chunk)
                if self._drift:
                    self._drift.record(chunk, preds)
                results.extend(preds)
                job.processed += len(chunk)
            job.results = results
            job.status = JobStatus.complete
        except Exception as exc:  # noqa: BLE001 - surface any failure on the job
            logger.exception("job failed", extra={"job_id": job.id})
            job.status = JobStatus.failed
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(UTC)
            self._update_gauges()
            logger.info("job finished", extra={"job_id": job.id, "status": job.status.value})

    def _evict_expired(self) -> None:
        cutoff = time.monotonic() - self._ttl
        expired = [
            jid
            for jid, job in self._jobs.items()
            if job.status in (JobStatus.complete, JobStatus.failed) and job.created_monotonic < cutoff
        ]
        for jid in expired:
            del self._jobs[jid]

    def _update_gauges(self) -> None:
        for status in JobStatus:
            metrics.JOBS.labels(status=status.value).set(
                sum(1 for j in self._jobs.values() if j.status == status)
            )
