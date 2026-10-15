from app.services.drift import DriftMonitor, histogram, psi
from app.services.inference import Prediction


def _pred(label, conf):
    return Prediction(label=label, confidence=conf, probabilities={})


def test_psi_identical_is_zero():
    assert psi([0.25] * 4, [0.25] * 4) == 0


def test_psi_detects_shift():
    assert psi([0.5, 0.5], [0.9, 0.1]) > 0.25


def test_histogram_open_ended_bins():
    assert histogram([1, 5, 15, 100], [10, 50]) == [0.5, 0.25, 0.25]


def test_report_stable_vs_drift(reference_file):
    mon = DriftMonitor(reference_file, window=200)
    assert mon.report()["status"] == "no_data"

    # Matches the reference shape roughly: varied lengths, mixed labels.
    texts = ["x" * n for n in (10, 30, 70, 150, 300)] * 20
    preds = [
        _pred("POSITIVE" if i % 2 else "NEGATIVE", c) for i, c in enumerate([0.5, 0.7, 0.85, 0.92, 0.97] * 20)
    ]
    mon.record(texts, preds)
    assert mon.report()["status"] in ("stable", "warning")

    # Everything short, all negative, low confidence -> drift.
    mon2 = DriftMonitor(reference_file, window=200)
    mon2.record(["bad"] * 100, [_pred("NEGATIVE", 0.55)] * 100)
    report = mon2.report()
    assert report["status"] == "drift"
    assert report["psi"]["label"] > 0.25


def test_record_writes_jsonl(tmp_path, reference_file):
    log = tmp_path / "preds.jsonl"
    mon = DriftMonitor(reference_file, log_path=str(log))
    mon.record(["great"], [_pred("POSITIVE", 0.9)])
    assert '"label": "POSITIVE"' in log.read_text()


def test_missing_reference(tmp_path):
    mon = DriftMonitor(str(tmp_path / "nope.json"))
    mon.record(["great"], [_pred("POSITIVE", 0.9)])
    assert mon.report()["status"] == "no_reference"


def test_drift_endpoint(client):
    client.post("/api/v1/batch", json={"texts": ["Great!", "Terrible."]})
    r = client.get("/api/v1/monitoring/drift").json()
    assert r["window_size"] == 2
    assert "psi" in r
