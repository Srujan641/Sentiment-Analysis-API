"""Prometheus metrics: HTTP health plus ML-specific counters exposed at GET /metrics."""

from prometheus_client import Counter, Gauge, Histogram

# --- HTTP ---
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests by method, route template and status code.",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "End-to-end HTTP request latency.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
RATE_LIMITED = Counter("rate_limited_requests_total", "Requests rejected with 429.", ["tier"])

# --- ML ---
PREDICTIONS = Counter("sentiment_predictions_total", "Predictions served, by predicted label.", ["label"])
PREDICTION_CONFIDENCE = Histogram(
    "sentiment_prediction_confidence",
    "Confidence (max class probability) of each prediction.",
    buckets=(0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.975, 0.99, 1.0),
)
INFERENCE_LATENCY = Histogram(
    "sentiment_inference_duration_seconds",
    "Model time per inference call (tokenize + forward + softmax).",
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30),
)
INFERENCE_BATCH_SIZE = Histogram(
    "sentiment_inference_batch_size",
    "Texts per forward pass.",
    buckets=(1, 2, 4, 8, 16, 32, 64, 128, 256),
)
INPUT_LENGTH = Histogram(
    "sentiment_input_length_chars",
    "Character length of input texts (a cheap drift signal).",
    buckets=(10, 25, 50, 100, 200, 400, 800, 1600, 3200, 5000),
)
MODEL_LOADED = Gauge("sentiment_model_loaded", "1 when the model is loaded and serving.")
JOBS = Gauge("sentiment_batch_jobs", "Background batch jobs by status.", ["status"])
DRIFT_SCORE = Gauge("sentiment_drift_psi", "Population stability index vs. training reference.", ["feature"])
