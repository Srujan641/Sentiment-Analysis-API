from tests.conftest import make_client


def test_request_id_is_generated_and_echoed(client):
    r = client.get("/health")
    assert len(r.headers["x-request-id"]) == 32
    r = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


def test_invalid_api_key_rejected(client):
    r = client.post("/api/v1/predict", json={"text": "good"}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_valid_api_key_gets_authenticated_tier(client):
    r = client.post("/api/v1/predict", json={"text": "good"}, headers={"X-API-Key": "test-key"})
    assert r.status_code == 200
    assert r.headers["x-ratelimit-tier"] == "authenticated"
    assert r.headers["x-ratelimit-limit"] == "5000"


def test_bearer_token_accepted(client):
    r = client.post("/api/v1/predict", json={"text": "good"}, headers={"Authorization": "Bearer test-key"})
    assert r.status_code == 200


def test_require_api_key(settings, backend):
    settings.require_api_key = True
    with make_client(settings, backend) as c:
        assert c.post("/api/v1/predict", json={"text": "good"}).status_code == 401
        assert c.get("/health").status_code == 200  # probes stay open


def test_rate_limit_tiers(settings, backend):
    settings.rate_limit_anonymous = "3/minute"
    settings.rate_limit_authenticated = "6/minute"
    with make_client(settings, backend) as c:
        anon = [c.post("/api/v1/predict", json={"text": "good"}).status_code for _ in range(4)]
        assert anon == [200, 200, 200, 429]
        keyed = [
            c.post("/api/v1/predict", json={"text": "good"}, headers={"X-API-Key": "test-key"}).status_code
            for _ in range(7)
        ]
        assert keyed == [200] * 6 + [429]


def test_rate_limit_rejects_before_inference(settings, backend):
    settings.rate_limit_anonymous = "1/minute"
    with make_client(settings, backend) as c:
        c.post("/api/v1/predict", json={"text": "good"})
        r = c.post("/api/v1/predict", json={"text": "good"})
        assert r.status_code == 429
        assert "retry-after" in r.headers
    assert backend.calls == [1]  # the rejected call never reached the model


def test_probes_are_not_rate_limited(settings, backend):
    settings.rate_limit_anonymous = "1/minute"
    with make_client(settings, backend) as c:
        assert all(c.get("/health").status_code == 200 for _ in range(5))


def test_cors_preflight(client):
    r = client.options(
        "/api/v1/predict",
        headers={"Origin": "https://example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] in ("*", "https://example.com")
