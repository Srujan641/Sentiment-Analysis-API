"""Daily Evidently AI drift report: live predictions vs. the training reference.

    python -m scripts.drift_report                          # last 24h of data/predictions.jsonl
    python -m scripts.drift_report --hours 168 --out reports/

Writes an HTML report plus a JSON summary and exits with code 2 when drift is detected,
so a cron job or CI schedule can alert (or kick off retraining) on a non-zero exit.

    # crontab: every day at 06:00
    0 6 * * * cd /srv/sentiment-api && .venv/bin/python -m scripts.drift_report || notify-retrain
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

FEATURES = ["text_length", "word_count", "confidence", "label"]


def load_current(path: Path, hours: int) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"no prediction log at {path}; is PREDICTION_LOG_PATH set on the API?")
    df = pd.read_json(path, lines=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    return df[df["ts"] >= cutoff][FEATURES]


def run_evidently(reference: pd.DataFrame, current: pd.DataFrame, html_path: Path) -> dict:
    """Supports both the current (>=0.7) and legacy Evidently APIs."""
    try:
        from evidently import DataDefinition, Dataset, Report
        from evidently.presets import DataDriftPreset

        definition = DataDefinition(
            numerical_columns=["text_length", "word_count", "confidence"], categorical_columns=["label"]
        )
        snapshot = Report([DataDriftPreset()]).run(
            current_data=Dataset.from_pandas(current, data_definition=definition),
            reference_data=Dataset.from_pandas(reference, data_definition=definition),
        )
        snapshot.save_html(str(html_path))
        share, columns = 0.0, {}
        for m in snapshot.dict()["metrics"]:
            name = str(m.get("metric_name") or m.get("metric_id", ""))
            if name.startswith("DriftedColumnsCount"):
                share = float(m["value"]["share"])
            elif name.startswith("ValueDrift(column="):
                col = name.split("column=", 1)[1].split(",", 1)[0]
                columns[col] = {"test": name.split("method=", 1)[1].split(",", 1)[0], "p_value": m["value"]}
        return {
            "drifted_share": share,
            "dataset_drift": share >= 0.5,
            "columns": columns,
            "engine": "evidently>=0.7",
        }
    except ImportError:
        from evidently.metric_preset import DataDriftPreset
        from evidently.report import Report

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=reference, current_data=current)
        report.save_html(str(html_path))
        res = report.as_dict()["metrics"][0]["result"]
        return {
            "drifted_share": float(res["share_of_drifted_columns"]),
            "dataset_drift": bool(res["dataset_drift"]),
            "engine": "evidently-legacy",
        }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reference", default="models/distilbert-sentiment/reference_sample.csv")
    p.add_argument("--current", default="data/predictions.jsonl")
    p.add_argument("--hours", type=int, default=24)
    p.add_argument("--min_rows", type=int, default=200)
    p.add_argument("--out", default="reports")
    args = p.parse_args(argv)

    ref_path = Path(args.reference)
    if not ref_path.exists():
        raise SystemExit(f"no reference sample at {ref_path}; it is written by scripts/train.py")
    reference = pd.read_csv(ref_path)[FEATURES]
    current = load_current(Path(args.current), args.hours)

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if len(current) < args.min_rows:
        print(f"only {len(current)} predictions in the last {args.hours}h (< {args.min_rows}); skipping")
        return 0

    summary = run_evidently(reference, current, out / f"drift-{stamp}.html")
    summary |= {
        "date": stamp,
        "window_hours": args.hours,
        "reference_rows": len(reference),
        "current_rows": len(current),
        "current_positive_rate": round(float((current["label"] == "POSITIVE").mean()), 4),
        "reference_positive_rate": round(float((reference["label"] == "POSITIVE").mean()), 4),
    }
    (out / f"drift-{stamp}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if summary["dataset_drift"]:
        print("DRIFT DETECTED: collect fresh labelled data and retrain", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
