import random

from scripts.augment import add_typos, typo_word


def test_typo_word_changes_word_but_keeps_first_letter():
    rng = random.Random(0)
    for word in ["stopped", "working", "battery", "charger", "product"]:
        for _ in range(20):
            out = typo_word(word, rng)
            assert out != word
            assert out[0] == word[0]


def test_add_typos_is_deterministic_and_preserves_punctuation():
    text = "Great product. Stopped working after one hour."
    a = add_typos(text, random.Random(7))
    b = add_typos(text, random.Random(7))
    assert a == b and a != text
    assert a.endswith(".") and len(a.split(" ")) == len(text.split(" "))


def test_add_typos_leaves_short_text_alone():
    assert add_typos("ok so bad", random.Random(1)) == "ok so bad"
