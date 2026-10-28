"""Apple App Store: official public endpoints, no key needed.

Search: https://itunes.apple.com/search  ·  Reviews: the customer-reviews RSS feed
(50 per page, up to 10 pages = 500 most recent reviews per country).
"""

from datetime import datetime

import httpx

from app.connectors.base import Candidate, ConnectorError, RawReview
from app.connectors.policy import USER_AGENT


class AppStoreConnector:
    name = "app_store"
    label = "Apple App Store"
    requires = None

    def __init__(self, country: str = "in", client: httpx.Client | None = None):
        self.country = country
        self._client = client or httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT})

    def available(self) -> bool:
        return True

    def discover(self, query: str, limit: int = 5) -> list[Candidate]:
        r = self._client.get(
            "https://itunes.apple.com/search",
            params={"term": query, "entity": "software", "country": self.country, "limit": limit},
        )
        r.raise_for_status()
        out = []
        for app in r.json().get("results", []):
            count = app.get("userRatingCount") or 0
            rating = app.get("averageUserRating")
            out.append(
                Candidate(
                    connector=self.name,
                    ref=f"{self.country}:{app['trackId']}",
                    label=app.get("trackName", str(app["trackId"])),
                    url=app.get("trackViewUrl"),
                    detail=f"{app.get('sellerName', '')} · {count:,} ratings"
                    + (f" · {rating:.1f}★" if rating else ""),
                )
            )
        return out

    def collect(self, ref: str, product_name: str, limit: int = 500) -> list[RawReview]:
        try:
            country, app_id = ref.split(":", 1)
            int(app_id)
        except ValueError as exc:
            raise ConnectorError("App Store sources look like 'in:434613896' (country:app id).") from exc
        reviews: list[RawReview] = []
        for page in range(1, 11):
            r = self._client.get(
                f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
            )
            if r.status_code == 404:
                break
            r.raise_for_status()
            entries = r.json().get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
            page_reviews = [e for e in entries if "im:rating" in e]  # skip the app-info entry if present
            if not page_reviews:
                break
            for e in page_reviews:
                title = e.get("title", {}).get("label", "").strip()
                body = e.get("content", {}).get("label", "").strip()
                updated = e.get("updated", {}).get("label")
                reviews.append(
                    RawReview(
                        text=f"{title}. {body}" if title and body else (body or title),
                        rating=float(e["im:rating"]["label"]),
                        reviewed_on=datetime.fromisoformat(updated).date() if updated else None,
                        external_id=f"appstore-{e.get('id', {}).get('label', '')}",
                        extra={"version": e.get("im:version", {}).get("label")},
                    )
                )
            if len(reviews) >= limit:
                break
        return reviews[:limit]
