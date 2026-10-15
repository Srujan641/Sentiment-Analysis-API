.PHONY: install install-train model run test lint format docker-build docker-run stack load-test drift train sweep

PY ?= python

install:            ## serving + dev dependencies (CPU torch)
	$(PY) -m pip install torch --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -r requirements-dev.txt

install-train:      ## training, sweep and drift-report dependencies
	$(PY) -m pip install -r requirements-train.txt

model:              ## download the quick-start checkpoint into models/distilbert-sentiment
	$(PY) -m scripts.download_model

run:                ## dev server with reload
	uvicorn app.main:app --reload --port 8000

test:
	pytest --cov

lint:
	ruff check . && black --check . && isort --check-only .

format:
	isort . && black . && ruff check --fix .

docker-build:
	docker build -f docker/Dockerfile -t sentiment-api:latest .

docker-run:
	docker run --rm -p 8000:8000 -v "$(PWD)/models:/app/models:ro" sentiment-api:latest

stack:              ## API + Prometheus + Grafana
	docker compose -f docker/docker-compose.yml up --build

load-test:
	$(PY) -m scripts.load_test --requests 300 --concurrency 8

drift:
	$(PY) -m scripts.drift_report

train:
	$(PY) -m scripts.train

sweep:
	$(PY) -m scripts.sweep --count 10
