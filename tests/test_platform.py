import io

import pytest

from app.platform.ingest import parse_date, parse_upload, scrub
from tests.conftest import make_client

PASSWORD = "correct-horse-battery"


def signup(client, email="asha@example.com", **extra):
    # Business account by default: products, reviews and keys are business features.
    body = {
        "email": email,
        "password": PASSWORD,
        "name": "Asha",
        "account_type": "organization",
        "organization_name": "Acme",
        **extra,
    }
    return client.post("/v1/auth/signup", json=body)


def new_key(client):
    r = client.post("/v1/keys", json={"name": "ci"})
    assert r.status_code == 201
    return r.json()["key"]


@pytest.fixture
def user(client):
    assert signup(client).status_code == 201
    return client


# ---------------------------------------------------------------- auth
def test_signup_sets_session_and_me(client):
    r = signup(client)
    assert r.status_code == 201
    assert "rp_session" in r.cookies
    body = r.json()
    assert body["organization"]["plan"] == "free"
    assert body["organization"]["account_type"] == "organization"
    assert client.get("/v1/auth/me").json()["user"]["email"] == "asha@example.com"


def test_signup_rules(client):
    assert signup(client).status_code == 201
    assert signup(client).status_code == 409  # duplicate email
    assert signup(client, email="b@example.com", password="short").status_code == 422
    r = signup(client, email="c@example.com", account_type="organization", organization_name=None)
    assert r.status_code == 422  # organization_name required


def test_organization_signup(client):
    r = signup(client, account_type="organization", organization_name="Boat Lifestyle")
    assert r.json()["organization"]["name"] == "Boat Lifestyle"


def test_login_logout(client):
    signup(client)
    client.post("/v1/auth/logout")
    assert client.get("/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/v1/auth/login", json={"email": "asha@example.com", "password": "wrong-password"}
        ).status_code
        == 401
    )
    assert (
        client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}).status_code
        == 401
    )
    r = client.post("/v1/auth/login", json={"email": "ASHA@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert client.get("/v1/auth/me").status_code == 200


def test_unauthenticated_is_401(client):
    assert client.get("/v1/products").status_code == 401
    assert client.get("/v1/products", headers={"X-API-Key": "rp_live_nope"}).status_code == 401


def test_login_brute_force_limited(settings, backend):
    settings.auth_rate_limit = "3/minute"
    with make_client(settings, backend) as c:
        codes = [
            c.post("/v1/auth/login", json={"email": "x@example.com", "password": "whatever-123"}).status_code
            for _ in range(4)
        ]
        assert codes == [401, 401, 401, 429]


# ---------------------------------------------------------------- keys
def test_key_shown_once_and_hashed(user, client):
    created = client.post("/v1/keys", json={"name": "server"}).json()
    assert created["key"].startswith("rp_live_")
    assert created["key"].startswith(created["prefix"])
    listed = client.get("/v1/keys").json()
    assert "key" not in listed[0]
    assert listed[0]["prefix"] == created["prefix"]


def test_api_key_authenticates_and_revocation(user, client):
    key = new_key(client)
    client.cookies.clear()
    h = {"Authorization": f"Bearer {key}"}
    assert client.get("/v1/products", headers=h).status_code == 200
    assert client.get("/v1/products", headers={"X-API-Key": key}).status_code == 200
    # keys cannot manage keys
    assert client.post("/v1/keys", json={"name": "x"}, headers=h).status_code == 403

    login = client.post("/v1/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert login.status_code == 200
    key_id = client.get("/v1/keys").json()[0]["id"]
    assert client.delete(f"/v1/keys/{key_id}").json()["revoked_at"] is not None
    client.cookies.clear()
    assert client.get("/v1/products", headers=h).status_code == 401


def test_plan_rate_limit_per_key(settings, backend):
    with make_client(settings, backend) as c:
        signup(c)
        key = new_key(c)
        c.cookies.clear()
        codes = [c.get("/v1/usage", headers={"X-API-Key": key}).status_code for _ in range(31)]
        assert codes[:30] == [200] * 30 and codes[30] == 429  # Free plan: 30/minute


# ---------------------------------------------------------------- products & changes
def test_product_crud_and_free_plan_limit(user, client):
    r = client.post(
        "/v1/products", json={"name": "Earbuds X200", "brand": "Acme", "identifiers": {"asin": "B0X"}}
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["identifiers"] == {"asin": "B0X"}
    assert client.post("/v1/products", json={"name": "Second"}).status_code == 429  # Free: 1 product
    assert client.patch(f"/v1/products/{pid}", json={"category": "Audio"}).json()["category"] == "Audio"
    assert client.delete(f"/v1/products/{pid}").json()["archived"] is True
    assert client.get("/v1/products").json() == []
    assert len(client.get("/v1/products?include_archived=true").json()) == 1
    assert client.post("/v1/products", json={"name": "Second"}).status_code == 201  # slot freed


def test_log_change(user, client):
    pid = client.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    body = {"changed_on": "2026-09-01", "aspects": [" Battery Life "], "description": "New battery supplier"}
    r = client.post(f"/v1/products/{pid}/changes", json=body)
    assert r.status_code == 201
    assert r.json()["aspects"] == ["battery life"]
    assert len(client.get(f"/v1/products/{pid}/changes").json()) == 1


def test_tenant_isolation(settings, backend):
    with make_client(settings, backend) as a, make_client(settings, backend) as b:
        signup(a, email="a@example.com")
        signup(b, email="b@example.com")
        pid = a.post("/v1/products", json={"name": "Secret product"}).json()["id"]
        a.post(f"/v1/products/{pid}/reviews", json={"reviews": [{"text": "private review"}]})
        assert b.get(f"/v1/products/{pid}").status_code == 404
        assert b.get(f"/v1/products/{pid}/reviews").status_code == 404
        assert b.post(f"/v1/products/{pid}/reviews", json={"reviews": [{"text": "x y"}]}).status_code == 404
        assert (
            b.post(
                f"/v1/products/{pid}/changes",
                json={"changed_on": "2026-01-01", "aspects": ["a"], "description": "nope"},
            ).status_code
            == 404
        )
        assert b.patch(f"/v1/products/{pid}", json={"name": "hacked"}).status_code == 404
        assert b.get("/v1/products").json() == []
        key_id = a.post("/v1/keys", json={"name": "k"}).json()["id"]
        assert b.delete(f"/v1/keys/{key_id}").status_code == 404


# ---------------------------------------------------------------- reviews
def test_push_dedupes_and_scrubs(user, client):
    pid = client.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    reviews = [
        {
            "text": "Battery dies in 2 hours. Mail me at asha@example.com or 98765 43210",
            "rating": 2,
            "reviewed_on": "2026-09-03",
        },
        {"text": "battery DIES in 2 hours. mail me at asha@example.com or 98765 43210", "rating": 2},
        {"text": "Great sound!", "rating": 5},
        {"text": " "},
    ]
    r = client.post(f"/v1/products/{pid}/reviews", json={"reviews": reviews}).json()
    assert (r["received"], r["added"], r["duplicates"], r["rejected"]) == (4, 2, 1, 1)
    again = client.post(f"/v1/products/{pid}/reviews", json={"reviews": reviews[:1]}).json()
    assert again["added"] == 0 and again["duplicates"] == 1

    items = client.get(f"/v1/products/{pid}/reviews").json()["items"]
    texts = " ".join(i["text"] for i in items)
    assert "asha@example.com" not in texts and "98765" not in texts
    assert "[email]" in texts and "[phone]" in texts
    assert client.get(f"/v1/products/{pid}").json()["review_count"] == 2
    assert client.get("/v1/usage").json()["reviews_ingested"]["used"] == 2


def test_csv_upload(user, client):
    pid = client.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    csv = 'Review,Stars,Review Date\nLoud and clear,5,2026-08-01\n"Case hinge broke, sad",1,01/09/2026\n'
    files = {"file": ("export.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = client.post(f"/v1/products/{pid}/reviews/upload", files=files)
    assert r.status_code == 201 and r.json()["added"] == 2
    items = client.get(f"/v1/products/{pid}/reviews").json()["items"]
    assert {i["reviewed_on"] for i in items} == {"2026-08-01", "2026-09-01"}


def test_bad_upload(user, client):
    pid = client.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    files = {"file": ("x.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")}
    r = client.post(f"/v1/products/{pid}/reviews/upload", files=files)
    assert r.status_code == 422 and "text column" in r.json()["detail"]


def test_review_quota(user, client, monkeypatch):
    from app.platform import plans

    monkeypatch.setitem(
        plans.PLANS,
        "free",
        plans.PLANS["free"].__class__(**{**plans.PLANS["free"].__dict__, "reviews_per_month": 3}),
    )
    pid = client.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    ok = client.post(
        f"/v1/products/{pid}/reviews", json={"reviews": [{"text": f"review {i}"} for i in range(3)]}
    )
    assert ok.status_code == 201 and ok.json()["remaining_this_month"] == 0
    over = client.post(f"/v1/products/{pid}/reviews", json={"reviews": [{"text": "one more"}]})
    assert over.status_code == 429 and "left this month" in over.json()["detail"]


def test_plans_public(client):
    business = client.get("/v1/plans?audience=business").json()
    assert [p["id"] for p in business] == ["free", "starter", "growth", "enterprise"]
    personal = client.get("/v1/plans?audience=individual").json()
    assert [(p["id"], p["research_per_day"]) for p in personal] == [
        ("personal_free", 10),
        ("personal_plus", 100),
    ]


# ---------------------------------------------------------------- ingest helpers
def test_scrub():
    out = scrub("Call +91 98765-43210, email a.b@x.co, see https://x.com/p")
    assert out == "Call [phone], email [email], see [link]"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-09-03", "2026-09-03"),
        ("2026-09-03T10:00:00Z", "2026-09-03"),
        ("03/09/2026", "2026-09-03"),
        ("3 Sep 2026", "2026-09-03"),
        ("Sep 3, 2026", "2026-09-03"),
        ("1788393600", "2026-09-03"),
        ("garbage", None),
    ],
)
def test_parse_date(raw, expected):
    d = parse_date(raw)
    assert (d.isoformat() if d else None) == expected


def test_parse_upload_json_variants():
    assert parse_upload("a.json", b'[{"review": "ok", "stars": 4}]')[0]["rating"] == 4
    assert parse_upload("a.json", b'{"reviews": [{"text": "ok"}]}')[0]["text"] == "ok"
    assert len(parse_upload("a.jsonl", b'{"text": "a"}\n{"text": "b"}\n')) == 2


# ---------------------------------------------------------------- two account types
def test_personal_and_business_logins_are_separate(client):
    personal = signup(client, email="p@example.com", account_type="individual", organization_name=None)
    assert personal.json()["organization"]["plan"] == "personal_free"
    client.post("/v1/auth/logout")
    signup(client, email="b@example.com")
    client.post("/v1/auth/logout")

    def login(email, portal):
        return client.post("/v1/auth/login", json={"email": email, "password": PASSWORD, "portal": portal})

    assert login("p@example.com", "business").status_code == 403
    assert "personal login" in login("p@example.com", "business").json()["detail"]
    assert login("b@example.com", "personal").status_code == 403
    assert login("p@example.com", "personal").status_code == 200
    assert login("b@example.com", "business").status_code == 200


def test_guardrails_between_account_types(client):
    signup(client, email="p@example.com", account_type="individual", organization_name=None)
    r = client.post("/v1/products", json={"name": "Earbuds"})
    assert r.status_code == 403 and "business accounts" in r.json()["detail"]
    assert client.get("/v1/connectors").status_code == 403
    assert client.get("/v1/usage").status_code == 200  # shared
