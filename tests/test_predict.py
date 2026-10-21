def test_predict_positive(client):
    r = client.post("/api/v1/predict", json={"text": "Best product I have ever bought!"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "POSITIVE"
    assert 0.5 <= body["confidence"] <= 1
    assert "probabilities" not in body
    assert body["request_id"] == r.headers["x-request-id"]


def test_predict_negative_with_probabilities(client):
    r = client.post(
        "/api/v1/predict",
        json={"text": "Terrible quality, broke immediately.", "return_probabilities": True},
    )
    body = r.json()
    assert body["label"] == "NEGATIVE"
    assert set(body["probabilities"]) == {"NEGATIVE", "POSITIVE"}
    assert abs(sum(body["probabilities"].values()) - 1) < 1e-6


def test_predict_rejects_blank_text(client):
    assert client.post("/api/v1/predict", json={"text": "   "}).status_code == 422


def test_predict_rejects_missing_field(client):
    assert client.post("/api/v1/predict", json={}).status_code == 422


def test_predict_rejects_overlong_text(client):
    assert client.post("/api/v1/predict", json={"text": "a" * 6000}).status_code == 422


def test_batch_is_a_single_forward_pass(client, backend):
    texts = ["Great product!", "Terrible quality, broke immediately.", "It is a box."]
    r = client.post("/api/v1/batch", json={"texts": texts})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert [x["label"] for x in body["results"]] == ["POSITIVE", "NEGATIVE", body["results"][2]["label"]]
    assert backend.calls == [3]  # one forward pass, not a loop


def test_batch_rejects_too_many_texts(client):
    r = client.post("/api/v1/batch", json={"texts": ["ok"] * 33})
    assert r.status_code == 422
    assert "jobs/batch" in r.text


def test_batch_rejects_empty_list(client):
    assert client.post("/api/v1/batch", json={"texts": []}).status_code == 422


def test_health_and_ready(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["model_loaded"] is True
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_metrics_exposes_ml_counters(client):
    client.post("/api/v1/predict", json={"text": "Great product!"})
    text = client.get("/metrics").text
    assert "sentiment_predictions_total" in text
    assert "sentiment_prediction_confidence_bucket" in text
    assert 'http_requests_total{method="POST",path="/api/v1/predict",status="200"}' in text


def test_openapi_lists_versioned_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in [
        "/api/v1/predict",
        "/api/v1/batch",
        "/api/v1/jobs/batch",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/results",
    ]:
        assert p in paths


def test_predict_flags_uncertain_below_threshold(client):
    confident = client.post("/api/v1/predict", json={"text": "Best product I have ever bought!"}).json()
    unsure = client.post("/api/v1/predict", json={"text": "It is a box."}).json()  # stub scores 0.5
    assert confident["uncertain"] is False
    assert unsure["uncertain"] is True
    assert unsure["label"] in {"POSITIVE", "NEGATIVE"}  # best guess is still returned


def test_batch_items_carry_uncertain_flag(client):
    r = client.post("/api/v1/batch", json={"texts": ["Great product!", "It is a box."]})
    assert [x["uncertain"] for x in r.json()["results"]] == [False, True]
