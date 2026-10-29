"""Research one product for a personal user: identify -> gather reviews from permitted
sources -> analyse with the engine -> find competitors -> plain-language summary."""

import difflib
import re
from collections.abc import Callable
from datetime import UTC, datetime

from app.analysis.engine import ReviewInput, analyse
from app.connectors.base import ConnectorError
from app.platform.ingest import scrub
from app.research.identify import Identity, identify

WEB_PAGES = 4  # review pages read per research (each is one extraction call)
COMPETITOR_PAGES = 2
APP_REVIEWS = 300
MIN_REVIEWS_FOR_VERDICT = 20

COMPETITOR_SCHEMA = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full product name with brand and model"},
                    "why": {"type": "string", "description": "One sentence on why it is an alternative"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                    "price": {"type": "string", "description": "Price if stated, with currency"},
                },
                "required": ["name"],
            },
        }
    },
    "required": ["competitors"],
}


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split())


def _same_product(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def research(
    query: str,
    connectors: dict,
    classifier,
    encoder,
    matcher,
    progress: Callable[[str], None] = lambda s: None,
) -> dict:
    web = connectors.get("web")
    web_ok = bool(web and web.available())
    notes: list[str] = []

    progress("identifying the product")
    ident: Identity = identify(query, page_reader=web.read_product_name if web_ok else None)
    name = ident.name

    reviews: list[ReviewInput] = []
    sources: list[dict] = []

    # App store: only if the top results really are this product (works for apps).
    store = connectors.get("app_store")
    if store and store.available():
        progress("checking the App Store")
        try:
            match = next((c for c in store.discover(name, limit=3) if _same_product(c.label, name)), None)
            if match:
                got = store.collect(match.ref, name, limit=APP_REVIEWS)
                reviews += [_ri(r, "app_store", len(reviews) + i) for i, r in enumerate(got)]
                sources.append(
                    {"label": match.label, "url": match.url, "kind": "App Store", "reviews": len(got)}
                )
        except (ConnectorError, Exception):  # noqa: BLE001 - one source failing must not stop research
            notes.append("The App Store couldn't be reached.")

    # The web: review sites, blogs, forums, brand pages (policy-checked; marketplaces excluded).
    if web_ok:
        progress("searching the web for reviews")
        try:
            pages = [c for c in web.discover(name) if c.allowed][:WEB_PAGES]
        except Exception:  # noqa: BLE001
            pages = []
            notes.append("Web search failed; results use other sources only.")
        for page in pages:
            progress(f"reading {page.label[:60]}")
            try:
                got = web.collect(page.ref, name)
            except ConnectorError:
                continue
            except Exception:  # noqa: BLE001
                continue
            if got:
                reviews += [_ri(r, "web", len(reviews) + i) for i, r in enumerate(got)]
                sources.append({"label": page.label, "url": page.url, "kind": "Web", "reviews": len(got)})
    else:
        notes.append("Web research isn't set up yet (FIRECRAWL_API_KEY), so only app stores were searched.")

    progress("analysing reviews")
    report = analyse(reviews, classifier, encoder, matcher, kind="quick")

    competitors: list[dict] = []
    if web_ok:
        progress("finding competing products")
        competitors = _competitors(web, name)

    n = len(reviews)
    confidence = (
        "high"
        if n >= 200
        else "medium" if n >= 60 else "low" if n >= MIN_REVIEWS_FOR_VERDICT else "insufficient"
    )
    if confidence == "insufficient":
        notes.append(
            f"Only {n} review{'s' if n != 1 else ''} found, which isn't enough for a reliable verdict."
        )
    overall = report.get("overall") or {}

    return {
        "product": {"name": name, "identified_from": ident.source, "query": query, "url": ident.url},
        "verdict": {
            "review_count": n,
            "confidence": confidence,
            "positive_share": overall.get("positive_share"),
            "sentiment_score": overall.get("sentiment_score"),
            "average_rating": overall.get("average_rating"),
        },
        "lacking": [
            {
                k: s[k]
                for k in (
                    "aspect",
                    "negative",
                    "negative_share",
                    "rating_impact",
                    "quotes",
                    "specific_issues",
                )
                if k in s
            }
            for s in report.get("lacking", [])[:5]
        ],
        "strengths": [
            {k: s[k] for k in ("aspect", "positive", "quotes") if k in s}
            for s in report.get("strengths", [])[:5]
        ],
        "summary": _summary(name, report, confidence, competitors),
        "competitors": competitors,
        "sources": sources,
        "notes": notes,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _ri(r, source: str, i: int) -> ReviewInput:
    # Same cleaning as stored reviews: no HTML, emails, phone numbers or links in quotes.
    return ReviewInput(
        id=f"{source}-{i}", text=scrub(r.text), rating=r.rating, reviewed_on=r.reviewed_on, source=source
    )


def _competitors(web, name: str) -> list[dict]:
    try:
        pages = [c for c in web.search(f"best alternatives to {name}", limit=5) if c.allowed][
            :COMPETITOR_PAGES
        ]
    except Exception:  # noqa: BLE001
        return []
    found: dict[str, dict] = {}
    for page in pages:
        try:
            data = web.extract(
                page.ref,
                COMPETITOR_SCHEMA,
                f"List products recommended as alternatives or competitors to “{name}”, with their pros and cons as "
                "stated on the page. Exclude the product itself and anything not a direct competitor.",
            )
        except Exception:  # noqa: BLE001
            continue
        for c in data.get("competitors") or []:
            cname = (c.get("name") or "").strip()
            if not cname or _same_product(cname, name):
                continue
            key = _norm(cname)
            entry = found.setdefault(
                key,
                {
                    "name": cname,
                    "why": c.get("why"),
                    "pros": [],
                    "cons": [],
                    "price": c.get("price"),
                    "mentions": 0,
                    "sources": [],
                },
            )
            entry["mentions"] += 1
            entry["pros"] = list(dict.fromkeys(entry["pros"] + (c.get("pros") or [])))[:4]
            entry["cons"] = list(dict.fromkeys(entry["cons"] + (c.get("cons") or [])))[:4]
            if page.url not in entry["sources"]:
                entry["sources"].append(page.url)
    return sorted(found.values(), key=lambda e: -e["mentions"])[:3]


def _summary(name: str, report: dict, confidence: str, competitors: list[dict]) -> list[str]:
    out = []
    o = report.get("overall")
    if not o:
        return [f"We couldn't find enough reviews of {name} on the sources we can use."]
    rating = f" (average {o['average_rating']:.1f}★)" if o.get("average_rating") else ""
    out.append(
        f"{o['positive_share'] * 100:.0f}% of {report['review_count']:,} reviews of {name} are positive{rating}."
    )
    if report.get("strengths"):
        out.append("People like: " + ", ".join(s["aspect"] for s in report["strengths"][:3]) + ".")
    if report.get("lacking"):
        out.append("What it's lacking: " + ", ".join(s["aspect"] for s in report["lacking"][:3]) + ".")
    if competitors:
        out.append("Alternatives worth comparing: " + ", ".join(c["name"] for c in competitors) + ".")
    if confidence in ("low", "insufficient"):
        out.append("Treat this as indicative: there were few reviews to work with.")
    return out
