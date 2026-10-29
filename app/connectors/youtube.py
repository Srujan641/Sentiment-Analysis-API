"""YouTube Data API v3: review videos for a product, and their comments.

Quota (default 10,000 units/day): a search costs 100 units, a page of comments 1 unit.
Comments are noisy, so only ones that read like product opinions are kept: no links
(promotions), at least a few words, mostly Latin script (the sentiment model is English;
Hinglish support is on the roadmap), and mentioning the product or a product aspect.
"""

import html
import re
from datetime import datetime

import httpx

from app.analysis.aspects import keyword_aspects
from app.analysis.language import english_ratio
from app.connectors.base import Candidate, ConnectorError, RawReview

API = "https://www.googleapis.com/youtube/v3"
MIN_WORDS = 5
_LINK = re.compile(r"https?://|www\.|\[link\]", re.I)
_TIMESTAMP = re.compile(r"\b\d{1,2}:\d{2}\b")
# Buying questions and requests, not opinions about the product.
_QUESTION = re.compile(
    r"\?|^\s*(is|are|does|do|did|should|which|what|can|could|will|would|how|has|have|anyone)\b|confused between|"
    r"\bsuggest\b|\brecommend me\b|\bplease review\b|\bmake a video\b",
    re.I,
)
# Common romanised Hindi words: comments full of them are Hinglish, which the English
# model misreads, so they're skipped until code-mixed support lands.
_HINGLISH = {
    "hai",
    "hain",
    "nahi",
    "nhi",
    "kya",
    "bhi",
    "lekin",
    "aur",
    "ye",
    "yeh",
    "bahut",
    "bhut",
    "accha",
    "acha",
    "ka",
    "ki",
    "ke",
    "ko",
    "se",
    "mein",
    "mai",
    "toh",
    "jata",
    "jaata",
    "raha",
    "rha",
    "kar",
    "karo",
    "lo",
}


def classify_comment(text: str, product_terms: set[str]) -> str:
    """'opinion', or why it was skipped: link | short | other_script | code_mixed | question | off_topic."""
    if _LINK.search(text):
        return "link"
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < MIN_WORDS:
        return "short"
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isascii() for c in letters) / len(letters) < 0.8:
        return "other_script"
    if sum(w in _HINGLISH for w in words) / len(words) > 0.25 or english_ratio(text, product_terms) < 0.6:
        return "code_mixed"  # Hindi, Telugu, Tamil... written in English letters
    if _QUESTION.search(text):
        return "question"
    if keyword_aspects(text) or product_terms & set(words):
        return "opinion"
    return "off_topic"


def is_opinion(text: str, product_terms: set[str]) -> bool:
    return classify_comment(text, product_terms) == "opinion"


def _terms(name: str) -> set[str]:
    stop = {"the", "and", "with", "for", "pro", "max", "plus", "new"}
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 3 and w not in stop}


class YouTubeConnector:
    name = "youtube"
    label = "YouTube comments"
    requires = "Set YOUTUBE_API_KEY in .env (YouTube Data API v3 key from console.cloud.google.com)."

    def __init__(self, api_key: str | None, region: str = "IN", client: httpx.Client | None = None):
        self._key = api_key
        self.region = region
        self._client = client or httpx.Client(timeout=20)
        self.last_skipped: dict[str, int] = {}  # reasons comments were skipped on the last collect()

    def available(self) -> bool:
        return bool(self._key)

    def _get(self, path: str, **params) -> dict:
        if not self._key:
            raise ConnectorError(self.requires)
        r = self._client.get(f"{API}/{path}", params={**params, "key": self._key})
        if r.status_code == 403:
            reason = r.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
            if reason == "commentsDisabled":
                raise ConnectorError("Comments are turned off on this video.")
            if "quota" in reason.lower():
                raise ConnectorError("The YouTube API daily quota is used up; try again tomorrow.")
        if r.status_code == 404:
            raise ConnectorError("Video not found.")
        r.raise_for_status()
        return r.json()

    def discover(self, query: str, limit: int = 5) -> list[Candidate]:
        data = self._get(
            "search",
            part="snippet",
            q=f"{query} review",
            type="video",
            maxResults=min(limit, 10),
            regionCode=self.region,
            relevanceLanguage="en",
        )
        ids = [i["id"]["videoId"] for i in data.get("items", [])]
        stats = {}
        if ids:
            for v in self._get("videos", part="statistics", id=",".join(ids)).get("items", []):
                stats[v["id"]] = v.get("statistics", {})
        out = []
        for item in data.get("items", []):
            vid, sn = item["id"]["videoId"], item["snippet"]
            st = stats.get(vid, {})
            out.append(
                Candidate(
                    connector=self.name,
                    ref=vid,
                    label=html.unescape(sn.get("title", vid)),
                    url=f"https://www.youtube.com/watch?v={vid}",
                    detail=f"{html.unescape(sn.get('channelTitle', ''))} · {int(st.get('commentCount', 0)):,} comments",
                )
            )
        return out

    def collect(self, ref: str, product_name: str, limit: int = 300) -> list[RawReview]:
        terms = _terms(product_name)
        out: list[RawReview] = []
        self.last_skipped = {}
        page_token = None
        for _ in range(5):  # up to 500 comments read per video
            params = {
                "part": "snippet",
                "videoId": ref,
                "maxResults": 100,
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("commentThreads", **params)
            for item in data.get("items", []):
                c = item["snippet"]["topLevelComment"]["snippet"]
                text = _TIMESTAMP.sub(
                    " ", html.unescape(c.get("textOriginal") or c.get("textDisplay") or "")
                ).strip()
                kind = classify_comment(text, terms)
                if kind != "opinion":
                    self.last_skipped[kind] = self.last_skipped.get(kind, 0) + 1
                    continue
                published = c.get("publishedAt")
                out.append(
                    RawReview(
                        text=text,
                        reviewed_on=(
                            datetime.fromisoformat(published.replace("Z", "+00:00")).date()
                            if published
                            else None
                        ),
                        external_id=f"yt-{item['id']}",
                    )
                )
                if len(out) >= limit:
                    return out
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return out
