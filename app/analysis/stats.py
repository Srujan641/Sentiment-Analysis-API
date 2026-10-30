"""Fix verification and early warning (requirements FIX-1..3, EWS-1..2).

Both work on review-level events: for one aspect, each review either contains a negative
mention of it (1) or not (0), on a date.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

# ---------------------------------------------------------------------------- fix verification
MIN_REVIEWS_PER_SIDE = 30
MIN_EVENTS = 5
WINDOW_DAYS = 182  # up to ~26 weeks on each side of the change
ALPHA = 0.05


@dataclass
class FixResult:
    verdict: str  # improved | worse | no_significant_change | inconclusive | not_enough_data
    before_rate: float | None
    after_rate: float | None
    relative_change: float | None  # after/before - 1, model-based
    ci_low: float | None
    ci_high: float | None
    p_value: float | None
    reviews_before: int
    reviews_after: int
    method: str
    note: str


def verify_fix(dates: list[date], events: list[int], changed_on: date) -> FixResult:
    """Interrupted time series at review level.

    logit P(negative mention) = b0 + b1 * weeks_since_change + b2 * after_change

    b1 absorbs a pre-existing trend, so a complaint rate that was already falling is not
    credited to the change. A trend term costs a lot of power over short windows (it is
    nearly collinear with the step), so it is included only when the before-period itself
    shows a significant trend; otherwise the model compares levels before vs after.
    exp(b2) is the odds ratio of the shift; the reported relative change is the predicted
    rate just after the change versus the no-change counterfactual.
    """
    lo, hi = changed_on - timedelta(days=WINDOW_DAYS), changed_on + timedelta(days=WINDOW_DAYS)
    rows = [(d, e) for d, e in zip(dates, events, strict=True) if lo <= d < hi]
    before = [e for d, e in rows if d < changed_on]
    after = [e for d, e in rows if d >= changed_on]
    nb, na = len(before), len(after)
    rate_b = sum(before) / nb if nb else None
    rate_a = sum(after) / na if na else None

    if nb < MIN_REVIEWS_PER_SIDE or na < MIN_REVIEWS_PER_SIDE or sum(before) + sum(after) < MIN_EVENTS:
        need = max(0, MIN_REVIEWS_PER_SIDE - nb) + max(0, MIN_REVIEWS_PER_SIDE - na)
        return FixResult(
            "not_enough_data",
            rate_b,
            rate_a,
            None,
            None,
            None,
            None,
            nb,
            na,
            "none",
            f"Needs at least {MIN_REVIEWS_PER_SIDE} dated reviews on each side of the change and "
            f"{MIN_EVENTS} complaints in total" + (f" ({need} more reviews)." if need else "."),
        )

    t = np.array([(d - changed_on).days / 7.0 for d, _ in rows])
    post = (t >= 0).astype(float)
    y = np.array([e for _, e in rows], dtype=float)

    use_trend = _trend_needed(t, post, y)
    ones = np.ones_like(t)
    level = _fit(y, np.column_stack([ones, post]))
    if level is None:
        return _fisher(before, after, nb, na, rate_b, rate_a)
    fit, k = level, 1
    significant = level.pvalues[1] < ALPHA
    if use_trend:
        trended = _fit(y, np.column_stack([ones, t, post]))
        if trended is not None:
            # Agreement rule: with a trend present, both models must find a shift in the same
            # direction. Selecting the model and then testing with it alone inflates false
            # positives (measured: 10.5% vs 6.5% at alpha 0.05).
            significant = (
                significant
                and trended.pvalues[2] < ALPHA
                and np.sign(trended.params[2]) == np.sign(level.params[1])
            )
            fit, k = trended, 2

    b, se, p = fit.params[k], fit.bse[k], float(fit.pvalues[k])
    if not significant:
        p = max(p, float(level.pvalues[1]))
    base_logit = fit.params[0]  # at t = 0 (the change date), without the shift
    p0 = 1 / (1 + math.exp(-base_logit))

    def rel(shift: float) -> float:
        return (1 / (1 + math.exp(-(base_logit + shift)))) / p0 - 1

    verdict = "no_significant_change" if not significant else ("improved" if b < 0 else "worse")
    method = (
        "segmented logistic regression (level shift + trend)"
        if use_trend
        else "logistic regression (before vs after)"
    )
    note = (
        "The complaint rate was already trending before the change; the effect is measured against that trend."
        if use_trend
        else "No significant trend before the change; compared complaint rates before and after."
    )
    if verdict in ("improved", "worse") and _placebo_effect(t[post == 0], y[post == 0], same_sign_as=b):
        verdict = "inconclusive"
        note = (
            "Complaints were already moving the same way before the change (a placebo test at the midpoint "
            "of the before-period also shows a significant shift), so the change can't be credited reliably."
        )
    return FixResult(
        verdict, rate_b, rate_a, rel(b), rel(b - 1.96 * se), rel(b + 1.96 * se), p, nb, na, method, note
    )


def _fit(y: np.ndarray, X: np.ndarray):
    """Logistic regression, or None when it fails or separates (coefficients blow up)."""
    import statsmodels.api as sm

    try:
        fit = sm.GLM(y, X, family=sm.families.Binomial()).fit()
    except Exception:  # noqa: BLE001
        return None
    if not np.all(np.isfinite(fit.params)) or np.any(np.abs(fit.params) > 20):
        return None
    return fit


def _placebo_effect(t: np.ndarray, y: np.ndarray, same_sign_as: float) -> bool:
    """Run the same before/after test inside the before-period, at its midpoint."""
    if len(t) < 2 * MIN_REVIEWS_PER_SIDE or y.sum() < MIN_EVENTS:
        return False
    import statsmodels.api as sm

    fake = (t >= np.median(t)).astype(float)
    try:
        fit = sm.GLM(y, np.column_stack([np.ones_like(t), fake]), family=sm.families.Binomial()).fit()
    except Exception:  # noqa: BLE001
        return False
    return bool(fit.pvalues[1] < ALPHA and np.sign(fit.params[1]) == np.sign(same_sign_as))


def _trend_needed(t: np.ndarray, post: np.ndarray, y: np.ndarray) -> bool:
    """Likelihood-ratio test: does a time trend improve on the level-shift-only model?

    A one-time step leaves each side flat, so the trend adds nothing; a gradual decline
    shows up as slope within both sides, and the trend is kept so the decline isn't
    credited to the change.
    """
    import statsmodels.api as sm
    from scipy.stats import chi2

    ones = np.ones_like(t)
    try:
        small = sm.GLM(y, np.column_stack([ones, post]), family=sm.families.Binomial()).fit()
        big = sm.GLM(y, np.column_stack([ones, t, post]), family=sm.families.Binomial()).fit()
    except Exception:  # noqa: BLE001
        return False
    lr = 2 * (big.llf - small.llf)
    return bool(chi2.sf(max(lr, 0.0), 1) < ALPHA)


def _fisher(before, after, nb, na, rate_b, rate_a) -> FixResult:
    from scipy.stats import fisher_exact

    table = [[sum(before), nb - sum(before)], [sum(after), na - sum(after)]]
    _, p = fisher_exact(table)
    rel = (rate_a / rate_b - 1) if rate_b else None
    verdict = "no_significant_change" if p >= ALPHA else ("improved" if rate_a < rate_b else "worse")
    return FixResult(
        verdict,
        rate_b,
        rate_a,
        rel,
        None,
        None,
        float(p),
        nb,
        na,
        "Fisher's exact test",
        "Regression was unstable on this data; used an exact before/after test.",
    )


# ---------------------------------------------------------------------------- early warning
BASELINE_WEEKS = 8
CURRENT_WEEKS = 2
EWS_ALPHA = 0.002  # per window; tuned by scripts/simulate_stats.py for few false alarms
MIN_ALERT_EVENTS = 3
MIN_RATE_RATIO = 1.5


@dataclass
class Alert:
    week: date  # Monday of the latest week in the alert window
    first_seen: date
    current_rate: float
    baseline_rate: float
    current_events: int
    current_reviews: int
    p_value: float


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def weekly(dates: list[date], events: list[int]) -> dict[date, tuple[int, int]]:
    """{monday: (reviews, events)}, including empty weeks between the first and last date."""
    out: dict[date, list[int]] = {}
    for d, e in zip(dates, events, strict=True):
        w = week_start(d)
        out.setdefault(w, [0, 0])
        out[w][0] += 1
        out[w][1] += e
    if not out:
        return {}
    w, last = min(out), max(out)
    while w <= last:
        out.setdefault(w, [0, 0])
        w += timedelta(days=7)
    return {k: (v[0], v[1]) for k, v in sorted(out.items())}


def check_week(series: dict[date, tuple[int, int]], at: date) -> Alert | None:
    """Is the complaint rate in the last 1 or CURRENT_WEEKS weeks ending at `at` significantly
    above the BASELINE_WEEKS before them? One-sided binomial test against the baseline rate.
    Checking the single latest week catches a sudden jump in its first week; the two-week
    window catches slower rises."""
    for span in (1, CURRENT_WEEKS):
        alert = _check_window(series, at, span)
        if alert:
            return alert
    return None


def _check_window(series: dict[date, tuple[int, int]], at: date, span: int) -> Alert | None:
    from scipy.stats import binom

    weeks = sorted(series)
    if at not in series:
        return None
    i = weeks.index(at)
    cur = weeks[max(0, i - span + 1) : i + 1]
    base = weeks[max(0, i - span + 1 - BASELINE_WEEKS) : max(0, i - span + 1)]
    if len(base) < BASELINE_WEEKS // 2:
        return None
    n_c = sum(series[w][0] for w in cur)
    k_c = sum(series[w][1] for w in cur)
    n_b = sum(series[w][0] for w in base)
    k_b = sum(series[w][1] for w in base)
    if n_c == 0 or n_b == 0 or k_c < MIN_ALERT_EVENTS:
        return None
    # Smoothed baseline so a zero-complaint baseline doesn't make every complaint "significant".
    rate_b = (k_b + 0.5) / (n_b + 1)
    rate_c = k_c / n_c
    if rate_c < MIN_RATE_RATIO * rate_b + 0.02:
        return None
    p = float(binom.sf(k_c - 1, n_c, rate_b))
    if p >= EWS_ALPHA:
        return None
    first = next((w for w in cur if series[w][0] and series[w][1] / series[w][0] > rate_b), cur[0])
    return Alert(at, first, rate_c, k_b / n_b, k_c, n_c, p)


def scan(series: dict[date, tuple[int, int]]) -> list[Alert]:
    """Alerts at every week, as if the system had run weekly. Used for backtesting."""
    return [a for w in series if (a := check_week(series, w))]


def current_alert(series: dict[date, tuple[int, int]]) -> Alert | None:
    return check_week(series, max(series)) if series else None
