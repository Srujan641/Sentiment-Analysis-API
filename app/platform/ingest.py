"""Review ingestion: parsing uploads, removing personal data, de-duplicating (ING-1, ING-2, ING-8)."""

import csv
import hashlib
import html
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime

MAX_REVIEW_CHARS = 5000

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Indian and international phone numbers: 10+ digits with optional separators / country code.
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\d[\s-]?){9,11}\d(?!\d)")
_URL = re.compile(r"https?://\S+")
_SPACE = re.compile(r"\s+")

TEXT_COLUMNS = ("text", "review", "review_text", "content", "body", "comment")
RATING_COLUMNS = ("rating", "stars", "score", "star_rating")
DATE_COLUMNS = ("date", "reviewed_on", "review_date", "created_at", "timestamp")
ID_COLUMNS = ("id", "review_id", "external_id")


@dataclass
class CleanReview:
    text: str
    rating: float | None
    reviewed_on: date | None
    external_id: str | None
    content_hash: str


_TAG = re.compile(r"<[^>]{0,200}>")


def scrub(text: str) -> str:
    """Strip HTML (exports often contain <br />), then remove emails, phone numbers and links."""
    text = _TAG.sub(" ", html.unescape(text))
    text = _EMAIL.sub("[email]", text)
    text = _URL.sub("[link]", text)
    text = _PHONE.sub("[phone]", text)
    return _SPACE.sub(" ", text).strip()


def content_hash(text: str) -> str:
    """Hash of the normalised text, so trivial variations count as duplicates."""
    norm = re.sub(r"[^\w]+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()


def parse_rating(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        rating = float(str(value).strip().split("/")[0])
    except ValueError:
        return None
    return rating if 0 <= rating <= 5 else None


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if s.isdigit() and len(s) >= 10:  # unix seconds or milliseconds
        ts = int(s) / (1000 if len(s) >= 13 else 1)
        return datetime.fromtimestamp(ts).date()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def clean(raw: dict) -> CleanReview | None:
    text = scrub(str(raw.get("text") or ""))[:MAX_REVIEW_CHARS]
    if len(text) < 2:
        return None
    return CleanReview(
        text=text,
        rating=parse_rating(raw.get("rating")),
        reviewed_on=parse_date(raw.get("reviewed_on") or raw.get("date")),
        external_id=(str(raw["external_id"])[:200] if raw.get("external_id") else None),
        content_hash=content_hash(text),
    )


def _pick(row: dict, names: tuple[str, ...]):
    # "Review Date", "review-date" and "review_date" all match.
    lower = {re.sub(r"[\s-]+", "_", k.strip().lower()): v for k, v in row.items() if k}
    for n in names:
        if n in lower and lower[n] not in (None, ""):
            return lower[n]
    return None


def parse_upload(filename: str, data: bytes) -> list[dict]:
    """Parse a CSV or JSON upload into raw review dicts. Raises ValueError with a readable message."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("File must be UTF-8 encoded") from exc

    name = filename.lower()
    if name.endswith(".json") or name.endswith(".jsonl") or text.lstrip().startswith(("[", "{")):
        if name.endswith(".jsonl"):
            items = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            loaded = json.loads(text)
            items = loaded.get("reviews", []) if isinstance(loaded, dict) else loaded
        if not isinstance(items, list):
            raise ValueError('JSON must be a list of reviews or {"reviews": [...]}')
        rows = [i for i in items if isinstance(i, dict)]
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        if not any(
            f and re.sub(r"[\s-]+", "_", f.strip().lower()) in TEXT_COLUMNS for f in reader.fieldnames
        ):
            raise ValueError(f"CSV needs a text column named one of: {', '.join(TEXT_COLUMNS)}")
        rows = list(reader)

    return [
        {
            "text": _pick(r, TEXT_COLUMNS),
            "rating": _pick(r, RATING_COLUMNS),
            "reviewed_on": _pick(r, DATE_COLUMNS),
            "external_id": _pick(r, ID_COLUMNS),
        }
        for r in rows
    ]
