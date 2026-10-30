"""Plan definitions: quotas and feature flags (docs/REQUIREMENTS.md section 9).

Personal plans (individuals researching products) and business plans (brands analysing
their own products) are separate; an account only ever has a plan for its own audience.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    audience: str  # "individual" | "business"
    price_inr_month: int | None  # None = custom
    max_products: int | None  # None = unlimited
    reports_per_month: int | None
    reviews_per_month: int | None
    rate_limit: str
    full_reports: bool
    fix_verification: bool
    early_warning: bool
    webhooks: bool
    research_per_day: int | None = None  # personal plans only


PLANS: dict[str, Plan] = {
    p.id: p
    for p in (
        # personal
        Plan(
            "personal_free",
            "Personal Free",
            "individual",
            0,
            0,
            0,
            0,
            "30/minute",
            False,
            False,
            False,
            False,
            10,
        ),
        Plan(
            "personal_plus",
            "Personal Plus",
            "individual",
            299,
            0,
            0,
            0,
            "60/minute",
            False,
            False,
            False,
            False,
            100,
        ),
        # business
        Plan("free", "Business Free", "business", 0, 1, 3, 2_000, "30/minute", False, False, False, False),
        Plan("starter", "Starter", "business", 2_999, 5, 50, 25_000, "120/minute", True, True, True, False),
        Plan("growth", "Growth", "business", 9_999, 25, 300, 200_000, "300/minute", True, True, True, True),
        Plan(
            "enterprise",
            "Enterprise",
            "business",
            None,
            None,
            None,
            None,
            "1000/minute",
            True,
            True,
            True,
            True,
        ),
    )
}

DEFAULT_PLAN = {"individual": "personal_free", "business": "free"}


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id, PLANS["free"])


def default_plan(account_type: str) -> str:
    return DEFAULT_PLAN["individual" if account_type == "individual" else "business"]
