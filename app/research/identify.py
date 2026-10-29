"""Work out which product a user means, from a link or a name.

Marketplace links (Amazon, Flipkart) are never fetched: their URLs already contain the
product name, which is all we need to research the product on permitted sources.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from app.connectors.policy import blocked_reason

MAX_NAME_WORDS = 9
# Words marketplaces append to titles that don't help identify the product.
_NOISE = {
    "with",
    "for",
    "and",
    "the",
    "in",
    "of",
    "upto",
    "up",
    "to",
    "hours",
    "hrs",
    "playback",
    "mic",
    "black",
    "white",
    "blue",
    "red",
    "green",
    "grey",
    "gray",
    "silver",
    "gold",
    "pink",
    "purple",
    "colour",
    "color",
    "pack",
    "combo",
    "set",
    "new",
    "latest",
    "edition",
    "version",
    "free",
    "delivery",
    "online",
    "buy",
}


class IdentifyError(ValueError):
    """The input can't be turned into a product; the message tells the user what to do."""


@dataclass
class Identity:
    name: str
    source: str  # amazon_link | flipkart_link | google_link | web_page | url_path | name
    url: str | None = None


def _clean_slug(slug: str) -> str:
    words = [w for w in re.split(r"[-_+\s]+", unquote(slug)) if w]
    # Keep the brand/model words at the start; stop at the first run of descriptive noise.
    kept: list[str] = []
    for w in words:
        if len(kept) >= 3 and w.lower() in _NOISE:
            break
        kept.append(w)
        if len(kept) == MAX_NAME_WORDS:
            break
    name = " ".join(kept).strip()
    return name if re.search(r"[A-Za-z]", name) else ""


def _amazon(path_parts: list[str]) -> str:
    for marker in ("dp", "gp"):
        if marker in path_parts:
            i = path_parts.index(marker)
            if i > 0:
                return _clean_slug(path_parts[i - 1])
    return ""


def _flipkart(path_parts: list[str]) -> str:
    if "p" in path_parts:
        i = path_parts.index("p")
        if i > 0:
            return _clean_slug(path_parts[i - 1])
    return ""


def identify(query: str, page_reader=None) -> Identity:
    """`page_reader(url) -> product name or None` reads a permitted web page (Firecrawl)."""
    q = query.strip()
    if len(q) < 2:
        raise IdentifyError("Enter a product name or paste a product link.")
    if not re.match(r"^https?://", q, re.I):
        if q.lower().startswith("www.") or re.match(r"^[a-z0-9-]+\.[a-z.]{2,}/", q, re.I):
            q = "https://" + q
        else:
            return Identity(name=" ".join(q.split())[:200], source="name")

    url = urlparse(q)
    host = (url.hostname or "").lower()
    parts = [p for p in url.path.split("/") if p]

    if "amazon." in host or host.startswith("amzn."):
        name = _amazon(parts)
        if not name:
            raise IdentifyError(
                "This Amazon link doesn't include the product name (short or shared links don't). "
                "Open the product page and copy the full link, or type the product name."
            )
        return Identity(name=name, source="amazon_link", url=q)
    if "flipkart." in host:
        name = _flipkart(parts)
        if not name:
            raise IdentifyError(
                "This Flipkart link doesn't include the product name. Type the product name instead."
            )
        return Identity(name=name, source="flipkart_link", url=q)
    if "google." in host:
        terms = parse_qs(url.query).get("q", [""])[0].strip()
        if not terms:
            raise IdentifyError("This Google link has no search text. Type the product name instead.")
        terms = re.sub(r"\b(reviews?|price|vs|buy|online|best)\b", " ", terms, flags=re.I)
        return Identity(name=" ".join(terms.split())[:200], source="google_link", url=q)
    if blocked_reason(q):
        raise IdentifyError("Links from this marketplace can't be read. Type the product name instead.")

    if page_reader is not None:
        name = page_reader(q)
        if name:
            return Identity(name=name[:200], source="web_page", url=q)
    name = _clean_slug(parts[-1]) if parts else ""
    if not name:
        raise IdentifyError("Couldn't tell which product this link is about. Type the product name instead.")
    return Identity(name=name, source="url_path", url=q)
