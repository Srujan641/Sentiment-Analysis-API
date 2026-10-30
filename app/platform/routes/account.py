"""Usage and plans (ACC-6, ACC-8)."""

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.platform import usage
from app.platform.deps import Principal, get_db, get_principal
from app.platform.plans import PLANS

router = APIRouter(tags=["account"])


@router.get("/usage")
def get_usage(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return usage.summary(db, p.org)


@router.get("/plans")
def list_plans(audience: Literal["individual", "business"] | None = None):
    """Public: plan quotas and features (used by the pricing page)."""
    return [asdict(p) for p in PLANS.values() if audience is None or p.audience == audience]
