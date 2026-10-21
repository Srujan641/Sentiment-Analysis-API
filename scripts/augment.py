"""Realistic typo noise for training-time augmentation and robustness evaluation.

Amazon reviews are mostly well spelled, so a model trained on them alone can flip on a single
misspelling: "stoped" tokenizes to `stop` + `##ed` and loses the strong "stopped working" signal.
Training on a share of corrupted reviews teaches the model to read through that noise.
"""

import random

# QWERTY neighbours, for fat-finger substitutions.
_KEYBOARD = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop",
    "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "awedxz",
    "t": "rfgy", "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}  # fmt: skip


def typo_word(word: str, rng: random.Random) -> str:
    """One realistic typo in `word`. The first letter is kept: people rarely get it wrong."""
    doubles = [i for i in range(1, len(word) - 1) if word[i] == word[i + 1] and word[i].isalpha()]
    if doubles and rng.random() < 0.5:  # stopped -> stoped, really -> realy
        i = rng.choice(doubles)
        return word[:i] + word[i + 1 :]

    i = rng.randrange(1, len(word))
    op = rng.choice(("delete", "swap", "double", "neighbour"))
    if op == "delete":
        return word[:i] + word[i + 1 :]
    if op == "swap" and i < len(word) - 1 and word[i] != word[i + 1]:
        return word[:i] + word[i + 1] + word[i] + word[i + 2 :]
    if op == "double":
        return word[:i] + word[i] + word[i:]
    near = _KEYBOARD.get(word[i].lower())
    if near:
        return word[:i] + rng.choice(near) + word[i + 1 :]
    return word[:i] + word[i + 1 :]


def add_typos(text: str, rng: random.Random, word_rate: float = 0.15) -> str:
    """Misspell roughly `word_rate` of the alphabetic words of 4+ letters (at least one)."""
    words = text.split(" ")
    # Trailing punctuation ("working.") is set aside so the word itself still qualifies.
    cores = [w.rstrip(".,!?;:") for w in words]
    candidates = [i for i, c in enumerate(cores) if len(c) >= 4 and c.isalpha()]
    if not candidates:
        return text
    chosen = [i for i in candidates if rng.random() < word_rate] or [rng.choice(candidates)]
    for i in chosen:
        words[i] = typo_word(cores[i], rng) + words[i][len(cores[i]) :]
    return " ".join(words)
