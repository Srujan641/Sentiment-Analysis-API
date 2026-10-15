"""Shared FastAPI dependencies: everything comes from app.state, created once at startup."""

from fastapi import HTTPException, Request, status

from app.services.drift import DriftMonitor
from app.services.inference import InferenceService
from app.services.jobs import JobManager


def get_inference(request: Request) -> InferenceService:
    service = getattr(request.app.state, "inference", None)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model is not loaded")
    return service


def get_jobs(request: Request) -> JobManager:
    jobs = getattr(request.app.state, "jobs", None)
    if jobs is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Job worker is not running")
    return jobs


def get_drift(request: Request) -> DriftMonitor | None:
    return getattr(request.app.state, "drift", None)


def get_request_id(request: Request) -> str | None:
    return request.scope.get("state", {}).get("request_id")
