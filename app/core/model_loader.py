"""Loads the fine-tuned DistilBERT checkpoint once, at application startup."""

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class LoadedModel:
    model: Any
    tokenizer: Any
    device: str
    labels: list[str]  # index -> canonical label ("NEGATIVE" / "POSITIVE")
    source: str


def _resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _canonical_labels(id2label: dict) -> list[str]:
    """Map checkpoint labels (e.g. LABEL_0 / negative) to NEGATIVE / POSITIVE."""
    labels = []
    for idx in range(len(id2label)):
        raw = str(id2label.get(idx, id2label.get(str(idx), idx))).upper()
        if raw in {"LABEL_0", "NEG", "NEGATIVE", "0"}:
            labels.append("NEGATIVE")
        elif raw in {"LABEL_1", "POS", "POSITIVE", "1"}:
            labels.append("POSITIVE")
        else:
            labels.append(raw)
    return labels


def load_model(settings: Settings) -> LoadedModel:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if settings.num_threads:
        torch.set_num_threads(settings.num_threads)

    started = time.perf_counter()
    source = settings.model_name_or_path
    device = _resolve_device(settings.device)

    tokenizer = AutoTokenizer.from_pretrained(source)
    model = AutoModelForSequenceClassification.from_pretrained(source)
    model.to(device)
    model.eval()  # inference only: disables dropout

    labels = _canonical_labels(model.config.id2label)
    logger.info(
        "model loaded",
        extra={
            "model_source": source,
            "device": device,
            "labels": labels,
            "load_seconds": round(time.perf_counter() - started, 2),
        },
    )
    return LoadedModel(model=model, tokenizer=tokenizer, device=device, labels=labels, source=source)
