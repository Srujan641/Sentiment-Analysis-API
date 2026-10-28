"""Turn a product's reviews into a report.

reviews -> clauses -> sentiment per clause (fine-tuned DistilBERT)
        -> aspects per clause (keywords, embeddings) + discovered specific issues
        -> per-aspect counts, rating impact, quotes
        -> (full) weekly trends, fix verification per logged change, early-warning alerts
        -> grounded summary sentences built from the numbers (no LLM)
"""

import re
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from app.analysis import stats
from app.analysis.aspects import AspectMatcher, Encoder, discover
from app.analysis.segment import split_clauses
from app.analysis.taxonomy import ASPECTS

MAX_SUB_ISSUES = 5

_RANK = {"neutral": 0, "positive": 1, "negative": 2}
POLARITY_CONFIDENCE = 0.75  # below this a clause is treated as neutral
MIN_ISSUE_MENTIONS = 3
QUOTES_PER_ISSUE = 3
MAX_QUOTE_CHARS = 220


@dataclass
class ReviewInput:
    id: str
    text: str
    rating: float | None
    reviewed_on: date | None
    source: str = "upload"


@dataclass
class ChangeInput:
    id: str
    changed_on: date
    aspects: list[str]
    description: str


@dataclass
class _Clause:
    review: int
    text: str
    polarity: str = "neutral"  # positive | negative | neutral
    confidence: float = 0.0
    aspects: list[str] = field(default_factory=list)


class Classifier:
    """Anything with predict(texts) -> objects having .label and .confidence (InferenceService)."""

    def predict(self, texts: list[str]): ...


def analyse(
    reviews: Sequence[ReviewInput],
    classifier: Classifier,
    encoder: Encoder,
    matcher: AspectMatcher,
    changes: Sequence[ChangeInput] = (),
    kind: str = "quick",
    progress: Callable[[str], None] = lambda stage: None,
) -> dict:
    started = time.perf_counter()
    n = len(reviews)
    if n == 0:
        return _empty(kind)

    # ---------------------------------------------------------------- clauses + sentiment
    progress("reading reviews")
    clauses = [_Clause(i, c) for i, r in enumerate(reviews) for c in split_clauses(r.text)]
    clause_preds = classifier.predict([c.text for c in clauses])
    for c, p in zip(clauses, clause_preds, strict=True):
        c.confidence = float(p.confidence)
        if p.confidence >= POLARITY_CONFIDENCE:
            c.polarity = "negative" if p.label == "NEGATIVE" else "positive"
    review_preds = classifier.predict([r.text for r in reviews])

    # ---------------------------------------------------------------- aspects
    progress("finding aspects")
    emb = encoder.encode([c.text for c in clauses])
    for c, found in zip(clauses, matcher.match([c.text for c in clauses], emb), strict=True):
        c.aspects = found

    # Specific issues: cluster all negative clauses; a cluster mostly inside one aspect becomes
    # a sub-issue of it ("durability" -> "case hinge"), otherwise a new top-level issue.
    neg_idx = [i for i, c in enumerate(clauses) if c.polarity == "negative"]
    sub_issues: dict[str, list[tuple[str, list[int]]]] = defaultdict(list)
    corpus = [c.text for c in clauses]
    min_top_level = max(5, int(0.005 * n))
    product_words = _product_vocabulary([r.text for r in reviews])
    top_level: list[tuple[str, list[int]]] = []
    for issue in discover(
        [clauses[i].text for i in neg_idx], emb[neg_idx], MIN_ISSUE_MENTIONS, corpus, product_words
    ):
        members = [neg_idx[m] for m in issue.members]
        counts: dict[str, int] = defaultdict(int)
        for m in members:
            for a in clauses[m].aspects:
                counts[a] += 1
        parent = max(counts, key=counts.get) if counts else None
        if parent and counts[parent] >= 0.5 * len(members):
            parent_words = set(parent.split()) | {k for a in ASPECTS if a.name == parent for k in a.keywords}
            if not set(issue.name.split()) <= parent_words:  # "scent" under fragrance adds nothing
                sub_issues[parent].append((issue.name, members))
        elif len({clauses[m].review for m in members}) >= min_top_level:
            top_level.append((issue.name, members))
    for name, members in _merge_by_shared_word(top_level):
        for m in members:  # top-level discovered issue: label its clauses with it
            if name not in clauses[m].aspects:
                clauses[m].aspects.append(name)
    discovered_names = {a for c in clauses for a in c.aspects if a not in matcher.names}

    # ---------------------------------------------------------------- per-review aspect polarity
    review_aspects: list[dict[str, str]] = [{} for _ in range(n)]
    clauses_by_aspect: dict[str, list[int]] = defaultdict(list)
    for ci, c in enumerate(clauses):
        for a in c.aspects:
            clauses_by_aspect[a].append(ci)
            cur = review_aspects[c.review].get(a)
            if cur is None or _RANK[c.polarity] > _RANK[cur]:  # negative > positive > neutral
                review_aspects[c.review][a] = c.polarity

    ratings = np.array([r.rating if r.rating is not None else np.nan for r in reviews], dtype=float)
    rated = ~np.isnan(ratings)
    use_ratings = rated.mean() >= 0.5 and rated.sum() >= 10

    aspect_stats = []
    for a, cidx in clauses_by_aspect.items():
        mention = np.array([a in ra for ra in review_aspects])
        neg = np.array([ra.get(a) == "negative" for ra in review_aspects])
        pos = np.array([ra.get(a) == "positive" for ra in review_aspects])
        impact = None
        if use_ratings and neg.sum() >= 2 and (~mention & rated).sum() >= 2:
            gap = np.nanmean(ratings[~mention & rated]) - np.nanmean(ratings[neg & rated])
            impact = float(max(gap, 0.0) * neg.mean())  # average-rating points lost to this aspect
        aspect_stats.append(
            {
                "aspect": a,
                "discovered": a in discovered_names,
                "mentions": int(mention.sum()),
                "negative": int(neg.sum()),
                "positive": int(pos.sum()),
                "share": float(mention.mean()),
                "negative_share": float(neg.mean()),
                "negative_rate": float(neg.sum() / mention.sum()) if mention.sum() else 0.0,
                "rating_impact": impact,
                "_clauses": cidx,
                "_neg_mask": neg,
            }
        )

    def score(s):  # rank by stars lost when ratings exist, else by how common the complaint is
        return (
            s["rating_impact"] if s["rating_impact"] is not None else s["negative_share"] * s["negative_rate"]
        )

    lacking = sorted(
        (s for s in aspect_stats if s["negative"] >= MIN_ISSUE_MENTIONS), key=score, reverse=True
    )
    strengths = sorted(
        (s for s in aspect_stats if s["positive"] >= MIN_ISSUE_MENTIONS and s["positive"] > s["negative"]),
        key=lambda s: s["positive"] / n,
        reverse=True,
    )

    def quotes(cidx: list[int], polarity: str) -> list[dict]:
        cands = sorted(
            (ci for ci in cidx if clauses[ci].polarity == polarity), key=lambda ci: -clauses[ci].confidence
        )
        picked: list[int] = []
        for ci in cands:
            if all(float(emb[ci] @ emb[p]) < 0.9 for p in picked):
                picked.append(ci)
            if len(picked) == QUOTES_PER_ISSUE:
                break
        out = []
        for ci in picked:
            r = reviews[clauses[ci].review]
            text = clauses[ci].text
            out.append(
                {
                    "text": text if len(text) <= MAX_QUOTE_CHARS else text[: MAX_QUOTE_CHARS - 1] + "…",
                    "review_id": r.id,
                    "rating": r.rating,
                    "date": r.reviewed_on.isoformat() if r.reviewed_on else None,
                    "source": r.source,
                }
            )
        return out

    def public(s: dict, polarity: str) -> dict:
        out = {k: v for k, v in s.items() if not k.startswith("_")}
        out["quotes"] = quotes(s["_clauses"], polarity)
        if polarity == "negative":
            out["specific_issues"] = [
                {
                    "name": name,
                    "mentions": len({clauses[m].review for m in members}),
                    "quotes": quotes(members, "negative")[:2],
                }
                for name, members in sorted(sub_issues.get(s["aspect"], []), key=lambda x: -len(x[1]))[
                    :MAX_SUB_ISSUES
                ]
            ]
        return out

    pos_share = float(np.mean([p.label == "POSITIVE" for p in review_preds]))
    dated = [r for r in reviews if r.reviewed_on]
    report: dict = {
        "kind": kind,
        "generated_at": datetime.now(UTC).isoformat(),
        "review_count": n,
        "dated_reviews": len(dated),
        "period": {
            "from": min(r.reviewed_on for r in dated).isoformat() if dated else None,
            "to": max(r.reviewed_on for r in dated).isoformat() if dated else None,
        },
        "overall": {
            "positive_share": pos_share,
            "negative_share": 1 - pos_share,
            "sentiment_score": round((2 * pos_share - 1) * 100),
            "average_rating": float(np.nanmean(ratings)) if rated.any() else None,
            "rated_reviews": int(rated.sum()),
        },
        "lacking": [public(s, "negative") for s in lacking[: 5 if kind == "quick" else 15]],
        "strengths": [public(s, "positive") for s in strengths[: 3 if kind == "quick" else 8]],
    }

    if kind == "full":
        progress("checking trends and changes")
        by_aspect = {s["aspect"]: s for s in aspect_stats}
        dates = [r.reviewed_on for r in reviews]

        def series(a: str):
            mask = by_aspect[a]["_neg_mask"] if a in by_aspect else np.zeros(n, bool)
            d = [dates[i] for i in range(n) if dates[i]]
            e = [int(mask[i]) for i in range(n) if dates[i]]
            return d, e

        report["trends"] = (
            [
                {
                    "aspect": s["aspect"],
                    "weeks": [
                        {"week": w.isoformat(), "reviews": rv, "negative": ev}
                        for w, (rv, ev) in stats.weekly(*series(s["aspect"])).items()
                    ],
                }
                for s in lacking[:8]
            ]
            if dated
            else []
        )

        report["fix_verification"] = [
            _verify(ch, matcher, by_aspect, series, discovered_names) for ch in changes
        ]

        alerts = []
        for s in lacking:
            d, e = series(s["aspect"])
            alert = stats.current_alert(stats.weekly(d, e)) if d else None
            if alert:
                recent = [
                    ci
                    for ci in s["_clauses"]
                    if clauses[ci].polarity == "negative"
                    and reviews[clauses[ci].review].reviewed_on
                    and reviews[clauses[ci].review].reviewed_on >= alert.first_seen
                ]
                alerts.append(
                    {
                        "aspect": s["aspect"],
                        "first_seen": alert.first_seen.isoformat(),
                        "current_rate": alert.current_rate,
                        "baseline_rate": alert.baseline_rate,
                        "complaints": alert.current_events,
                        "reviews": alert.current_reviews,
                        "p_value": alert.p_value,
                        "quotes": quotes(recent, "negative"),
                    }
                )
        report["alerts"] = alerts

    report["summary"] = _summary(report)
    report["methodology"] = {
        "sentiment_model": "DistilBERT fine-tuned on 60k Amazon reviews (94.97% test accuracy)",
        "aspects": "keyword match, then sentence-embedding similarity (all-MiniLM-L6-v2); specific issues by clustering negative clauses",
        "rating_impact": "average star rating of reviews without the aspect minus those complaining about it, times the share complaining",
        "fix_verification": "logistic regression on review-level complaints before/after the change, trend-adjusted when a trend is "
        "detected, with a placebo check; a steady pre-existing decline can still be mistaken for an effect, so read verdicts "
        "alongside the weekly chart",
        "early_warning": "one-sided binomial test of the latest 1-2 weeks against the previous 8 weeks (alpha 0.002)",
        "clauses_analysed": len(clauses),
        "seconds": round(time.perf_counter() - started, 2),
    }
    return report


_WORD = re.compile(r"[a-z]{3,}")


def _product_vocabulary(texts: list[str], min_share: float = 0.10) -> set[str]:
    """Words in at least 10% of a product's reviews ("mat", "spray"): they describe the
    product, not a problem, so they never name an issue."""
    df: dict[str, int] = defaultdict(int)
    for t in texts:
        for w in set(_WORD.findall(t.lower())):
            df[w] += 1
    return {w for w, c in df.items() if c >= min_share * len(texts)}


def _merge_by_shared_word(issues: list[tuple[str, list[int]]]) -> list[tuple[str, list[int]]]:
    """“spray bottle” and “bottle defective” are one issue: merge names sharing a word,
    keeping the name of the larger cluster."""
    merged: list[tuple[str, list[int]]] = []
    for name, members in sorted(issues, key=lambda x: -len(x[1])):
        for i, (kept, kept_members) in enumerate(merged):
            if set(name.split()) & set(kept.split()):
                merged[i] = (kept, sorted(set(kept_members) | set(members)))
                break
        else:
            merged.append((name, list(members)))
    return merged


def _verify(ch: ChangeInput, matcher: AspectMatcher, by_aspect: dict, series, discovered: set[str]) -> dict:
    results = []
    for raw in ch.aspects:
        target = raw if raw in by_aspect else next((d for d in discovered if raw in d or d in raw), None)
        target = target or matcher.nearest(raw)
        if target is None:
            results.append(
                {
                    "requested": raw,
                    "aspect": None,
                    "verdict": "unknown_aspect",
                    "note": "No reviews mention this aspect yet.",
                }
            )
            continue
        d, e = series(target)
        r = stats.verify_fix(d, e, ch.changed_on)
        results.append(
            {"requested": raw, "aspect": target, **{k: getattr(r, k) for k in r.__dataclass_fields__}}
        )
    return {
        "change_id": ch.id,
        "changed_on": ch.changed_on.isoformat(),
        "description": ch.description,
        "results": results,
    }


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _summary(r: dict) -> list[str]:
    """Plain-language findings, each built directly from a number in the report."""
    out = []
    o = r["overall"]
    rating = f", average rating {o['average_rating']:.1f}★" if o["average_rating"] is not None else ""
    out.append(f"{_pct(o['positive_share'])} of {r['review_count']:,} reviews are positive{rating}.")
    if r["lacking"]:
        top = r["lacking"][0]
        line = f"The biggest problem is {top['aspect']}: {_pct(top['negative_share'])} of reviews complain about it"
        if top["rating_impact"]:
            line += f", costing an estimated {top['rating_impact']:.2f} stars of average rating"
        out.append(line + ".")
        if top.get("specific_issues"):
            out.append(
                f"Within {top['aspect']}, customers specifically mention “{top['specific_issues'][0]['name']}”."
            )
        if len(r["lacking"]) > 1:
            out.append("Next: " + ", ".join(s["aspect"] for s in r["lacking"][1:4]) + ".")
    if r["strengths"]:
        out.append("Customers praise " + ", ".join(s["aspect"] for s in r["strengths"][:3]) + ".")
    for a in r.get("alerts", []):
        out.append(
            f"Warning: complaints about {a['aspect']} rose to {_pct(a['current_rate'])} of recent reviews "
            f"(baseline {_pct(a['baseline_rate'])}) since {a['first_seen']}."
        )
    for fv in r.get("fix_verification", []):
        for res in fv["results"]:
            if res.get("verdict") == "improved":
                out.append(
                    f"The change on {fv['changed_on']} reduced {res['aspect']} complaints by about "
                    f"{abs(res['relative_change']) * 100:.0f}% (p = {res['p_value']:.3f})."
                )
            elif res.get("verdict") == "worse":
                out.append(f"After the change on {fv['changed_on']}, {res['aspect']} complaints increased.")
    return out


def _empty(kind: str) -> dict:
    return {
        "kind": kind,
        "generated_at": datetime.now(UTC).isoformat(),
        "review_count": 0,
        "lacking": [],
        "strengths": [],
        "summary": ["No reviews yet. Upload or push reviews, then run the analysis again."],
        "overall": None,
    }
