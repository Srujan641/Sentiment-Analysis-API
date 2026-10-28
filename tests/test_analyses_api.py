import time
from datetime import date, timedelta

from sqlalchemy import select

from app.platform.models import User
from tests.conftest import make_client

PASSWORD = "correct-horse-battery"


def signup(c, email="brand@example.com"):
    r = c.post(
        "/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "name": "B", "account_type": "individual"},
    )
    assert r.status_code == 201


def set_plan(c, email, plan):
    with c.app.state.db.sessionmaker() as s:
        s.scalar(select(User).where(User.email == email)).org.plan = plan
        s.commit()


def seed(c):
    pid = c.post("/v1/products", json={"name": "Earbuds"}).json()["id"]
    start = date(2026, 1, 5)
    reviews = []
    for i in range(200):
        d = start + timedelta(days=i % 170)
        if i % 3 == 0 and d < date(2026, 4, 6):
            text, rating = f"Sound is great but the battery is terrible ({i})", 2
        elif i % 9 == 0:
            text, rating = f"Battery is terrible again ({i})", 2
        else:
            text, rating = f"Great sound, great price ({i})", 5
        reviews.append({"text": text, "rating": rating, "reviewed_on": d.isoformat()})
    assert c.post(f"/v1/products/{pid}/reviews", json={"reviews": reviews}).json()["added"] == 200
    return pid


def wait(c, analysis_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        a = c.get(f"/v1/analyses/{analysis_id}").json()
        if a["status"] in ("complete", "failed"):
            return a
        time.sleep(0.05)
    raise AssertionError("analysis did not finish")


def test_quick_analysis_end_to_end(settings, backend):
    with make_client(settings, backend) as c:
        signup(c)
        pid = seed(c)
        assert c.get(f"/v1/products/{pid}/insights").status_code == 404
        r = c.post(f"/v1/products/{pid}/analyses", json={"kind": "quick"})
        assert r.status_code == 202 and r.json()["status"] == "queued"
        done = wait(c, r.json()["id"])
        assert done["status"] == "complete", done["error"]
        report = c.get(done["report_url"]).json()
        assert report["review_count"] == 200
        assert report["lacking"][0]["aspect"] == "battery life"
        assert c.get(f"/v1/products/{pid}/insights").json()["analysis_id"] == done["id"]
        assert c.get("/v1/usage").json()["reports_generated"]["used"] == 1


def test_full_report_requires_paid_plan_and_verifies_fix(settings, backend):
    with make_client(settings, backend) as c:
        signup(c)
        pid = seed(c)
        assert c.post(f"/v1/products/{pid}/analyses", json={"kind": "full"}).status_code == 403
        set_plan(c, "brand@example.com", "starter")
        c.post(
            f"/v1/products/{pid}/changes",
            json={"changed_on": "2026-04-06", "aspects": ["battery"], "description": "new cells"},
        )
        done = wait(c, c.post(f"/v1/products/{pid}/analyses", json={"kind": "full"}).json()["id"])
        report = c.get(done["report_url"]).json()
        result = report["fix_verification"][0]["results"][0]
        assert result["aspect"] == "battery life" and result["verdict"] == "improved"
        assert "trends" in report and "alerts" in report


def test_report_quota_and_isolation(settings, backend):
    with make_client(settings, backend) as a, make_client(settings, backend) as b:
        signup(a, "a@example.com")
        signup(b, "b@example.com")
        pid = seed(a)
        ids = []
        for _ in range(3):  # Free plan: 3 reports / month
            r = a.post(f"/v1/products/{pid}/analyses", json={"kind": "quick"})
            assert r.status_code == 202
            ids.append(r.json()["id"])
            wait(a, ids[-1])
        assert a.post(f"/v1/products/{pid}/analyses", json={"kind": "quick"}).status_code == 429
        assert len(a.get(f"/v1/products/{pid}/analyses").json()) == 3
        assert b.get(f"/v1/analyses/{ids[0]}").status_code == 404
        assert b.get(f"/v1/analyses/{ids[0]}/report").status_code == 404
        assert b.post(f"/v1/products/{pid}/analyses", json={"kind": "quick"}).status_code == 404
