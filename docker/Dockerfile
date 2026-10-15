# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/tmp/hf \
    MODEL_NAME_OR_PATH=/app/models/distilbert-sentiment \
    DRIFT_REFERENCE_PATH=/app/models/distilbert-sentiment/reference_stats.json \
    PREDICTION_LOG_PATH=/app/data/predictions.jsonl

WORKDIR /app

# CPU-only torch keeps the image ~1 GB smaller than the default CUDA wheel.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Weights are mounted read-only at /app/models (or MODEL_NAME_OR_PATH points at the Hub),
# so a new model can be swapped in without rebuilding the image.
RUN useradd --create-home --uid 10001 api \
    && mkdir -p /app/models /app/data \
    && chown -R api:api /app/data
USER api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/ready').status != 200)"

# One worker: the model is held in memory once and batch jobs live in this process.
# Scale horizontally with replicas (and a Redis RATE_LIMIT_STORAGE_URI) instead.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
