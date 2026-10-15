"""The four layers every request crosses before it reaches a tensor.

    CORS -> rate limit -> request ID + structured logging -> API key -> route

All are plain ASGI middleware. Rate limiting is deliberately ahead of auth and inference
so a flood is rejected cheaply, before it costs a forward pass.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid

from limits import parse
from slowapi import Limiter
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.logging import request_id_ctx
from app.services import metrics

logger = logging.getLogger("app.access")

# Probes, metrics and docs are never rate limited or authenticated.
EXEMPT_PREFIXES = ("/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json")


def _exempt(path: str) -> bool:
    return path == "/" or path.startswith(EXEMPT_PREFIXES)


def extract_api_key(headers: Headers) -> str | None:
    key = headers.get("x-api-key")
    if key:
        return key.strip()
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def is_valid_key(key: str | None, valid_keys: list[str]) -> bool:
    if not key:
        return False
    return any(hmac.compare_digest(key, k) for k in valid_keys)


async def _send_json(send: Send, status: int, body: dict, headers: dict | None = None) -> None:
    raw = json.dumps(body).encode()
    hdrs = [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]
    hdrs += [(k.lower().encode(), str(v).encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": hdrs})
    await send({"type": "http.response.body", "body": raw})


class RateLimitMiddleware:
    """Tiered limits via slowapi: anonymous callers by client IP, keyed callers by key."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        self.enabled = settings.rate_limit_enabled
        self.limiter = Limiter(
            key_func=lambda request: "unused",  # keys are computed below
            storage_uri=settings.rate_limit_storage_uri,
            strategy="moving-window",
        )
        self.anon_limit = parse(settings.rate_limit_anonymous)
        self.auth_limit = parse(settings.rate_limit_authenticated)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled or _exempt(scope["path"]):
            await self.app(scope, receive, send)
            return

        key = extract_api_key(Headers(scope=scope))
        if is_valid_key(key, self.settings.api_keys):
            tier, limit = "authenticated", self.auth_limit
            identity = "key:" + hashlib.sha256(key.encode()).hexdigest()[:16]
        else:
            tier, limit = "anonymous", self.anon_limit
            client = scope.get("client")
            identity = "ip:" + (client[0] if client else "unknown")

        strategy = self.limiter.limiter
        allowed = strategy.hit(limit, identity)
        reset_at, remaining = strategy.get_window_stats(limit, identity)
        rl_headers = {
            "X-RateLimit-Limit": limit.amount,
            "X-RateLimit-Remaining": max(remaining, 0),
            "X-RateLimit-Reset": int(reset_at),
            "X-RateLimit-Tier": tier,
        }

        if not allowed:
            metrics.RATE_LIMITED.labels(tier=tier).inc()
            retry_after = max(int(reset_at - time.time()), 1)
            await _send_json(
                send,
                429,
                {"detail": f"Rate limit exceeded: {limit} for {tier} callers"},
                {**rl_headers, "Retry-After": retry_after},
            )
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for k, v in rl_headers.items():
                    headers[k] = str(v)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _route_template(scope: Scope) -> str:
    """Full path with params collapsed (/api/v1/jobs/{job_id}) to keep metric cardinality low."""
    if scope.get("route") is None:
        return "unmatched"
    path = scope["path"]
    for name, value in (scope.get("path_params") or {}).items():
        path = path.replace(f"/{value}", f"/{{{name}}}", 1)
    return path


class RequestIdMiddleware:
    """Attach a request ID to the request, every log line it emits, and the response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and len(incoming) <= 128 else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            path = _route_template(scope)
            method = scope["method"]
            metrics.HTTP_REQUESTS.labels(method=method, path=path, status=str(status_code)).inc()
            metrics.HTTP_LATENCY.labels(method=method, path=path).observe(elapsed)
            if path != "/metrics":
                logger.info(
                    "request",
                    extra={
                        "method": method,
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": round(elapsed * 1000, 2),
                        "client": (scope.get("client") or ("-",))[0],
                    },
                )
            request_id_ctx.reset(token)


class ApiKeyMiddleware:
    """Optional API-key auth. A wrong key is always rejected; a missing key only when required."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or _exempt(scope["path"]):
            await self.app(scope, receive, send)
            return

        key = extract_api_key(Headers(scope=scope))
        authenticated = is_valid_key(key, self.settings.api_keys)
        if key and not authenticated:
            await _send_json(send, 401, {"detail": "Invalid API key"}, {"WWW-Authenticate": "ApiKey"})
            return
        if self.settings.require_api_key and not authenticated:
            await _send_json(send, 401, {"detail": "API key required"}, {"WWW-Authenticate": "ApiKey"})
            return

        scope.setdefault("state", {})["authenticated"] = authenticated
        await self.app(scope, receive, send)
