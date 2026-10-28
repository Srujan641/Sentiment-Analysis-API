import random
import zlib
from datetime import date, timedelta

import numpy as np
import pytest

from app.analysis.aspects import AspectMatcher, discover, keyword_aspects
from app.analysis.engine import ChangeInput, ReviewInput, analyse
from app.analysis.segment import split_clauses
from app.analysis.stats import current_alert, verify_fix, weekly


class HashEncoder:
    """Deterministic bag-of-words embedding: similar wording -> similar vectors."""

    dim = 256

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim))
        for i, t in enumerate(texts):
            for w in t.lower().replace(",", " ").split():
                out[i, zlib.crc32(w.encode()) % self.dim] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


class Pred:
    def __init__(self, label, confidence):
        self.label, self.confidence = label, confidence


class KeywordClassifier:
    NEG = ("dies", "broke", "late", "bad", "terrible", "hurts", "stopped", "leaked")

    def predict(self, texts):
        return [
            Pred("NEGATIVE", 0.95) if any(w in t.lower() for w in self.NEG) else Pred("POSITIVE", 0.95)
            for t in texts
        ]


@pytest.fixture(scope="module")
def matcher():
    return AspectMatcher(HashEncoder())


# ---------------------------------------------------------------- segment / aspects
def test_split_clauses_on_contrast():
    assert split_clauses("Sound is great but the battery dies fast. Sad.") == [
        "Sound is great",
        "but the battery dies fast Sad",
    ]
    assert split_clauses("Fits well; mic is bad") == ["Fits well", "mic is bad"]
    assert split_clauses("Good") == ["Good"]


def test_keyword_aspects():
    assert keyword_aspects("the battery dies in 2 hours") == ["battery life"]
    assert "delivery" in keyword_aspects("delivery was late")
    assert keyword_aspects("case hinge is loose and weak") == []  # "loose" alone is not about fit


def test_discover_names_cluster():
    # Wording close enough for the toy bag-of-words encoder to cluster.
    clauses = ["the case hinge broke", "case hinge broke again", "case hinge broke off", "lovely colour"]
    issues = discover(clauses, HashEncoder().encode(clauses), min_size=3)
    assert issues and "hinge" in issues[0].name


# ---------------------------------------------------------------- stats
def _stream(rate_before, rate_after, change, n=900, seed=3):
    rng = random.Random(seed)
    ds, es = [], []
    for _ in range(n):
        d = change - timedelta(days=90) + timedelta(days=rng.randint(0, 180))
        ds.append(d)
        es.append(int(rng.random() < (rate_before if d < change else rate_after)))
    return ds, es


def test_verify_fix_detects_real_improvement():
    change = date(2026, 4, 6)
    r = verify_fix(*_stream(0.30, 0.12, change), change)
    assert r.verdict == "improved" and r.relative_change < 0 and r.p_value < 0.05
    assert r.ci_low < r.relative_change < r.ci_high


def test_verify_fix_false_positive_rate_and_not_enough_data():
    change = date(2026, 4, 6)
    # With no real change, a significant verdict should be rare (alpha = 0.05 two-sided).
    verdicts = [verify_fix(*_stream(0.2, 0.2, change, seed=s), change).verdict for s in range(40)]
    assert sum(v in ("improved", "worse") for v in verdicts) <= 5
    small = verify_fix(*_stream(0.3, 0.1, change, n=30), change)
    assert small.verdict == "not_enough_data" and "more reviews" in small.note


def test_early_warning_detects_jump_only_at_the_end():
    rng = random.Random(5)
    start = date(2026, 1, 5)
    ds, es = [], []
    for wk in range(14):
        rate = 0.04 if wk < 13 else 0.40
        for _ in range(40):
            ds.append(start + timedelta(days=7 * wk + rng.randint(0, 6)))
            es.append(int(rng.random() < rate))
    series = weekly(ds, es)
    alert = current_alert(series)
    assert alert is not None and alert.current_rate > 0.25
    assert current_alert({w: v for w, v in series.items() if w < max(series)}) is None


def test_weekly_fills_gaps():
    s = weekly([date(2026, 1, 5), date(2026, 1, 26)], [1, 0])
    assert len(s) == 4 and s[date(2026, 1, 12)] == (0, 0)


# ---------------------------------------------------------------- engine
def _reviews():
    rng = random.Random(1)
    start = date(2026, 1, 5)
    out = []
    for i in range(240):
        d = start + timedelta(days=i % 180)
        fixed = d >= date(2026, 4, 6)
        if rng.random() < (0.10 if fixed else 0.45):
            text, rating = "Sound is great but the battery dies in two hours", 2
        elif rng.random() < 0.15:
            text, rating = "Delivery was late and the box leaked", 3
        else:
            text, rating = "Love the sound and the price is fair", 5
        out.append(ReviewInput(id=f"r{i}", text=text, rating=rating, reviewed_on=d))
    return out


def test_quick_report_ranks_battery_first(matcher):
    r = analyse(_reviews(), KeywordClassifier(), HashEncoder(), matcher, kind="quick")
    assert r["review_count"] == 240
    assert r["lacking"][0]["aspect"] == "battery life"
    assert r["lacking"][0]["rating_impact"] > 0
    assert r["lacking"][0]["quotes"][0]["review_id"].startswith("r")
    assert any(s["aspect"] == "sound quality" for s in r["strengths"])
    assert "trends" not in r and "fix_verification" not in r
    assert "battery life" in " ".join(r["summary"])


def test_full_report_verifies_fix(matcher):
    change = ChangeInput("c1", date(2026, 4, 6), ["battery"], "new cells")
    r = analyse(_reviews(), KeywordClassifier(), HashEncoder(), matcher, changes=[change], kind="full")
    res = r["fix_verification"][0]["results"][0]
    assert res["aspect"] == "battery life"
    assert res["verdict"] == "improved"
    assert r["trends"] and r["trends"][0]["weeks"]
    assert isinstance(r["alerts"], list)


def test_empty_product(matcher):
    r = analyse([], KeywordClassifier(), HashEncoder(), matcher)
    assert r["review_count"] == 0 and r["lacking"] == []
