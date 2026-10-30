"""Products and logged product changes (PRD-1..3)."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform import usage
from app.platform.deps import Principal, get_business_principal, get_db
from app.platform.models import Product, ProductChange, Review
from app.platform.schemas import ChangeIn, ChangeOut, ProductIn, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


def owned_product(db: Session, p: Principal, product_id: str) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.org_id != p.org.id:  # 404, not 403: don't reveal other tenants' ids
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def _out(db: Session, product: Product) -> ProductOut:
    count = db.scalar(select(func.count()).select_from(Review).where(Review.product_id == product.id))
    return ProductOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        identifiers=json.loads(product.identifiers or "{}"),
        links=json.loads(product.links or "[]"),
        review_count=count,
        archived=product.archived_at is not None,
        created_at=product.created_at,
    )


@router.get("", response_model=list[ProductOut])
def list_products(
    include_archived: bool = Query(False),
    p: Principal = Depends(get_business_principal),
    db: Session = Depends(get_db),
):
    q = select(Product).where(Product.org_id == p.org.id)
    if not include_archived:
        q = q.where(Product.archived_at.is_(None))
    return [_out(db, x) for x in db.scalars(q.order_by(Product.created_at.desc())).all()]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductIn, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    usage.ensure_product_slot(db, p.org)
    product = Product(
        org_id=p.org.id,
        name=body.name.strip(),
        brand=body.brand,
        category=body.category,
        identifiers=json.dumps(body.identifiers),
        links=json.dumps(body.links),
    )
    db.add(product)
    db.commit()
    return _out(db, product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    return _out(db, owned_product(db, p, product_id))


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str,
    body: ProductUpdate,
    p: Principal = Depends(get_business_principal),
    db: Session = Depends(get_db),
):
    product = owned_product(db, p, product_id)
    data = body.model_dump(exclude_unset=True)
    for field in ("name", "brand", "category"):
        if field in data:
            setattr(product, field, data[field])
    if "identifiers" in data:
        product.identifiers = json.dumps(data["identifiers"] or {})
    if "links" in data:
        product.links = json.dumps(data["links"] or [])
    db.commit()
    return _out(db, product)


@router.delete("/{product_id}", response_model=ProductOut)
def archive_product(
    product_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    """Archive (soft delete): frees a plan slot, keeps the review history."""
    product = owned_product(db, p, product_id)
    if product.archived_at is None:
        product.archived_at = datetime.now(UTC)
        db.commit()
    return _out(db, product)


def _change_out(c: ProductChange) -> ChangeOut:
    return ChangeOut(
        id=c.id,
        changed_on=c.changed_on,
        aspects=json.loads(c.aspects),
        description=c.description,
        created_at=c.created_at,
    )


@router.get("/{product_id}/changes", response_model=list[ChangeOut])
def list_changes(
    product_id: str, p: Principal = Depends(get_business_principal), db: Session = Depends(get_db)
):
    return [_change_out(c) for c in owned_product(db, p, product_id).changes]


@router.post("/{product_id}/changes", response_model=ChangeOut, status_code=status.HTTP_201_CREATED)
def log_change(
    product_id: str,
    body: ChangeIn,
    p: Principal = Depends(get_business_principal),
    db: Session = Depends(get_db),
):
    """Log a change you shipped. Fix verification will test whether the named aspects improved."""
    product = owned_product(db, p, product_id)
    change = ProductChange(
        org_id=p.org.id,
        product_id=product.id,
        changed_on=body.changed_on,
        aspects=json.dumps(body.aspects),
        description=body.description.strip(),
    )
    db.add(change)
    db.commit()
    return _change_out(change)
