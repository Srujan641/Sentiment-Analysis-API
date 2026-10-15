import time


def _wait(client, job_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("complete", "failed"):
            return status
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_lifecycle(client, backend):
    texts = ["Great product!"] * 50 + ["Terrible, broke."] * 50
    r = client.post("/api/v1/jobs/batch", json={"texts": texts, "return_probabilities": True})
    assert r.status_code == 202
    submitted = r.json()
    assert submitted["total"] == 100
    assert submitted["status_url"] == f"/api/v1/jobs/{submitted['job_id']}"

    status = _wait(client, submitted["job_id"])
    assert status["status"] == "complete"
    assert status["processed"] == 100

    res = client.get(submitted["results_url"]).json()
    assert res["count"] == 100
    assert res["results"][0]["label"] == "POSITIVE"
    assert res["results"][-1]["label"] == "NEGATIVE"
    assert "probabilities" in res["results"][0]
    assert max(backend.calls) <= 32  # chunked into forward passes of batch_size


def test_job_limit_is_1000(client):
    assert client.post("/api/v1/jobs/batch", json={"texts": ["ok"] * 1001}).status_code == 422


def test_unknown_job_is_404(client):
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404
    assert client.get("/api/v1/jobs/does-not-exist/results").status_code == 404


def test_results_before_completion_is_409(client):
    from app.services.jobs import Job

    jobs = client.app.state.jobs
    job = Job(id="pending", texts=["x"])
    jobs._jobs[job.id] = job  # queued but never enqueued for the worker
    assert client.get("/api/v1/jobs/pending/results").status_code == 409
