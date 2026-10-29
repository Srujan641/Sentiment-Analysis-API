"""Monthly quota tracking and enforcement (requirements ACC-6..8)."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform.models import Organization, Product, UsageCounter
from app.platform.plans import get_plan

METRICS = ("reviews_ingested", "reports_generated")


def current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def get_count(db: Session, org_id: str, metric: str, period: str | None = None) -> int:
    row = db.get(UsageCounter, (org_id, period or current_period(), metric))
    return row.count if row else 0


def add(db: Session, org_id: str, metric: str, amount: int) -> None:
    period = current_period()
    row = db.get(UsageCounter, (org_id, period, metric))
    if row is None:
        row = UsageCounter(org_id=org_id, period=period, metric=metric, count=0)
        db.add(row)
    row.count += amount


def _limit_for(org: Organization, metric: str) -> int | None:
    plan = get_plan(org.plan)
    return {"reviews_ingested": plan.reviews_per_month, "reports_generated": plan.reports_per_month}[metric]


def remaining(db: Session, org: Organization, metric: str) -> int | None:
    limit = _limit_for(org, metric)
    return None if limit is None else max(limit - get_count(db, org.id, metric), 0)


def ensure_product_slot(db: Session, org: Organization) -> None:
    limit = get_plan(org.plan).max_products
    if limit is None:
        return
    active = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.org_id == org.id, Product.archived_at.is_(None))
    )
    if active >= limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Your {get_plan(org.plan).name} plan allows {limit} active product(s). "
            "Archive one or upgrade your plan.",
        )


def summary(db: Session, org: Organization) -> dict:
    plan = get_plan(org.plan)
    if plan.audience == "individual":
        from app.platform.routes.research import daily_usage

        used, frees_at = daily_usage(db, org.id)
        return {
            "plan": plan.id,
            "audience": "individual",
            "research_today": {
                "used": used,
                "limit": plan.research_per_day,
                "next_free_at": frees_at.isoformat() if frees_at else None,
            },
            "rate_limit": plan.rate_limit,
        }
    products = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.org_id == org.id, Product.archived_at.is_(None))
    )
    return {
        "period": current_period(),
        "plan": plan.id,
        "audience": "business",
        "products": {"used": products, "limit": plan.max_products},
        "reviews_ingested": {
            "used": get_count(db, org.id, "reviews_ingested"),
            "limit": plan.reviews_per_month,
        },
        "reports_generated": {
            "used": get_count(db, org.id, "reports_generated"),
            "limit": plan.reports_per_month,
        },
        "rate_limit": plan.rate_limit,
    }
