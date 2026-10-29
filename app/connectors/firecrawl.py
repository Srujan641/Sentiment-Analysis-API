"""Web pages via Firecrawl: search for pages about a product, then extract reviews as
structured data with AI extraction, so no per-site scraper is needed.

Active only when FIRECRAWL_API_KEY is set. Every URL passes app/connectors/policy.py
(blocked marketplaces, robots.txt) before any request is made to Firecrawl.
"""

import hashlib
from datetime import date

from app.connectors.base import Candidate, ConnectorError, RawReview
from app.connectors.policy import check_url

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "product_name": {"type": "string", "description": "Name of the product the page's reviews are about"},
        "about_product": {
            "type": "boolean",
            "description": "True only if the page contains customer reviews or opinions of the requested product",
        },
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The review or opinion text, verbatim"},
                    "rating": {"type": "number", "description": "Star rating out of 5, if shown"},
                    "date": {"type": "string", "description": "Review date as YYYY-MM-DD, if shown"},
                },
                "required": ["text"],
            },
        },
    },
    "required": ["about_product", "reviews"],
}

MAX_PAGES_PER_SEARCH = 8


class FirecrawlConnector:
    name = "web"
    label = "Web (via Firecrawl)"
    requires = "Set FIRECRAWL_API_KEY in .env (free key at firecrawl.dev)."

    def __init__(self, api_key: str | None, client=None):
        self._key = api_key
        self._client = client

    def available(self) -> bool:
        return bool(self._key) or self._client is not None

    def _fc(self):
        if self._client is None:
            if not self._key:
                raise ConnectorError(self.requires)
            from firecrawl import Firecrawl

            self._client = Firecrawl(api_key=self._key)
        return self._client

    def discover(self, query: str, limit: int = MAX_PAGES_PER_SEARCH) -> list[Candidate]:
        return self.search(f"{query} reviews", limit)

    def search(self, query: str, limit: int = MAX_PAGES_PER_SEARCH) -> list[Candidate]:
        """Web search; every result is checked against the source policy."""
        data = self._fc().search(query, limit=min(limit, MAX_PAGES_PER_SEARCH))
        out = []
        for r in data.web or []:
            url = getattr(r, "url", None)
            if not url:
                continue
            allowed, reason = check_url(url)
            out.append(
                Candidate(
                    connector=self.name,
                    ref=url,
                    label=getattr(r, "title", None) or url,
                    url=url,
                    detail=(getattr(r, "description", None) or "")[:200],
                    allowed=allowed,
                    reason=reason,
                )
            )
        return out

    def extract(self, url: str, schema: dict, prompt: str) -> dict:
        """AI extraction of structured data from one permitted page."""
        allowed, reason = check_url(url)
        if not allowed:
            raise ConnectorError(reason)
        doc = self._fc().scrape(
            url,
            formats=[{"type": "json", "schema": schema, "prompt": prompt}],
            only_main_content=True,
            timeout=60000,
        )
        return getattr(doc, "json", None) or {}

    def read_product_name(self, url: str) -> str | None:
        try:
            data = self.extract(
                url,
                {
                    "type": "object",
                    "properties": {"product_name": {"type": "string"}, "brand": {"type": "string"}},
                },
                "Give the full name (with brand and model) of the main product this page is about.",
            )
        except ConnectorError:
            return None
        return (data.get("product_name") or "").strip() or None

    def collect(self, ref: str, product_name: str, limit: int = 500) -> list[RawReview]:
        allowed, reason = check_url(ref)
        if not allowed:
            raise ConnectorError(reason)
        doc = self._fc().scrape(
            ref,
            formats=[
                {
                    "type": "json",
                    "schema": REVIEW_SCHEMA,
                    "prompt": (
                        f"Extract customer reviews of the product “{product_name}”. Include only genuine customer "
                        "opinions, verbatim. Do not include reviewer names or any personal details. Set about_product "
                        "to false if the page has no customer reviews of this product."
                    ),
                }
            ],
            only_main_content=True,
            timeout=60000,
        )
        data = getattr(doc, "json", None) or {}
        if not data.get("about_product"):
            raise ConnectorError("This page doesn't contain customer reviews of the product.")
        out = []
        for i, r in enumerate(data.get("reviews") or []):
            text = (r.get("text") or "").strip()
            if len(text) < 3:
                continue
            rating = r.get("rating")
            out.append(
                RawReview(
                    text=text,
                    rating=float(rating) if isinstance(rating, int | float) and 0 <= rating <= 5 else None,
                    reviewed_on=_date(r.get("date")),
                    external_id="web-" + hashlib.sha1(f"{ref}|{i}|{text[:80]}".encode()).hexdigest()[:20],
                )
            )
        return out[:limit]


def _date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None
