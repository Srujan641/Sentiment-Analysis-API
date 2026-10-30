"""Split reviews into clauses, so "great sound but the battery dies" scores both parts."""

import re

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+|;\s*")
# Contrast words start a new clause; the word itself stays with the clause it introduces.
_CONTRAST = re.compile(
    r"\s*(?:,\s*)?\b(?=(?:but|however|although|though|except|whereas|yet|unfortunately|sadly)\b)", re.I
)
_MIN_WORDS = 2
MAX_CLAUSES = 12


def split_clauses(text: str) -> list[str]:
    clauses: list[str] = []
    for sentence in _SENTENCE.split(text):
        for part in _CONTRAST.split(sentence):
            part = part.strip(" ,.-–—")
            if not part:
                continue
            if len(part.split()) < _MIN_WORDS and clauses:
                clauses[-1] = f"{clauses[-1]} {part}"  # glue fragments like "Sad." to the previous clause
            else:
                clauses.append(part)
    return clauses[:MAX_CLAUSES] or [text.strip()]
