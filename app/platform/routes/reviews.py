"""Review ingestion: JSON push and file upload (ING-1, ING-2, ING-8, ING-9)."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform import usage
from app.platform.deps import Principal, get_db, get_principal
from app.platform.ingest import clean, parse_upload
from app.platform.models import Review
from app.platform.routes.products import owned_product
from app.platform.schemas import IngestResult, ReviewBatch, ReviewPage

router = APIRouter(prefix="/products/{product_id}/reviews", tags=["reviews"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_ROWS = 50_000


def _store(db: Session, p: Principal, product_id: str, raw_rows: list[dict], source: str) -> IngestResult:
    cleaned, rejected = [], 0
    for raw in raw_rows:
        r = clean(raw)
        if r is None:
            rejected += 1
        else:
            cleaned.append(r)

    # De-duplicate within the batch, then against what is already stored for this product.
    unique = {r.content_hash: r for r in cleaned}
    existing = set()
    hashes = list(unique)
    for i in range(0, len(hashes), 500):
        existing |= set(
            db.scalars(
                select(Review.content_hash).where(
                    Review.product_id == product_id, Review.content_hash.in_(hashes[i : i + 500])
                )
            )
        )
    new = [r for h, r in unique.items() if h not in existing]
    duplicates = len(cleaned) - len(new)

    left = usage.remaining(db, p.org, "reviews_ingested")
    if left is not None and len(new) > left:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"This would add {len(new)} reviews but your {p.plan.name} plan has {left} left this month.",
        )

    db.add_all(
        Review(
            org_id=p.org.id,
            product_id=product_id,
            source=source,
            external_id=r.external_id,
            text=r.text,
            rating=r.rating,
            reviewed_on=r.reviewed_on,
            content_hash=r.content_hash,
        )
        for r in new
    )
    usage.add(db, p.org.id, "reviews_ingested", len(new))
    db.commit()
    return IngestResult(
        received=len(raw_rows),
        added=len(new),
        duplicates=duplicates,
        rejected=rejected,
        remaining_this_month=usage.remaining(db, p.org, "reviews_ingested"),
    )


@router.post("", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def push_reviews(
    product_id: str, body: ReviewBatch, p: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    """Push up to 1,000 reviews as JSON."""
    owned_product(db, p, product_id)
    rows = [r.model_dump() for r in body.reviews]
    return _store(db, p, product_id, rows, body.source)


@router.post("/upload", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
async def upload_reviews(
    product_id: str,
    file: UploadFile = File(..., description="CSV (with a text/review column) or JSON / JSONL"),
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """Upload a review export. Columns are matched by common names (text/review, rating/stars, date...)."""
    owned_product(db, p, product_id)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Files are limited to 10 MB")
    try:
        rows = parse_upload(file.filename or "upload.csv", data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No reviews found in the file")
    if len(rows) > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"At most {MAX_UPLOAD_ROWS:,} rows per file"
        )
    return _store(db, p, product_id, rows, "upload")


@router.get("", response_model=ReviewPage)
def list_reviews(
    product_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: str | None = None,
    p: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    owned_product(db, p, product_id)
    q = select(Review).where(Review.product_id == product_id, Review.org_id == p.org.id)
    if source:
        q = q.where(Review.source == source)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(
        q.order_by(Review.reviewed_on.desc().nulls_last(), Review.ingested_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ReviewPage(items=items, total=total, limit=limit, offset=offset)
