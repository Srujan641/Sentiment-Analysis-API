"""Assign aspects to clauses, and discover issues outside the taxonomy.

1. Keywords (word-boundary match): precise, explainable.
2. Embeddings: a clause with no keyword is compared with each aspect's descriptive phrases;
   the best aspect is assigned if cosine similarity >= SIM_THRESHOLD.
3. Discovery: negative clauses that match nothing are clustered; clusters large enough to
   matter become new issues, named by their most distinctive words.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.analysis.taxonomy import ASPECTS

SIM_THRESHOLD = 0.45
MAX_ASPECTS_PER_CLAUSE = 3


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return L2-normalised embeddings, shape (len(texts), dim)."""
        ...


class SentenceTransformerEncoder:
    """Default encoder: all-MiniLM-L6-v2 (384-dim, CPU friendly). Loaded once per process."""

    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.MODEL, device=device)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            self._model.encode(list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        )


_KEYWORD_PATTERNS = [
    (
        a.name,
        re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in sorted(a.keywords, key=len, reverse=True)) + r")\b",
            re.I,
        ),
    )
    for a in ASPECTS
]


def keyword_aspects(clause: str) -> list[str]:
    return [name for name, pattern in _KEYWORD_PATTERNS if pattern.search(clause)][:MAX_ASPECTS_PER_CLAUSE]


class AspectMatcher:
    def __init__(self, encoder: Encoder):
        self.encoder = encoder
        vecs = []
        for a in ASPECTS:
            v = encoder.encode([*a.phrases, a.name]).mean(axis=0)
            vecs.append(v / (np.linalg.norm(v) or 1.0))
        self._centroids = np.vstack(vecs)
        self._names = [a.name for a in ASPECTS]

    @property
    def names(self) -> list[str]:
        return self._names

    def match(self, clauses: Sequence[str], embeddings: np.ndarray) -> list[list[str]]:
        sims = embeddings @ self._centroids.T if len(clauses) else np.zeros((0, len(self._names)))
        out = []
        for i, clause in enumerate(clauses):
            found = keyword_aspects(clause)
            if not found:
                j = int(np.argmax(sims[i]))
                if sims[i, j] >= SIM_THRESHOLD:
                    found = [self._names[j]]
            out.append(found)
        return out

    def nearest(self, text: str, threshold: float = SIM_THRESHOLD) -> str | None:
        """Map free text (e.g. a logged change's aspect) onto a taxonomy aspect."""
        found = keyword_aspects(text)
        if found:
            return found[0]
        sims = self.encoder.encode([text])[0] @ self._centroids.T
        j = int(np.argmax(sims))
        return self._names[j] if sims[j] >= threshold else None


@dataclass
class DiscoveredIssue:
    name: str
    members: list[int]  # indexes into the clauses passed to discover()


_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "it",
    "its",
    "is",
    "was",
    "were",
    "be",
    "been",
    "this",
    "that",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "my",
    "i",
    "me",
    "very",
    "so",
    "but",
    "not",
    "no",
    "after",
    "just",
    "too",
    "they",
    "them",
    "has",
    "have",
    "had",
    "are",
    "at",
    "as",
    "all",
    "one",
    "get",
    "got",
    "product",
    "item",
    "really",
    "also",
    "even",
    "only",
    "than",
    "then",
    "when",
    "will",
    "would",
    "could",
    "can",
    "does",
    "did",
    "do",
    "dont",
    "don",
    "t",
    "s",
    "within",
    "days",
    "day",
    "week",
    "weeks",
    "however",
    "though",
    "although",
    "unfortunately",
    "sadly",
    "bad",
    "poor",
    "worst",
    "terrible",
    "good",
    "great",
    "like",
    "bit",
    # generic opinion words that name no specific problem
    "star",
    "stars",
    "disappointed",
    "disappointing",
    "disappointment",
    "am",
    "love",
    "loved",
    "hate",
    "awful",
    "horrible",
    "waste",
    "money",
    "buy",
    "bought",
    "ordered",
    "order",
    "received",
    "use",
    "used",
    "using",
    "work",
    "works",
    "worked",
    "working",
    "amazon",
    "seller",
    "review",
    "don't",
    "didn",
    "doesn",
    "isn",
    "wasn",
    "won",
    "ok",
    "okay",
    "nice",
    "best",
    "better",
    "much",
    "more",
    "less",
    "time",
    "first",
    "two",
    "three",
    "out",
    "up",
    "what",
    "which",
    "there",
    "here",
    "some",
    "any",
    "back",
    "never",
}
# Time and filler words: never meaningful as an issue name.
_STOP |= {
    "now",
    "today",
    "yesterday",
    "again",
    "still",
    "ever",
    "always",
    "every",
    "since",
    "ago",
    "yet",
    "please",
    "pls",
    "plz",
    "app",
    "application",
    "experience",
    "service",
    "worst",
    "pathetic",
    "useless",
}
GENERIC = {"product", "item", "quality", "thing", "stuff", "purchase"}


def discover(
    clauses: Sequence[str],
    embeddings: np.ndarray,
    min_size: int = 3,
    corpus: Sequence[str] | None = None,
    exclude: set[str] = frozenset(),
) -> list[DiscoveredIssue]:
    """Cluster negative clauses; name each cluster by its most distinctive words.

    `corpus` (all of the product's clauses) sets the word weights, so words used everywhere
    for this product ("mat", "spray") don't become issue names.
    """
    n = len(clauses)
    if n < min_size:
        return []
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.feature_extraction.text import TfidfVectorizer

    labels = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=0.45
    ).fit_predict(embeddings)

    vec = TfidfVectorizer(
        stop_words=list(_STOP | set(exclude)),
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
    )
    try:
        vec.fit(list(corpus) if corpus else clauses)
        tfidf = vec.transform(clauses)
    except ValueError:  # only stop words
        return []
    vocab = np.array(vec.get_feature_names_out())

    issues = []
    for label in set(labels):
        members = [i for i in range(n) if labels[i] == label]
        if len(members) < min_size:
            continue
        scores = np.asarray(tfidf[members].mean(axis=0)).ravel()
        order = np.argsort(scores)[::-1][:3]
        top = [vocab[j] for j in order if scores[j] > 0 and vocab[j] not in GENERIC]
        if not top:
            continue
        # A word must appear in at least a third of the cluster to name it; otherwise the
        # cluster has no shared vocabulary and is too vague to report as a specific issue.
        support = np.asarray((tfidf[members][:, list(vocab).index(top[0])] > 0).sum())
        if support < max(2, len(members) / 3):
            continue
        # Prefer a bigram if it covers the top unigram ("charging case" over "case").
        name = next((w for w in top if " " in w and top[0] in w.split()), top[0])
        issues.append(DiscoveredIssue(name=name, members=members))
    return sorted(issues, key=lambda d: -len(d.members))
