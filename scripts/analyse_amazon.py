"""Run the analysis engine on one product from the Amazon Reviews 2023 dataset.

    python -m scripts.analyse_amazon --asin B0C1HHXQ94 --kind full [--change 2023-01-15:battery life]

Reviewer ids are never read. Prints the summary; --out saves the full report as JSON.
"""

import argparse
import json
from datetime import UTC, date, datetime

DEFAULT_FILE = "data/amazon2023/raw/review_categories/Health_and_Personal_Care.jsonl"


def load(path: str, asin: str):
    from app.analysis.engine import ReviewInput

    out = []
    with open(path) as f:
        for line in f:
            if f'"{asin}"' not in line:
                continue
            r = json.loads(line)
            if r["parent_asin"] != asin:
                continue
            text = " ".join(x for x in (r.get("title"), r.get("text")) if x).strip()
            if not text:
                continue
            day = datetime.fromtimestamp(r["timestamp"] / 1000, tz=UTC).date()
            out.append(
                ReviewInput(
                    id=f"{asin}-{len(out)}",
                    text=text[:2000],
                    rating=r.get("rating"),
                    reviewed_on=day,
                    source="amazon_2023",
                )
            )
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--asin", required=True)
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--kind", choices=["quick", "full"], default="full")
    ap.add_argument("--change", action="append", default=[], help="YYYY-MM-DD:aspect[,aspect]")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    from app.analysis.aspects import AspectMatcher, SentenceTransformerEncoder
    from app.analysis.engine import ChangeInput, analyse
    from app.core.config import Settings
    from app.services.inference import build_inference_service

    reviews = load(a.file, a.asin)
    print(
        f"{len(reviews)} reviews for {a.asin}, {min(r.reviewed_on for r in reviews)} to {max(r.reviewed_on for r in reviews)}"
    )
    changes = []
    for i, c in enumerate(a.change):
        d, asp = c.split(":", 1)
        changes.append(
            ChangeInput(f"c{i}", date.fromisoformat(d), [x.strip() for x in asp.split(",")], "logged change")
        )

    clf = build_inference_service(Settings(_env_file=None))
    enc = SentenceTransformerEncoder()
    report = analyse(
        reviews, clf, enc, AspectMatcher(enc), changes, kind=a.kind, progress=lambda s: print("  ..", s)
    )

    print("\nSUMMARY")
    for line in report["summary"]:
        print(" -", line)
    print("\nWHAT'S LACKING")
    for s in report["lacking"][:8]:
        imp = f"{s['rating_impact']:.3f}★" if s["rating_impact"] is not None else "-"
        subs = ", ".join(f"{x['name']} ({x['mentions']})" for x in s.get("specific_issues", []))
        print(
            f"  {s['aspect']:28} neg {s['negative']:4} ({s['negative_share']:.1%})  impact {imp:>7}  {('-> ' + subs) if subs else ''}"
        )
        if s["quotes"]:
            print(f"      “{s['quotes'][0]['text']}”")
    print("\nSTRENGTHS:", ", ".join(f"{s['aspect']} ({s['positive']})" for s in report["strengths"]))
    for al in report.get("alerts", []):
        print(
            f"ALERT {al['aspect']}: {al['current_rate']:.0%} vs {al['baseline_rate']:.0%} since {al['first_seen']}"
        )
    for fv in report.get("fix_verification", []):
        for r in fv["results"]:
            print(f"FIX {fv['changed_on']} {r['requested']} -> {r['verdict']}  {r.get('note', '')}")
    print(
        "\n", report["methodology"]["clauses_analysed"], "clauses in", report["methodology"]["seconds"], "s"
    )
    if a.out:
        with open(a.out, "w") as f:
            json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    main()
