"""Analyses and reports (JOB-1, REP-1, REP-2)."""

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import usage
from app.platform.deps import Principal, get_business_polling_principal, get_business_principal, get_db
from app.platform.models import Analysis
from app.platform.routes.products import owned_product

router = APIRouter(tags=["analyses"])


class AnalysisRequest(BaseModel):
    kind: Literal["quick", "full"] = "quick"


class AnalysisOut(BaseModel):
    id: str
    product_id: str
    kind: str
    status: str
    stage: str | None
    error: str | None
    review_count: int | None
    created_at: datetime
    finished_at: datetime | None
    status_url: str
    report_url: str


def _out(a: Analysis) -> AnalysisOut:
    return AnalysisOut(
        id=a.id,
        product_id=a.product_id,
        kind=a.kind,
        status=a.status,
        stage=a.stage,
        error=a.error,
        review_count=a.review_count,
        created_at=a.created_at,
        finished_at=a.finished_at,
        status_url=f"/v1/analyses/{a.id}",
        report_url=f"/v1/analyses/{a.id}/report",
    )


def _owned(db: Session, p: Principal, analysis_id: str) -> Analysis:
    a = db.get(Analysis, analysis_id)
    if a is None or a.org_id != p.org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return a


@router.post(
    "/products/{product_id}/analyses", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED
)
def start_analysis(
    product_id: str,
    body: AnalysisRequest,
    request: Request,
    p: Principal = Depends(get_business_principal),
    db: Session = Depends(get_db),
):
    """Start an analysis. Quick: issues and strengths. Full (paid plans): plus trends,
    fix verification and early warning. Returns immediately; poll `status_url`."""
    owned_product(db, p, product_id)
    if body.kind == "full" and not p.plan.full_reports:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Full reports (trends, fix verification, early warning) need a paid plan; you're on {p.plan.name}.",
        )
    running = db.scalar(
        select(Analysis).where(Analysis.product_id == product_id, Analysis.status.in_(("queued", "running")))
    )
    if running:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"An analysis is already {running.status} for this product"
        )
    left = usage.remaining(db, p.org, "reports_generated")
    if left == 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You've used all reports on the {p.plan.name} plan this month.",
        )

    a = Analysis(org_id=p.org.id, product_id=product_id, kind=body.kind)
    db.add(a)
    usage.add(db, p.org.id, "reports_generated", 1)
    db.commit()
    request.app.state.analysis_runner.submit(a.id)
    return _out(a)


@router.get("/products/{product_id}/analyses", response_model=list[AnalysisOut])
def list_analyses(
    product_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    owned_product(db, p, product_id)
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.product_id == product_id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
    )
    return [_out(a) for a in rows]


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: str, p: Principal = Depends(get_business_polling_principal), db: Session = Depends(get_db)
):
    """Status of an analysis. Poll freely: this has its own limit (120/min), separate from your plan's."""
    return _out(_owned(db, p, analysis_id))


@router.get("/analyses/{analysis_id}/report")
def get_report(
    analysis_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    a = _owned(db, p, analysis_id)
    if a.status != "complete":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Analysis is {a.status}; poll /v1/analyses/{a.id}")
    return {"analysis_id": a.id, "product_id": a.product_id, **json.loads(a.report)}


@router.get("/products/{product_id}/insights")
def latest_insights(
    product_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    """The most recent completed report for a product."""
    owned_product(db, p, product_id)
    a = db.scalar(
        select(Analysis)
        .where(Analysis.product_id == product_id, Analysis.status == "complete")
        .order_by(Analysis.created_at.desc())
    )
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No completed analysis yet")
    return {"analysis_id": a.id, "product_id": a.product_id, **json.loads(a.report)}
