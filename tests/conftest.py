import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.inference import InferenceService

POSITIVE_WORDS = {"great", "best", "love", "excellent", "good"}
NEGATIVE_WORDS = {"terrible", "broke", "awful", "worst", "bad"}


class StubBackend:
    """Keyword scorer standing in for DistilBERT; records each forward-pass size."""

    labels = ["NEGATIVE", "POSITIVE"]
    source = "stub"

    def __init__(self):
        self.calls: list[int] = []

    def predict_proba(self, texts):
        self.calls.append(len(texts))
        rows = []
        for text in texts:
            words = set(text.lower().replace("!", " ").replace(".", " ").replace(",", " ").split())
            score = len(words & POSITIVE_WORDS) - len(words & NEGATIVE_WORDS)
            pos = 0.9 if score > 0 else 0.1 if score < 0 else 0.5
            rows.append([1 - pos, pos])
        return rows


@pytest.fixture
def reference_file(tmp_path):
    path = tmp_path / "reference_stats.json"
    path.write_text(
        json.dumps(
            {
                "n": 1000,
                "positive_rate": 0.5,
                "text_length": {"edges": [20, 50, 100, 200], "freqs": [0.2, 0.2, 0.2, 0.2, 0.2]},
                "confidence": {"edges": [0.6, 0.8, 0.9, 0.95], "freqs": [0.1, 0.1, 0.2, 0.3, 0.3]},
            }
        )
    )
    return str(path)


@pytest.fixture
def settings(reference_file):
    return Settings(
        api_keys=["test-key"],
        rate_limit_anonymous="1000/minute",
        rate_limit_authenticated="5000/minute",
        prediction_log_path=None,
        drift_reference_path=reference_file,
        log_json=False,
        log_level="WARNING",
        _env_file=None,
    )


@pytest.fixture
def backend():
    return StubBackend()


def make_client(settings, backend):
    app = create_app(settings, inference=InferenceService(backend, batch_size=settings.inference_batch_size))
    return TestClient(app)


@pytest.fixture
def client(settings, backend):
    with make_client(settings, backend) as c:
        yield c
