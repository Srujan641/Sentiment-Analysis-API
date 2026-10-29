"""Personal product research (individual accounts)."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform.deps import Principal, aware, get_db, get_personal_polling_principal, get_personal_principal
from app.platform.models import Research

router = APIRouter(prefix="/research", tags=["research"])
WINDOW = timedelta(hours=24)


class ResearchIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000, description="A product name, or a product link")


class ResearchOut(BaseModel):
    id: str
    query: str
    product_name: str | None
    identified_from: str | None
    status: str
    stage: str | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    result: dict | None = None
    status_url: str


def _out(r: Research, with_result: bool = True) -> ResearchOut:
    return ResearchOut(
        id=r.id,
        query=r.query,
        product_name=r.product_name,
        identified_from=r.identified_from,
        status=r.status,
        stage=r.stage,
        error=r.error,
        created_at=r.created_at,
        finished_at=r.finished_at,
        result=json.loads(r.result) if with_result and r.result else None,
        status_url=f"/v1/research/{r.id}",
    )


def daily_usage(db: Session, org_id: str) -> tuple[int, datetime | None]:
    """(researches in the last 24 h, when the oldest of them stops counting)."""
    since = datetime.now(UTC) - WINDOW
    rows = db.scalars(
        select(Research.created_at)
        .where(Research.org_id == org_id, Research.created_at >= since)
        .order_by(Research.created_at)
    ).all()
    return len(rows), (aware(rows[0]) + WINDOW if rows else None)


@router.post("", response_model=ResearchOut, status_code=status.HTTP_202_ACCEPTED)
def start_research(
    body: ResearchIn,
    request: Request,
    p: Principal = Depends(get_personal_principal),
    db: Session = Depends(get_db),
):
    """Research a product from its name or link. Personal Free allows 10 per 24 hours."""
    limit = p.plan.research_per_day
    used, frees_at = daily_usage(db, p.org.id)
    if limit is not None and used >= limit:
        when = frees_at.strftime("%H:%M UTC") if frees_at else "soon"
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've used all {limit} researches for today on {p.plan.name}. "
            f"The next one frees up at {when}, or upgrade to Personal Plus for more.",
        )
    active = db.scalar(
        select(func.count())
        .select_from(Research)
        .where(Research.org_id == p.org.id, Research.status.in_(("queued", "running")))
    )
    if active >= 2:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Two researches are already running; wait for one to finish."
        )
    r = Research(org_id=p.org.id, user_id=p.user.id if p.user else None, query=body.query.strip())
    db.add(r)
    db.commit()
    request.app.state.analysis_runner.submit_research(r.id)
    return _out(r)


@router.get("", response_model=list[ResearchOut])
def list_research(p: Principal = Depends(get_personal_principal), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Research).where(Research.org_id == p.org.id).order_by(Research.created_at.desc()).limit(50)
    )
    return [_out(r, with_result=False) for r in rows]


@router.get("/{research_id}", response_model=ResearchOut)
def get_research(
    research_id: str, p: Principal = Depends(get_personal_polling_principal), db: Session = Depends(get_db)
):
    r = db.get(Research, research_id)
    if r is None or r.org_id != p.org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research not found")
    return _out(r)
