"""Online drift detection.

Every prediction is recorded (in a rolling in-memory window, and optionally appended to a
JSONL log that the daily Evidently report reads). The live window is compared against the
reference statistics written by `scripts/train.py` using the population stability index.

PSI rule of thumb: < 0.1 stable, 0.1-0.25 moderate shift, > 0.25 significant drift.
"""

import json
import logging
import math
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from app.services import metrics

logger = logging.getLogger(__name__)

PSI_WARN = 0.1
PSI_ALERT = 0.25
_EPS = 1e-4


def psi(expected: list[float], actual: list[float]) -> float:
    """Population stability index between two binned frequency distributions."""
    total = 0.0
    for e, a in zip(expected, actual, strict=True):
        e, a = max(e, _EPS), max(a, _EPS)
        total += (a - e) * math.log(a / e)
    return total


def histogram(values: list[float], edges: list[float]) -> list[float]:
    """Relative frequencies of `values` over bins defined by `edges` (open-ended at both ends)."""
    counts = [0] * (len(edges) + 1)
    for v in values:
        idx = 0
        while idx < len(edges) and v >= edges[idx]:
            idx += 1
        counts[idx] += 1
    n = max(len(values), 1)
    return [c / n for c in counts]


class DriftMonitor:
    def __init__(self, reference_path: str | None, window: int = 1000, log_path: str | None = None):
        self.window = window
        self._records: deque[dict] = deque(maxlen=window)
        self._lock = threading.Lock()
        self.reference = self._load_reference(reference_path)
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_reference(path: str | None) -> dict | None:
        if not path or not Path(path).exists():
            logger.warning("drift reference stats not found; drift scores disabled", extra={"path": path})
            return None
        with open(path) as fh:
            return json.load(fh)

    def record(self, texts: list[str], predictions) -> None:
        now = datetime.now(UTC).isoformat()
        rows = [
            {
                "ts": now,
                "text_length": len(text),
                "word_count": len(text.split()),
                "label": pred.label,
                "confidence": round(pred.confidence, 6),
            }
            for text, pred in zip(texts, predictions, strict=True)
        ]
        for row in rows:
            metrics.INPUT_LENGTH.observe(row["text_length"])
        with self._lock:
            self._records.extend(rows)
            if self.log_path:
                try:
                    with self.log_path.open("a") as fh:
                        fh.writelines(json.dumps(r) + "\n" for r in rows)
                except OSError:
                    logger.exception("failed to append prediction log")

    def report(self) -> dict:
        with self._lock:
            records = list(self._records)

        n = len(records)
        result: dict = {
            "window_size": n,
            "window_capacity": self.window,
            "reference_loaded": bool(self.reference),
        }
        if n == 0:
            result["status"] = "no_data"
            return result

        positive_rate = sum(r["label"] == "POSITIVE" for r in records) / n
        result["live"] = {
            "positive_rate": round(positive_rate, 4),
            "mean_confidence": round(sum(r["confidence"] for r in records) / n, 4),
            "mean_text_length": round(sum(r["text_length"] for r in records) / n, 1),
        }
        if not self.reference:
            result["status"] = "no_reference"
            return result

        features = {}
        for name in ("text_length", "confidence"):
            ref = self.reference[name]
            live = histogram([r[name] for r in records], ref["edges"])
            score = psi(ref["freqs"], live)
            metrics.DRIFT_SCORE.labels(feature=name).set(score)
            features[name] = round(score, 4)

        ref_pos = self.reference["positive_rate"]
        label_psi = psi([1 - ref_pos, ref_pos], [1 - positive_rate, positive_rate])
        metrics.DRIFT_SCORE.labels(feature="label").set(label_psi)
        features["label"] = round(label_psi, 4)

        worst = max(features.values())
        result["psi"] = features
        result["reference"] = {
            "positive_rate": ref_pos,
            "n": self.reference.get("n"),
        }
        result["status"] = "drift" if worst > PSI_ALERT else "warning" if worst > PSI_WARN else "stable"
        result["min_samples_for_reliable_psi"] = 200
        return result
