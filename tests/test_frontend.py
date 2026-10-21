from tests.conftest import make_client


def test_root_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Sentiment Analysis" in r.text
    assert "/static/app.js" in r.text


def test_static_assets_served(client):
    for path, kind in (("/static/app.js", "javascript"), ("/static/styles.css", "text/css")):
        r = client.get(path)
        assert r.status_code == 200
        assert kind in r.headers["content-type"]


def test_frontend_not_rate_limited(settings, backend):
    settings.rate_limit_anonymous = "1/minute"
    with make_client(settings, backend) as c:
        assert all(c.get(p).status_code == 200 for p in ["/", "/static/app.js", "/static/styles.css"] * 3)
