"""FastAPI application factory.

The model is loaded exactly once, in the lifespan hook, and shared through `app.state`.
Every request after startup is a forward pass, not a file read.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import ApiKeyMiddleware, RateLimitMiddleware, RequestIdMiddleware
from app.schemas.sentiment import HealthResponse
from app.services import metrics
from app.services.drift import DriftMonitor
from app.services.inference import InferenceService, build_inference_service
from app.services.jobs import JobManager

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, inference: InferenceService | None = None) -> FastAPI:
    """Build the app. Tests pass a stub `inference` service to skip loading real weights."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.inference = inference or build_inference_service(settings)
        metrics.MODEL_LOADED.set(1)
        app.state.drift = DriftMonitor(
            reference_path=settings.drift_reference_path,
            window=settings.drift_window,
            log_path=settings.prediction_log_path,
        )
        app.state.jobs = JobManager(
            app.state.inference,
            drift=app.state.drift,
            ttl_seconds=settings.job_ttl_seconds,
            chunk_size=settings.inference_batch_size,
        )
        app.state.jobs.start()
        logger.info("startup complete", extra={"model_source": app.state.inference.model_source})
        try:
            yield
        finally:
            await app.state.jobs.stop()
            metrics.MODEL_LOADED.set(0)
            app.state.inference = None

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Fine-tuned DistilBERT sentiment classifier for product reviews. "
            "Anonymous: 60 req/min. With `X-API-Key`: 300 req/min."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.inference = None

    # Starlette wraps middleware in reverse order of registration: the last one added is
    # outermost. Effective order per request: CORS -> rate limit -> request ID -> API key.
    app.add_middleware(ApiKeyMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    )

    app.include_router(api_router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def frontend():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    async def health(request: Request):
        """Liveness: the process is up."""
        service = request.app.state.inference
        return HealthResponse(
            status="ok",
            model_loaded=service is not None,
            model_source=service.model_source if service else None,
            version=__version__,
        )

    @app.get("/ready", response_model=HealthResponse, tags=["ops"])
    async def ready(request: Request):
        """Readiness: the model is loaded and can serve predictions."""
        service = request.app.state.inference
        body = HealthResponse(
            status="ready" if service else "loading",
            model_loaded=service is not None,
            model_source=service.model_source if service else None,
            version=__version__,
        )
        return JSONResponse(body.model_dump(), status_code=200 if service else 503)

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(request: Request):
        drift = getattr(request.app.state, "drift", None)
        if drift:
            drift.report()  # refresh drift gauges on every scrape
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error")
        return JSONResponse(
            {
                "detail": "Internal server error",
                "request_id": request.scope.get("state", {}).get("request_id"),
            },
            status_code=500,
        )

    return app


app = create_app()
