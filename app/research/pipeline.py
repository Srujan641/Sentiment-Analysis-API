"""Research one product for a personal user: identify -> gather reviews from permitted
sources -> analyse with the engine -> find competitors -> plain-language summary."""

import difflib
import html
import re
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.analysis.engine import ReviewInput, analyse
from app.connectors.base import ConnectorError
from app.platform.ingest import scrub
from app.research.identify import Identity, identify

WEB_PAGES = 5  # review pages read per research (each is one extraction call)
YOUTUBE_VIDEOS = 5
YOUTUBE_COMMENTS = 150
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


# Category words marketplace titles append; searching with them finds fewer, worse matches.
_GENERIC = {
    "bluetooth",
    "wireless",
    "wired",
    "headphones",
    "headphone",
    "headset",
    "earphones",
    "earbuds",
    "earphone",
    "tws",
    "neckband",
    "on",
    "over",
    "in",
    "ear",
    "with",
    "mic",
    "smartwatch",
    "smart",
    "watch",
    "phone",
    "smartphone",
    "mobile",
    "laptop",
    "notebook",
    "speaker",
    "portable",
    "true",
    "anc",
    "cancelling",
}


def core_name(name: str) -> str:
    """'boAt Rockerz 450 Bluetooth Headphones' -> 'boAt Rockerz 450' (keeps at least 2 words)."""
    words = name.split()
    kept = [w for w in words if _norm(w) not in _GENERIC]
    return " ".join(kept if len(kept) >= 2 else words[:3])


def _key_terms(name: str) -> set[str]:
    return {w for w in _norm(name).split() if len(w) >= 3 or any(c.isdigit() for c in w)}


def _title_matches(title: str, terms: set[str]) -> bool:
    """A video counts if its title has most of the product's distinctive words (brand, model)."""
    words = set(_norm(title).split())
    return bool(terms) and len(terms & words) / len(terms) >= 0.6


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
    search_name = core_name(name)

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

    # YouTube: comments on review videos whose titles match the product.
    yt = connectors.get("youtube")
    if yt and yt.available():
        progress("reading YouTube review comments")
        try:
            terms = _key_terms(search_name)
            found = yt.discover(search_name, limit=8)
            videos = [v for v in found if _title_matches(v.label, terms)][:YOUTUBE_VIDEOS]
        except Exception:  # noqa: BLE001
            videos = []
            notes.append("YouTube couldn't be searched.")
        hinglish = 0
        for v in videos:
            try:
                got = yt.collect(v.ref, search_name, limit=YOUTUBE_COMMENTS)
            except Exception:  # noqa: BLE001 - comments disabled, quota, etc.
                continue
            hinglish += getattr(yt, "last_skipped", {}).get("code_mixed", 0)
            if got:
                reviews += [_ri(r, "youtube", len(reviews) + i) for i, r in enumerate(got)]
                sources.append({"label": v.label, "url": v.url, "kind": "YouTube", "reviews": len(got)})
        if hinglish:
            notes.append(
                f"{hinglish} YouTube comment{'s' if hinglish != 1 else ''} in Hindi, Telugu or other languages written "
                "in English letters were skipped: the model reads English for now; Indian-language support is coming."
            )

    # The web: review sites, blogs, forums, brand pages (policy-checked; marketplaces excluded).
    if web_ok:
        progress("searching the web for reviews")
        try:
            seen: set[str] = set()
            pages = []
            for q in (f"{search_name} review", f"{search_name} user reviews pros cons"):
                for c in web.search(q, limit=8):
                    if c.allowed and c.ref not in seen:
                        seen.add(c.ref)
                        pages.append(c)
            pages = pages[:WEB_PAGES]
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
        competitors = _competitors(web, search_name)

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
    rated = overall.get("rated_reviews") or 0
    # Comments have no stars: an average from a small rated minority would mislead.
    show_rating = rated >= 20 and rated >= 0.3 * max(n, 1)

    return {
        "product": {"name": name, "identified_from": ident.source, "query": query, "url": ident.url},
        "verdict": {
            "review_count": n,
            "confidence": confidence,
            "positive_share": overall.get("positive_share"),
            "sentiment_score": overall.get("sentiment_score"),
            "average_rating": overall.get("average_rating") if show_rating else None,
            "rated_reviews": rated,
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
        "summary": _summary(name, report, confidence, competitors, show_rating),
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


_VS = re.compile(r"\s+(?:vs\.?|versus|v/s)\s+", re.I)
_BETWEEN = re.compile(
    r"(?:difference between|compare|best[,:]?)\s+(.+?)\s+(?:and|or)\s+(.+?)(?:\?|$| for | in )", re.I
)
_SITE_SUFFIX = re.compile(r"\s+[|\-–—:]\s+[^|\-–—:]+$")


def _clean_name(s: str) -> str:
    s = s.split(":")[0]  # "Noise Two: What is the difference" -> "Noise Two"
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)  # "(2024)", "[Review]"
    s = re.sub(
        r"\b(review|reviews|comparison|compared|full|specs|price|which is better|which one)\b.*$",
        "",
        s,
        flags=re.I,
    )
    words = [w for w in re.split(r"\s+", s.strip(" -–—:|?!.,")) if w][:6]
    return " ".join(words)


def names_from_result(title: str, url: str) -> list[str]:
    """Product names compared in a search result's title or link ("A vs B", "between A and B")."""
    out: list[str] = []
    t = _SITE_SUFFIX.sub("", html.unescape(title or "")).strip()
    if _VS.search(t):
        out += [_clean_name(x) for x in _VS.split(t)]
    else:
        m = _BETWEEN.search(t)
        if m:
            out += [_clean_name(m.group(1)), _clean_name(m.group(2))]
    slug = urlparse(url).path.rstrip("/").split("/")[-1] if url else ""
    if "-vs-" in slug:
        out += [
            " ".join(w.capitalize() if w.isalpha() and w.islower() else w for w in part.split("-"))
            for part in slug.split("-vs-")
        ]
    unique: list[str] = []
    for x in out:  # title and link often name the same products; count each once per result
        if len(x) >= 3 and re.search(r"[A-Za-z]", x) and not any(_same_product(x, u) for u in unique):
            unique.append(x)
    return unique


def _competitors(web, name: str) -> list[dict]:
    """Alternatives from comparison searches. Names come from search titles and links (the
    search engine's data, so blocked sites are never visited); pros and cons are added from
    comparison pages we're allowed to read."""
    results = []
    for q in (f"best alternatives to {name}", f"{name} vs"):
        try:
            results += web.search(q, limit=8)
        except Exception:  # noqa: BLE001
            continue

    found: dict[str, dict] = {}

    def add(cname: str, url: str | None, **info) -> dict | None:
        cname = cname.strip()
        if not cname or _same_product(cname, name):
            return None
        key = next((k for k in found if _same_product(k, cname)), _norm(cname))
        entry = found.setdefault(
            key,
            {"name": cname, "why": None, "pros": [], "cons": [], "price": None, "mentions": 0, "sources": []},
        )
        entry["mentions"] += 1
        if url and url not in entry["sources"]:
            entry["sources"].append(url)
        if info.get("why") and not entry["why"]:
            entry["why"] = info["why"]
        if info.get("price") and not entry["price"]:
            entry["price"] = info["price"]
        entry["pros"] = list(dict.fromkeys(entry["pros"] + (info.get("pros") or [])))[:4]
        entry["cons"] = list(dict.fromkeys(entry["cons"] + (info.get("cons") or [])))[:4]
        return entry

    for r in results:
        for cname in names_from_result(r.label, r.url or ""):
            add(cname, r.url)

    for page in [r for r in results if r.allowed][:COMPETITOR_PAGES]:
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
            add(
                c.get("name") or "",
                page.url,
                why=c.get("why"),
                pros=c.get("pros"),
                cons=c.get("cons"),
                price=c.get("price"),
            )

    for e in found.values():
        if not e["why"]:
            n = e["mentions"]
            e["why"] = f"Compared with {name} in {n} comparison{'s' if n != 1 else ''} we found."
    return sorted(found.values(), key=lambda e: (-e["mentions"], -len(e["pros"])))[:3]


def _summary(
    name: str, report: dict, confidence: str, competitors: list[dict], show_rating: bool = True
) -> list[str]:
    out = []
    o = report.get("overall")
    if not o:
        return [f"We couldn't find enough reviews of {name} on the sources we can use."]
    rating = f" (average {o['average_rating']:.1f}★)" if show_rating and o.get("average_rating") else ""
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
