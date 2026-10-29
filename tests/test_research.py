import time

import pytest
from fastapi.testclient import TestClient

from app.connectors.base import Candidate, ConnectorError, RawReview
from app.main import create_app
from app.research.identify import IdentifyError, identify
from app.services.inference import InferenceService
from tests.test_analysis import HashEncoder

PASSWORD = "correct-horse-battery"


# ---------------------------------------------------------------- identify
@pytest.mark.parametrize(
    "query,name,source",
    [
        (
            "https://www.amazon.in/boAt-Rockerz-450-Bluetooth-Headphones-Playback/dp/B07PR1CL3S/ref=x",
            "boAt Rockerz 450 Bluetooth Headphones",
            "amazon_link",
        ),
        (
            "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac?pid=X",
            "apple iphone 15",
            "flipkart_link",
        ),
        ("https://www.google.com/search?q=sony+wh-1000xm5+review", "sony wh-1000xm5", "google_link"),
        ("Noise ColorFit Pro 5", "Noise ColorFit Pro 5", "name"),
    ],
)
def test_identify(query, name, source):
    ident = identify(query)
    assert (ident.name, ident.source) == (name, source)


def test_identify_rejects_links_without_names():
    for q in (
        "https://amzn.in/d/abc",
        "https://www.amazon.in/dp/B07PR1CL3S",
        "https://www.myntra.com/x/123/buy",
        "x",
    ):
        with pytest.raises(IdentifyError):
            identify(q)


def test_identify_reads_permitted_pages():
    assert (
        identify("https://brand.example/p/xyz", page_reader=lambda url: "Acme Buds Pro").name
        == "Acme Buds Pro"
    )


# ---------------------------------------------------------------- pipeline through the API
class FakeWeb:
    name, label, requires = "web", "Web", None

    def __init__(self):
        self.collected = []

    def available(self):
        return True

    def read_product_name(self, url):
        return None

    def search(self, query, limit=8):
        if query.startswith("best alternatives"):
            return [
                Candidate(
                    "web", "https://compare.example/best", "Best earbuds", url="https://compare.example/best"
                )
            ]
        return []

    def discover(self, query, limit=8):
        return [
            Candidate("web", "https://blog.example/review", "Review", url="https://blog.example/review"),
            Candidate(
                "web",
                "https://www.amazon.in/x",
                "Amazon",
                url="https://www.amazon.in/x",
                allowed=False,
                reason="blocked",
            ),
            Candidate("web", "https://forum.example/thread", "Forum", url="https://forum.example/thread"),
        ]

    def collect(self, ref, product_name, limit=500):
        self.collected.append(ref)
        if "forum" in ref:
            raise ConnectorError("no reviews on page")
        out = []
        for i in range(60):
            if i % 3 == 0:
                out.append(RawReview(f"Sound is great but the battery is terrible ({i})", rating=2))
            else:
                out.append(RawReview(f"Great sound and great price ({i})", rating=5))
        return out

    def extract(self, url, schema, prompt):
        return {
            "competitors": [
                {"name": "Acme Buds Pro", "why": "Better battery", "pros": ["battery"], "cons": ["price"]},
                {"name": "boAt Rockerz 450", "why": "same product"},
                {"name": "Zeta Pods 2", "pros": ["fit"]},
            ]
        }


class NoStore:
    name, label, requires = "app_store", "App Store", None

    def available(self):
        return False


@pytest.fixture
def setup(settings, backend):
    web = FakeWeb()
    app = create_app(
        settings,
        inference=InferenceService(backend),
        encoder_factory=HashEncoder,
        connectors={"web": web, "app_store": NoStore()},
    )
    with TestClient(app) as c:
        yield c, web


def personal(c, email="p@example.com"):
    r = c.post(
        "/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "name": "P", "account_type": "individual"},
    )
    assert r.status_code == 201


def wait(c, rid):
    for _ in range(200):
        r = c.get(f"/v1/research/{rid}").json()
        if r["status"] in ("complete", "failed"):
            return r
        time.sleep(0.05)
    raise AssertionError("research did not finish")


def test_research_from_amazon_link(setup):
    c, web = setup
    personal(c)
    r = c.post(
        "/v1/research",
        json={"query": "https://www.amazon.in/boAt-Rockerz-450-Bluetooth-Headphones/dp/B07PR1CL3S"},
    )
    assert r.status_code == 202
    done = wait(c, r.json()["id"])
    assert done["status"] == "complete", done["error"]
    res = done["result"]
    assert res["product"] == {
        "name": "boAt Rockerz 450 Bluetooth Headphones",
        "identified_from": "amazon_link",
        "query": done["query"],
        "url": done["query"],
    }
    assert "https://www.amazon.in/x" not in web.collected  # marketplace page never collected
    assert res["verdict"]["review_count"] == 60 and res["verdict"]["confidence"] == "medium"
    assert res["lacking"][0]["aspect"] == "battery life"
    assert [x["name"] for x in res["competitors"]] == ["Acme Buds Pro", "Zeta Pods 2"]  # itself excluded
    assert res["sources"] == [
        {"label": "Review", "url": "https://blog.example/review", "kind": "Web", "reviews": 60}
    ]
    assert any("Alternatives worth comparing" in s for s in res["summary"])
    assert c.get("/v1/research").json()[0]["product_name"] == "boAt Rockerz 450 Bluetooth Headphones"


def test_bad_link_fails_with_guidance(setup):
    c, _ = setup
    personal(c)
    done = wait(c, c.post("/v1/research", json={"query": "https://amzn.in/d/abc"}).json()["id"])
    assert done["status"] == "failed" and "type the product name" in done["error"]


def test_daily_limit(setup, monkeypatch):
    from app.platform import plans

    monkeypatch.setitem(
        plans.PLANS,
        "personal_free",
        plans.Plan(**{**vars(plans.PLANS["personal_free"]), "research_per_day": 3}),
    )
    c, _ = setup
    personal(c)
    for _ in range(3):
        wait(c, c.post("/v1/research", json={"query": "Acme earbuds"}).json()["id"])
    over = c.post("/v1/research", json={"query": "Acme earbuds"})
    assert over.status_code == 429 and "Personal Plus" in over.json()["detail"]
    usage = c.get("/v1/usage").json()
    assert usage["audience"] == "individual" and usage["research_today"]["used"] == 3


def test_business_accounts_cannot_research(setup):
    c, _ = setup
    c.post(
        "/v1/auth/signup",
        json={
            "email": "b@example.com",
            "password": PASSWORD,
            "name": "B",
            "account_type": "organization",
            "organization_name": "B Co",
        },
    )
    r = c.post("/v1/research", json={"query": "Acme earbuds"})
    assert r.status_code == 403 and "personal accounts" in r.json()["detail"]


def test_research_is_private(setup):
    c, _ = setup
    personal(c, "one@example.com")
    rid = c.post("/v1/research", json={"query": "Acme earbuds"}).json()["id"]
    wait(c, rid)
    c.post("/v1/auth/logout")
    personal(c, "two@example.com")
    assert c.get(f"/v1/research/{rid}").status_code == 404
