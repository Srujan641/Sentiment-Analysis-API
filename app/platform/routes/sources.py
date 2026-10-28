"""Review sources: discover, add, remove, and collect (ING-3..7, ING-10)."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.policy import check_url
from app.platform.deps import Principal, get_db, get_polling_principal, get_principal
from app.platform.models import CollectionRun, ProductSource
from app.platform.routes.products import owned_product

router = APIRouter(tags=["sources"])
MAX_SOURCES = 25


class ConnectorOut(BaseModel):
    name: str
    label: str
    available: bool
    requires: str | None


class CandidateOut(BaseModel):
    connector: str
    ref: str
    label: str
    url: str | None
    detail: str | None
    allowed: bool
    reason: str | None


class SourceIn(BaseModel):
    connector: str
    ref: str = Field(..., min_length=1, max_length=500)
    label: str | None = Field(None, max_length=300)
    url: str | None = Field(None, max_length=1000)


class SourceOut(BaseModel):
    id: str
    connector: str
    ref: str
    label: str
    url: str | None
    last_collected_at: datetime | None
    last_added: int | None
    last_error: str | None


class RunOut(BaseModel):
    id: str
    product_id: str
    status: str
    stage: str | None
    results: list[dict] | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    status_url: str


def _connectors(request: Request) -> dict:
    return request.app.state.connectors


def _source_out(s: ProductSource) -> SourceOut:
    return SourceOut(
        id=s.id,
        connector=s.connector,
        ref=s.ref,
        label=s.label,
        url=s.url,
        last_collected_at=s.last_collected_at,
        last_added=s.last_added,
        last_error=s.last_error,
    )


def _run_out(r: CollectionRun) -> RunOut:
    return RunOut(
        id=r.id,
        product_id=r.product_id,
        status=r.status,
        stage=r.stage,
        results=json.loads(r.results) if r.results else None,
        error=r.error,
        created_at=r.created_at,
        finished_at=r.finished_at,
        status_url=f"/v1/collections/{r.id}",
    )


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors(request: Request, p: Principal = Depends(get_principal)):
    return [
        ConnectorOut(name=c.name, label=c.label, available=c.available(), requires=c.requires)
        for c in _connectors(request).values()
    ]


@router.get("/products/{product_id}/sources/suggest", response_model=list[CandidateOut])
def suggest_sources(
    product_id: str,
    request: Request,
    connector: str = Query(...),
    q: str | None = Query(None, max_length=200, description="Search text; defaults to the product name"),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """Find candidate sources for a product with one connector. Nothing is collected yet."""
    product = owned_product(db, p, product_id)
    c = _connectors(request).get(connector)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown connector '{connector}'")
    if not c.available():
        raise HTTPException(status.HTTP_409_CONFLICT, f"{c.label} isn't set up: {c.requires}")
    try:
        found = c.discover(q or product.name)
    except ConnectorError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - upstream API failure
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"{c.label} search failed; try again shortly."
        ) from exc
    return [CandidateOut(**vars(x)) for x in found]


@router.get("/products/{product_id}/sources", response_model=list[SourceOut])
def list_sources(product_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    owned_product(db, p, product_id)
    rows = db.scalars(
        select(ProductSource).where(ProductSource.product_id == product_id).order_by(ProductSource.created_at)
    )
    return [_source_out(s) for s in rows]


@router.post("/products/{product_id}/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def add_source(
    product_id: str,
    body: SourceIn,
    request: Request,
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    owned_product(db, p, product_id)
    c = _connectors(request).get(body.connector)
    if c is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown connector '{body.connector}'")
    if body.connector == "web":
        allowed, reason = check_url(body.ref)
        if not allowed:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, reason)
    existing = db.scalars(select(ProductSource).where(ProductSource.product_id == product_id)).all()
    if any(s.connector == body.connector and s.ref == body.ref for s in existing):
        raise HTTPException(status.HTTP_409_CONFLICT, "This source is already added")
    if len(existing) >= MAX_SOURCES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"At most {MAX_SOURCES} sources per product")
    src = ProductSource(
        org_id=p.org.id,
        product_id=product_id,
        connector=body.connector,
        ref=body.ref,
        label=body.label or body.ref,
        url=body.url or (body.ref if body.connector == "web" else None),
    )
    db.add(src)
    db.commit()
    return _source_out(src)


@router.delete("/products/{product_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_source(
    product_id: str, source_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    owned_product(db, p, product_id)
    src = db.get(ProductSource, source_id)
    if src is None or src.product_id != product_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    db.delete(src)
    db.commit()


@router.post("/products/{product_id}/collect", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def collect(
    product_id: str, request: Request, p: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    """Collect new reviews from all of the product's sources in the background."""
    owned_product(db, p, product_id)
    if not db.scalar(select(ProductSource.id).where(ProductSource.product_id == product_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Add at least one source first")
    if db.scalar(
        select(CollectionRun.id).where(
            CollectionRun.product_id == product_id, CollectionRun.status.in_(("queued", "running"))
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "A collection is already running for this product")
    run = CollectionRun(org_id=p.org.id, product_id=product_id)
    db.add(run)
    db.commit()
    request.app.state.analysis_runner.submit_collection(run.id)
    return _run_out(run)


@router.get("/collections/{run_id}", response_model=RunOut)
def get_collection(run_id: str, p: Principal = Depends(get_polling_principal), db: Session = Depends(get_db)):
    run = db.get(CollectionRun, run_id)
    if run is None or run.org_id != p.org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")
    return _run_out(run)
