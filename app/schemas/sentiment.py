"""Pydantic request / response models. Invalid input is rejected with 422 before inference."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


def _clean(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("text must not be empty or whitespace")
    limit = get_settings().max_text_length
    if len(text) > limit:
        raise ValueError(f"text exceeds {limit} characters")
    return text


# ---------- requests ----------
class PredictRequest(BaseModel):
    text: str = Field(..., examples=["Best product I have ever bought!"])
    return_probabilities: bool = False

    @field_validator("text")
    @classmethod
    def _check(cls, text: str) -> str:
        return _clean(text)


class BatchRequest(BaseModel):
    texts: list[str] = Field(
        ...,
        min_length=1,
        examples=[["Great product!", "Terrible quality, broke immediately."]],
    )
    return_probabilities: bool = False

    @field_validator("texts")
    @classmethod
    def _check(cls, texts: list[str]) -> list[str]:
        limit = get_settings().inference_batch_size
        if len(texts) > limit:
            raise ValueError(
                f"at most {limit} texts per /batch call; use /api/v1/jobs/batch for larger inputs"
            )
        return [_clean(t) for t in texts]


class JobRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    return_probabilities: bool = False

    @field_validator("texts")
    @classmethod
    def _check(cls, texts: list[str]) -> list[str]:
        limit = get_settings().max_job_texts
        if len(texts) > limit:
            raise ValueError(f"at most {limit} texts per job")
        return [_clean(t) for t in texts]


# ---------- responses ----------
class PredictionOut(BaseModel):
    label: str
    confidence: float = Field(..., ge=0, le=1)
    probabilities: dict[str, float] | None = None


class PredictResponse(PredictionOut):
    model_config = ConfigDict(protected_namespaces=())

    text: str
    latency_ms: float
    request_id: str | None = None


class BatchItem(PredictionOut):
    text: str


class BatchResponse(BaseModel):
    results: list[BatchItem]
    count: int
    latency_ms: float
    request_id: str | None = None


class JobSubmitted(BaseModel):
    job_id: str
    status: str
    total: int
    status_url: str
    results_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    processed: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class JobResultsResponse(BaseModel):
    job_id: str
    status: str
    count: int
    results: list[BatchItem]


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    model_loaded: bool
    model_source: str | None = None
    version: str
