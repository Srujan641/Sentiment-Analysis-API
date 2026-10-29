import time
from types import SimpleNamespace

import httpx
import pytest

from app.connectors import policy
from app.connectors.app_store import AppStoreConnector
from app.connectors.base import Candidate, ConnectorError, RawReview
from app.connectors.firecrawl import FirecrawlConnector
from app.main import create_app
from app.services.inference import InferenceService
from tests.test_analysis import HashEncoder

PASSWORD = "correct-horse-battery"


# ---------------------------------------------------------------- policy
@pytest.fixture(autouse=True)
def _clear_robots_cache():
    policy._robots_cache.clear()
    yield
    policy._robots_cache.clear()


def robots_client(body: str, status: int = 200):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, text=body)))


def test_policy_blocks_marketplaces_without_network():
    for url in [
        "https://www.amazon.in/dp/X",
        "https://amazon.com/x",
        "https://smile.amazon.co.uk/x",
        "https://www.flipkart.com/p/1",
        "https://www.myntra.com/x",
    ]:
        allowed, reason = policy.check_url(url, client=robots_client("", 500))
        assert not allowed and "terms prohibit" in reason


def test_policy_respects_robots():
    c = robots_client("User-agent: *\nDisallow: /private/\n")
    assert policy.check_url("https://blog.example/review", client=c) == (True, None)
    assert policy.check_url("https://blog.example/private/x", client=c)[0] is False
    assert policy.check_url("https://open.example/x", client=robots_client("", 404)) == (True, None)
    assert policy.check_url("https://locked.example/x", client=robots_client("", 403))[0] is False


# ---------------------------------------------------------------- app store
def test_app_store_parses_search_and_feed():
    def handler(req: httpx.Request):
        if req.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "trackId": 42,
                            "trackName": "Acme",
                            "sellerName": "Acme Ltd",
                            "userRatingCount": 1200,
                            "averageUserRating": 4.2,
                            "trackViewUrl": "https://apps.apple.com/app/id42",
                        }
                    ]
                },
            )
        if "page=1/" in req.url.path:
            return httpx.Response(
                200,
                json={
                    "feed": {
                        "entry": [
                            {
                                "im:rating": {"label": "2"},
                                "title": {"label": "Crashes"},
                                "content": {"label": "App crashes on login"},
                                "updated": {"label": "2026-10-20T10:00:00-07:00"},
                                "id": {"label": "r1"},
                                "im:version": {"label": "3.1"},
                            },
                        ]
                    }
                },
            )
        return httpx.Response(200, json={"feed": {}})

    c = AppStoreConnector("in", client=httpx.Client(transport=httpx.MockTransport(handler)))
    (cand,) = c.discover("acme")
    assert cand.ref == "in:42" and "1,200 ratings" in cand.detail
    (r,) = c.collect("in:42", "Acme")
    assert r.text == "Crashes. App crashes on login" and r.rating == 2 and r.extra["version"] == "3.1"
    assert r.reviewed_on.isoformat() == "2026-10-20"
    with pytest.raises(ConnectorError):
        c.collect("not-a-ref", "Acme")


# ---------------------------------------------------------------- firecrawl
class FakeFirecrawl:
    def __init__(self, page_json):
        self.page_json = page_json
        self.scraped = []

    def search(self, query, limit):
        return SimpleNamespace(
            web=[
                SimpleNamespace(
                    url="https://blog.example/acme-review", title="Acme review", description="..."
                ),
                SimpleNamespace(url="https://www.amazon.in/acme", title="Acme on Amazon", description=""),
            ]
        )

    def scrape(self, url, **kw):
        self.scraped.append(url)
        return SimpleNamespace(json=self.page_json)


def test_firecrawl_discover_flags_blocked_and_extracts(monkeypatch):
    monkeypatch.setattr(policy, "_robots", lambda origin, client=None: _allow_all())
    page = {
        "about_product": True,
        "reviews": [{"text": "Battery is weak", "rating": 2, "date": "2026-09-01"}, {"text": "x"}],
    }
    fake = FakeFirecrawl(page)
    c = FirecrawlConnector(api_key=None, client=fake)
    cands = c.discover("Acme earbuds")
    assert [x.allowed for x in cands] == [True, False]
    reviews = c.collect("https://blog.example/acme-review", "Acme earbuds")
    assert len(reviews) == 1 and reviews[0].rating == 2 and reviews[0].reviewed_on.isoformat() == "2026-09-01"
    with pytest.raises(ConnectorError):
        c.collect("https://www.amazon.in/acme", "Acme earbuds")
    assert fake.scraped == ["https://blog.example/acme-review"]  # blocked URL never sent to Firecrawl
    fake.page_json = {"about_product": False, "reviews": []}
    with pytest.raises(ConnectorError, match="doesn't contain customer reviews"):
        c.collect("https://blog.example/other", "Acme earbuds")


def test_firecrawl_unavailable_without_key():
    assert FirecrawlConnector(api_key=None).available() is False


def _allow_all():
    from urllib.robotparser import RobotFileParser

    p = RobotFileParser()
    p.allow_all = True
    return p


# ---------------------------------------------------------------- API flow
class FakeConnector:
    name, label, requires = "app_store", "Apple App Store", None

    def __init__(self, n=40, fail=False):
        self.n, self.fail = n, fail

    def available(self):
        return True

    def discover(self, query, limit=5):
        return [Candidate(self.name, "in:42", f"{query} app", detail="1,000 ratings")]

    def collect(self, ref, product_name, limit=500):
        if self.fail:
            raise ConnectorError("Source is down")
        return [RawReview(text=f"Review number {i} about {product_name}", rating=4) for i in range(self.n)]


@pytest.fixture
def app_client(settings, backend):
    from fastapi.testclient import TestClient

    connectors = {
        "app_store": FakeConnector(),
        "broken": FakeConnector(fail=True),
        "web": FirecrawlConnector(api_key=None),
    }
    connectors["broken"].name = "broken"
    app = create_app(
        settings, inference=InferenceService(backend), encoder_factory=HashEncoder, connectors=connectors
    )
    with TestClient(app) as c:
        c.post(
            "/v1/auth/signup",
            json={
                "email": "s@example.com",
                "password": PASSWORD,
                "name": "S",
                "account_type": "organization",
                "organization_name": "S Co",
            },
        )
        yield c


def wait_run(c, run_id):
    for _ in range(100):
        r = c.get(f"/v1/collections/{run_id}").json()
        if r["status"] in ("complete", "failed"):
            return r
        time.sleep(0.1)
    raise AssertionError("collection did not finish")


def test_collect_flow(app_client):
    c = app_client
    pid = c.post("/v1/products", json={"name": "Acme"}).json()["id"]
    conns = {x["name"]: x for x in c.get("/v1/connectors").json()}
    assert conns["app_store"]["available"] and not conns["web"]["available"]
    assert "FIRECRAWL_API_KEY" in conns["web"]["requires"]
    assert c.get(f"/v1/products/{pid}/sources/suggest?connector=web").status_code == 409

    (cand,) = c.get(f"/v1/products/{pid}/sources/suggest?connector=app_store").json()
    assert cand["label"] == "Acme app"
    assert c.post(f"/v1/products/{pid}/collect").status_code == 409  # no sources yet
    src = c.post(
        f"/v1/products/{pid}/sources",
        json={"connector": "app_store", "ref": cand["ref"], "label": cand["label"]},
    )
    assert src.status_code == 201
    assert (
        c.post(f"/v1/products/{pid}/sources", json={"connector": "app_store", "ref": cand["ref"]}).status_code
        == 409
    )
    c.post(f"/v1/products/{pid}/sources", json={"connector": "broken", "ref": "x"})

    run = c.post(f"/v1/products/{pid}/collect")
    assert run.status_code == 202
    done = wait_run(c, run.json()["id"])
    assert done["status"] == "complete"
    by_conn = {r["connector"]: r for r in done["results"]}
    assert by_conn["app_store"]["added"] == 40
    assert by_conn["broken"]["error"] == "Source is down"  # one failing source doesn't stop the rest
    assert c.get(f"/v1/products/{pid}").json()["review_count"] == 40
    sources = {s["connector"]: s for s in c.get(f"/v1/products/{pid}/sources").json()}
    assert sources["app_store"]["last_added"] == 40 and sources["broken"]["last_error"] == "Source is down"

    # second run: everything is a duplicate
    again = wait_run(c, c.post(f"/v1/products/{pid}/collect").json()["id"])
    assert {r["connector"]: r for r in again["results"]}["app_store"]["duplicates"] == 40


def test_web_source_policy_enforced_on_add(app_client):
    pid = app_client.post("/v1/products", json={"name": "Acme"}).json()["id"]
    r = app_client.post(
        f"/v1/products/{pid}/sources", json={"connector": "web", "ref": "https://www.flipkart.com/acme"}
    )
    assert r.status_code == 422 and "Flipkart" in r.json()["detail"]


def test_collection_keeps_partial_reviews_over_quota(app_client, monkeypatch):
    from app.platform import plans

    monkeypatch.setitem(
        plans.PLANS, "free", plans.Plan(**{**vars(plans.PLANS["free"]), "reviews_per_month": 25})
    )
    c = app_client
    pid = c.post("/v1/products", json={"name": "Acme"}).json()["id"]
    c.post(f"/v1/products/{pid}/sources", json={"connector": "app_store", "ref": "in:42"})
    res = wait_run(c, c.post(f"/v1/products/{pid}/collect").json()["id"])["results"][0]
    assert res["added"] == 25 and res["skipped_over_quota"] == 15
