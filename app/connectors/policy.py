"""Which web sources may be collected from (docs/REQUIREMENTS.md section 7).

1. Marketplaces whose terms prohibit automated collection are blocked outright, whatever
   tool is used. Brands get that data through uploads or the marketplace's official API.
2. Every other URL must be allowed by the site's robots.txt for our user agent.
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ReviewPulseBot/1.0 (+https://github.com/Srujan641/Sentiment-Analysis-API)"

BLOCKED_DOMAINS = {
    "amazon": "Amazon's terms prohibit automated collection. Upload your Seller Central export instead; "
    "the official Amazon seller connector is planned.",
    "flipkart": "Flipkart's terms prohibit automated collection. Upload your seller review export instead.",
    "myntra": "Myntra's terms prohibit automated collection.",
    "meesho": "Meesho's terms prohibit automated collection.",
    "ajio": "Ajio's terms prohibit automated collection.",
    "snapdeal": "Snapdeal's terms prohibit automated collection.",
}

_robots_cache: dict[str, RobotFileParser | None] = {}


def blocked_reason(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    labels = host.split(".")
    for name, reason in BLOCKED_DOMAINS.items():
        if name in labels or any(label.startswith(name) for label in labels[:-1]):
            return reason
    return None


def _robots(origin: str, client: httpx.Client | None = None) -> RobotFileParser | None:
    if origin in _robots_cache:
        return _robots_cache[origin]
    parser = RobotFileParser()
    try:
        c = client or httpx.Client(timeout=8, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        r = c.get(f"{origin}/robots.txt")
        if r.status_code in (401, 403):
            parser.disallow_all = True
        elif r.status_code >= 400:
            parser.allow_all = True  # no robots.txt: crawling is permitted by convention
        else:
            parser.parse(r.text.splitlines())
    except httpx.HTTPError:
        parser = None  # unreachable: treat as not allowed
    _robots_cache[origin] = parser
    return parser


def check_url(url: str, client: httpx.Client | None = None) -> tuple[bool, str | None]:
    """Return (allowed, reason_if_not)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False, "Only http(s) links can be collected."
    reason = blocked_reason(url)
    if reason:
        return False, reason
    parser = _robots(f"{parsed.scheme}://{parsed.hostname}", client)
    if parser is None:
        return False, "The site's robots.txt couldn't be read, so we don't collect from it."
    if not parser.can_fetch(USER_AGENT, url):
        return False, "The site's robots.txt doesn't allow automated access to this page."
    return True, None
