"""Plan definitions: quotas and feature flags (docs/REQUIREMENTS.md section 9)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_inr_month: int | None  # None = custom
    max_products: int | None  # None = unlimited
    reports_per_month: int | None
    reviews_per_month: int | None
    rate_limit: str
    full_reports: bool
    fix_verification: bool
    early_warning: bool
    webhooks: bool


PLANS: dict[str, Plan] = {
    p.id: p
    for p in (
        Plan("free", "Free", 0, 1, 3, 2_000, "30/minute", False, False, False, False),
        Plan("starter", "Starter", 2_999, 5, 50, 25_000, "120/minute", True, True, True, False),
        Plan("growth", "Growth", 9_999, 25, 300, 200_000, "300/minute", True, True, True, True),
        Plan("enterprise", "Enterprise", None, None, None, None, "1000/minute", True, True, True, True),
    )
}

DEFAULT_PLAN = "free"


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id, PLANS[DEFAULT_PLAN])
