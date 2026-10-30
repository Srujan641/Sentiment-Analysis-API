"""Monte Carlo check of fix verification and early warning (requirements section 8).

    python -m scripts.simulate_stats --sims 300

Fix verification: power to detect a real 30% / 40% reduction, and the false-positive rate
when nothing changed (including a pre-existing downward trend that must NOT be credited).
Early warning: detection rate and delay for a jump, and false alarms on a stable stream.
"""

import argparse
import random
from datetime import date, timedelta

from app.analysis.stats import scan, verify_fix, weekly

START, CHANGE = date(2026, 1, 5), date(2026, 4, 6)


def fix_stream(rng, n, base, rel_effect, trend_per_week=0.0):
    ds, es = [], []
    for _ in range(n):
        d = START + timedelta(days=rng.randint(0, 181))
        weeks = (d - START).days / 7
        rate = max(0.001, base + trend_per_week * weeks)
        if d >= CHANGE:
            rate *= 1 + rel_effect
        ds.append(d)
        es.append(int(rng.random() < rate))
    return ds, es


def fix_trial(rng, sims, n, base, rel_effect, trend=0.0):
    verdicts = [verify_fix(*fix_stream(rng, n, base, rel_effect, trend), CHANGE).verdict for _ in range(sims)]
    return {v: verdicts.count(v) / sims for v in set(verdicts)}


def ews_trial(rng, sims, per_week, base, jump, jump_week=20, weeks=26):
    detected, delays, false_alarm_runs = 0, [], 0
    for _ in range(sims):
        ds, es = [], []
        for wk in range(weeks):
            rate = base * (jump if wk >= jump_week else 1)
            for _ in range(rng.randint(int(per_week * 0.7), int(per_week * 1.3))):
                ds.append(START + timedelta(days=7 * wk + rng.randint(0, 6)))
                es.append(int(rng.random() < rate))
        alerts = scan(weekly(ds, es))
        jump_monday = START + timedelta(days=7 * jump_week)
        before = [a for a in alerts if a.week < jump_monday]
        after = [a for a in alerts if a.week >= jump_monday]
        false_alarm_runs += bool(before)
        if after:
            detected += 1
            delays.append((after[0].week - jump_monday).days // 7)
    return detected / sims, (sum(delays) / len(delays) if delays else None), false_alarm_runs / sims


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)

    print("FIX VERIFICATION  (reviews over 26 weeks, change at week 13)")
    for label, n, base, eff, trend in [
        ("real -30%, 900 reviews, base 25%", 900, 0.25, -0.30, 0.0),
        ("real -40%, 600 reviews, base 25%", 600, 0.25, -0.40, 0.0),
        ("real -30%, 400 reviews, base 25%", 400, 0.25, -0.30, 0.0),
        ("no change, 900 reviews", 900, 0.25, 0.0, 0.0),
        ("no change but already falling 1pt/week", 900, 0.35, 0.0, -0.01),
    ]:
        r = fix_trial(rng, a.sims, n, base, eff, trend)
        print(
            f"  {label:42} improved={r.get('improved', 0):.2f}  worse={r.get('worse', 0):.2f}  "
            f"no change={r.get('no_significant_change', 0):.2f}  inconclusive={r.get('inconclusive', 0):.2f}"
        )

    print("\nEARLY WARNING  (8-week baseline; jump at week 20 of 26)")
    for label, per_week, base, jump in [
        ("40 reviews/wk, 5% -> 15%", 40, 0.05, 3.0),
        ("40 reviews/wk, 5% -> 10%", 40, 0.05, 2.0),
        ("15 reviews/wk, 5% -> 20%", 15, 0.05, 4.0),
        ("stable 5%, 40 reviews/wk", 40, 0.05, 1.0),
    ]:
        det, delay, fa = ews_trial(rng, a.sims, per_week, base, jump)
        d = f"{delay:.1f} wk" if delay is not None else "-"
        print(
            f"  {label:30} detected={det:.2f}  mean delay={d:>7}  runs with false alarm before jump={fa:.2f}"
        )


if __name__ == "__main__":
    main()
