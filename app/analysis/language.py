"""How much of a text is English, measured against the sentiment model's own vocabulary.

The model reads English; comments in Hindi, Telugu, Tamil and other languages written in
Latin letters (code-mixed) are misread, so connectors skip them and say so. Clear English
scores ~0.8-1.0; code-mixed comments ~0.2-0.6.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

_WORD = re.compile(r"[a-z]+")
# Contractions people type without the apostrophe.
_CONTRACTIONS = {
    "dont",
    "cant",
    "wont",
    "didnt",
    "doesnt",
    "isnt",
    "wasnt",
    "arent",
    "ive",
    "its",
    "thats",
    "theres",
}


@lru_cache(maxsize=1)
def _domain_words() -> frozenset[str]:
    """Product vocabulary the general model splits into pieces (headphones, earbuds...)."""
    from app.analysis.taxonomy import ASPECTS

    words = {w for a in ASPECTS for k in a.keywords for w in k.split()}
    words |= {
        "headphones",
        "headphone",
        "earbuds",
        "earphones",
        "smartwatch",
        "smartphone",
        "laptop",
        "charger",
        "bluetooth",
        "anc",
        "earcups",
        "cushions",
        "bass",
        "treble",
        "mic",
        "app",
        "apps",
        "ui",
        "fps",
    }
    return frozenset(words)


@lru_cache(maxsize=1)
def _vocab() -> frozenset[str]:
    from app.core.config import get_settings

    path = Path(get_settings().model_name_or_path) / "tokenizer.json"
    try:
        return frozenset(json.loads(path.read_text())["model"]["vocab"])
    except (OSError, KeyError, ValueError):
        return frozenset()


def english_ratio(text: str, extra: set[str] | frozenset[str] = frozenset()) -> float:
    """Share of words (3+ letters) that are English, product vocabulary, or in `extra`."""
    vocab = _vocab()
    if not vocab:
        return 1.0  # no vocabulary available: don't filter
    words = [w for w in _WORD.findall(text.lower()) if len(w) >= 3]
    if not words:
        return 1.0

    domain = _domain_words()

    def known(w: str) -> bool:
        if w in vocab or w in domain or w in extra or w in _CONTRACTIONS:
            return True
        return (w.endswith("s") and w[:-1] in vocab) or (w.endswith("es") and w[:-2] in vocab)

    return sum(known(w) for w in words) / len(words)
