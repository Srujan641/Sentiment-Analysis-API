"""Inference service: tokenize -> batch -> forward pass -> softmax.

The service is constructed once at startup and shared by every request. All texts in a
call are scored together; inputs larger than `batch_size` are split into chunks of
`batch_size`, each of which is a single forward pass.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from app.core.model_loader import LoadedModel
from app.services import metrics

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


class InferenceBackend(Protocol):
    """Anything that turns a list of texts into per-class probability rows."""

    labels: list[str]
    source: str

    def predict_proba(self, texts: list[str]) -> list[list[float]]: ...


class TransformerBackend:
    def __init__(self, loaded: LoadedModel, max_length: int):
        self._loaded = loaded
        self._max_length = max_length
        self.labels = loaded.labels
        self.source = loaded.source

    def predict_proba(self, texts: list[str]) -> list[list[float]]:
        import torch

        tok = self._loaded.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        tok = {k: v.to(self._loaded.device) for k, v in tok.items()}
        with torch.inference_mode():  # no autograd graph: we are not training
            logits = self._loaded.model(**tok).logits
        return torch.softmax(logits, dim=-1).cpu().tolist()


class InferenceService:
    def __init__(self, backend: InferenceBackend, batch_size: int = 32):
        self.backend = backend
        self.batch_size = batch_size
        # Requests run in a threadpool; one forward pass at a time keeps the tokenizer
        # thread-safe and lets torch use all cores for that pass.
        self._lock = threading.Lock()

    @property
    def labels(self) -> list[str]:
        return self.backend.labels

    @property
    def model_source(self) -> str:
        return self.backend.source

    def predict(self, texts: list[str]) -> list[Prediction]:
        if not texts:
            return []

        started = time.perf_counter()
        rows: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            with self._lock:
                rows.extend(self.backend.predict_proba(chunk))
            metrics.INFERENCE_BATCH_SIZE.observe(len(chunk))
        metrics.INFERENCE_LATENCY.observe(time.perf_counter() - started)

        predictions = []
        for probs in rows:
            best = max(range(len(probs)), key=probs.__getitem__)
            pred = Prediction(
                label=self.labels[best],
                confidence=float(probs[best]),
                probabilities={label: float(p) for label, p in zip(self.labels, probs, strict=True)},
            )
            metrics.PREDICTIONS.labels(label=pred.label).inc()
            metrics.PREDICTION_CONFIDENCE.observe(pred.confidence)
            predictions.append(pred)
        return predictions

    def predict_one(self, text: str) -> Prediction:
        return self.predict([text])[0]


def build_inference_service(settings) -> InferenceService:
    from app.core.model_loader import load_model

    loaded = load_model(settings)
    backend = TransformerBackend(loaded, max_length=settings.max_sequence_length)
    # Warm-up pass so the first real request doesn't pay for lazy kernel initialisation.
    backend.predict_proba(["warm-up"])
    return InferenceService(backend, batch_size=settings.inference_batch_size)
