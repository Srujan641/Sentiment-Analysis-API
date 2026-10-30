"""Load a demo brand account with real Amazon Reviews 2023 products, through the real API.

    python -m scripts.seed_demo            # API must be running (make run)

Creates demo@example.com (password printed), sets the Growth plan, adds products, pushes
their reviews, and logs one clearly labelled example change for fix verification.
"""

import argparse
import json

import httpx

from scripts.analyse_amazon import DEFAULT_FILE, load
from scripts.set_plan import main as set_plan

PRODUCTS = [
    ("B0C1HHXQ94", "Yoga Mat Cleaner Spray", "Fitness"),
    ("B01CKMP406", "Product B01CKMP406", "Health & Personal Care"),
]
EMAIL, PASSWORD = "demo@example.com", "demo-password-123"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--file", default=DEFAULT_FILE)
    a = ap.parse_args(argv)

    c = httpx.Client(base_url=a.api, timeout=120)
    r = c.post(
        "/v1/auth/signup",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "name": "Demo Brand Owner",
            "account_type": "organization",
            "organization_name": "Demo Brand",
        },
    )
    if r.status_code == 409:
        c.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).raise_for_status()
    else:
        r.raise_for_status()
    set_plan([EMAIL, "growth"])

    existing = {p["name"]: p for p in c.get("/v1/products").json()}
    for asin, name, category in PRODUCTS:
        if name in existing and existing[name]["review_count"]:
            print(f"{name}: already loaded")
            continue
        reviews = load(a.file, asin)
        if name in existing:
            pid = existing[name]["id"]
        else:
            pid = (
                c.post(
                    "/v1/products", json={"name": name, "category": category, "identifiers": {"asin": asin}}
                )
                .raise_for_status()
                .json()["id"]
            )
        added = 0
        for i in range(0, len(reviews), 1000):
            batch = [
                {
                    "text": r.text,
                    "rating": r.rating,
                    "reviewed_on": r.reviewed_on.isoformat(),
                    "external_id": r.id,
                }
                for r in reviews[i : i + 1000]
            ]
            res = c.post(f"/v1/products/{pid}/reviews", json={"source": "amazon_2023", "reviews": batch})
            res.raise_for_status()
            added += res.json()["added"]
        print(f"{name}: {added} reviews added")
        if asin == "B0C1HHXQ94":
            c.post(
                f"/v1/products/{pid}/changes",
                json={
                    "changed_on": "2022-01-01",
                    "aspects": ["spray bottle"],
                    "description": "Demo only: example date to show fix verification (not a real event)",
                },
            ).raise_for_status()

    print(json.dumps({"login": EMAIL, "password": PASSWORD, "site": "http://localhost:3000/login"}, indent=2))


if __name__ == "__main__":
    main()
