"""POST /api/v1/predict and POST /api/v1/batch — synchronous scoring."""

import time

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_drift, get_inference, get_request_id
from app.schemas.sentiment import (
    BatchItem,
    BatchRequest,
    BatchResponse,
    PredictRequest,
    PredictResponse,
)

router = APIRouter(tags=["predict"])


@router.post("/predict", response_model=PredictResponse, response_model_exclude_none=True)
async def predict(
    body: PredictRequest,
    inference=Depends(get_inference),
    drift=Depends(get_drift),
    request_id=Depends(get_request_id),
):
    """One text in, label and confidence out."""
    started = time.perf_counter()
    # Run the forward pass off the event loop so other requests keep flowing.
    (pred,) = await run_in_threadpool(inference.predict, [body.text])
    latency_ms = (time.perf_counter() - started) * 1000
    if drift:
        drift.record([body.text], [pred])
    return PredictResponse(
        text=body.text,
        label=pred.label,
        confidence=round(pred.confidence, 6),
        probabilities=_round(pred.probabilities) if body.return_probabilities else None,
        latency_ms=round(latency_ms, 2),
        request_id=request_id,
    )


@router.post("/batch", response_model=BatchResponse, response_model_exclude_none=True)
async def batch(
    body: BatchRequest,
    inference=Depends(get_inference),
    drift=Depends(get_drift),
    request_id=Depends(get_request_id),
):
    """Up to `INFERENCE_BATCH_SIZE` texts scored in a single forward pass."""
    started = time.perf_counter()
    preds = await run_in_threadpool(inference.predict, body.texts)
    latency_ms = (time.perf_counter() - started) * 1000
    if drift:
        drift.record(body.texts, preds)
    return BatchResponse(
        results=[
            BatchItem(
                text=text,
                label=p.label,
                confidence=round(p.confidence, 6),
                probabilities=_round(p.probabilities) if body.return_probabilities else None,
            )
            for text, p in zip(body.texts, preds, strict=True)
        ],
        count=len(preds),
        latency_ms=round(latency_ms, 2),
        request_id=request_id,
    )


def _round(probs: dict[str, float]) -> dict[str, float]:
    return {k: round(v, 6) for k, v in probs.items()}
