"""Async batch jobs: submit (202 + job_id) -> poll status -> collect results."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_jobs
from app.schemas.sentiment import (
    BatchItem,
    JobRequest,
    JobResultsResponse,
    JobStatusResponse,
    JobSubmitted,
)
from app.services.jobs import Job, JobManager, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job(job_id: str, jobs: JobManager) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found (unknown or expired)")
    return job


@router.post("/batch", response_model=JobSubmitted, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(body: JobRequest, request: Request, jobs: JobManager = Depends(get_jobs)):
    """Queue up to `MAX_JOB_TEXTS` texts for background scoring. Returns immediately."""
    job = jobs.submit(body.texts, return_probabilities=body.return_probabilities)
    return JobSubmitted(
        job_id=job.id,
        status=job.status.value,
        total=job.total,
        status_url=str(request.url_for("job_status", job_id=job.id).path),
        results_url=str(request.url_for("job_results", job_id=job.id).path),
    )


@router.get("/{job_id}", response_model=JobStatusResponse, name="job_status")
async def job_status(job_id: str, jobs: JobManager = Depends(get_jobs)):
    job = _get_job(job_id, jobs)
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        total=job.total,
        processed=job.processed,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
    )


@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    response_model_exclude_none=True,
    name="job_results",
)
async def job_results(job_id: str, jobs: JobManager = Depends(get_jobs)):
    job = _get_job(job_id, jobs)
    if job.status == JobStatus.failed:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Job failed: {job.error}")
    if job.status != JobStatus.complete:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job is {job.status.value} ({job.processed}/{job.total}); poll /api/v1/jobs/{job.id}",
        )
    with_probs = job.return_probabilities
    return JobResultsResponse(
        job_id=job.id,
        status=job.status.value,
        count=len(job.results),
        results=[
            BatchItem(
                text=text,
                label=p.label,
                confidence=round(p.confidence, 6),
                probabilities={k: round(v, 6) for k, v in p.probabilities.items()} if with_probs else None,
            )
            for text, p in zip(job.texts, job.results, strict=True)
        ],
    )
