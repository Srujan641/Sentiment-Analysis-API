"""Authentication and per-plan rate limiting for the /v1 platform API.

A caller is either a logged-in website user (session cookie) or a program (API key in
`Authorization: Bearer ...` or `X-API-Key`). Both resolve to a Principal scoped to one org.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, Response, status
from limits import parse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.models import ApiKey, Organization, User, WebSession
from app.platform.plans import Plan, get_plan
from app.platform.security import sha256

SESSION_COOKIE = "rp_session"


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat stored values as UTC."""
    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


@dataclass
class Principal:
    org: Organization
    user: User | None = None
    api_key: ApiKey | None = None

    @property
    def plan(self) -> Plan:
        return get_plan(self.org.plan)


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def _from_api_key(db: Session, raw: str) -> Principal | None:
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == sha256(raw), ApiKey.revoked_at.is_(None)))
    if key is None:
        return None
    now = datetime.now(UTC)
    last = aware(key.last_used_at)
    if last is None or (now - last).total_seconds() > 60:  # avoid a write on every request
        key.last_used_at = now
        db.commit()
    return Principal(org=db.get(Organization, key.org_id), api_key=key)


def _from_session(db: Session, token: str) -> Principal | None:
    sess = db.get(WebSession, sha256(token))
    if sess is None:
        return None
    if aware(sess.expires_at) < datetime.now(UTC):
        db.delete(sess)
        db.commit()
        return None
    user = db.get(User, sess.user_id)
    return Principal(org=user.org, user=user) if user else None


def _raw_key(request: Request) -> str | None:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() if auth.lower().startswith("bearer ") else None


def _rate_limit(request: Request, response: Response, principal: Principal) -> None:
    limiter = request.app.state.platform_limiter
    limit = parse(principal.plan.rate_limit)
    identity = f"key:{principal.api_key.id}" if principal.api_key else f"user:{principal.user.id}"
    allowed = limiter.hit(limit, "v1", identity)
    reset_at, remaining = limiter.get_window_stats(limit, "v1", identity)
    response.headers["X-RateLimit-Limit"] = str(limit.amount)
    response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
    if not allowed:
        retry = max(int(reset_at - datetime.now(UTC).timestamp()), 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit of {principal.plan.rate_limit} for the {principal.plan.name} plan exceeded",
            headers={"Retry-After": str(retry)},
        )


def get_principal(request: Request, response: Response, db: Session = Depends(get_db)) -> Principal:
    raw = _raw_key(request)
    if raw:
        principal = _from_api_key(db, raw)
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
    else:
        token = request.cookies.get(SESSION_COOKIE)
        principal = _from_session(db, token) if token else None
        if principal is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Authentication required: send an API key or log in",
                headers={"WWW-Authenticate": "Bearer"},
            )
    _rate_limit(request, response, principal)
    return principal


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    """For account management (keys, settings): only a logged-in person, never an API key."""
    if principal.user is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action requires logging in on the website")
    return principal


def auth_rate_limit(request: Request) -> None:
    """Brute-force protection for signup and login, per client IP."""
    limiter = request.app.state.platform_limiter
    limit = parse(request.app.state.settings.auth_rate_limit)
    ip = request.client.host if request.client else "unknown"
    if not limiter.hit(limit, "auth", ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Wait a minute and try again."
        )
