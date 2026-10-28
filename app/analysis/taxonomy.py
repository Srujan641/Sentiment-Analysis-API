"""Generic product aspects.

Each aspect has keywords (high-precision matching) and descriptive phrases (embedded for
semantic matching of clauses that use other words). Issues outside this list are found by
clustering (app/analysis/aspects.py: discover).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Aspect:
    name: str
    keywords: tuple[str, ...]
    phrases: tuple[str, ...]


ASPECTS: tuple[Aspect, ...] = (
    Aspect(
        "battery life",
        ("battery", "batteries", "battery life", "drains", "backup", "mah"),
        ("the battery dies quickly", "battery lasts all day", "poor battery backup"),
    ),
    Aspect(
        "charging",
        ("charging", "charger", "charge", "cable", "charging case", "type-c", "usb"),
        ("it takes long to charge", "the charger stopped working", "charging is fast"),
    ),
    Aspect(
        "sound quality",
        ("sound", "audio", "bass", "treble", "volume", "noise cancellation", "anc", "speaker"),
        ("the sound quality is great", "audio is muffled", "bass is weak"),
    ),
    Aspect(
        "microphone and calls",
        ("mic", "microphone", "calls", "call quality", "caller", "voice"),
        ("people can't hear me on calls", "mic quality is poor", "clear voice on calls"),
    ),
    Aspect(
        "connectivity",
        (
            "bluetooth",
            "pairing",
            "pair",
            "connection",
            "connectivity",
            "wifi",
            "wi-fi",
            "disconnect",
            "signal",
        ),
        ("it keeps disconnecting", "bluetooth pairing fails", "connection is stable"),
    ),
    Aspect(
        "display",
        ("screen", "display", "brightness", "resolution", "touchscreen"),
        ("the screen is not bright", "display quality is sharp"),
    ),
    Aspect(
        "performance",
        ("performance", "lag", "laggy", "slow", "speed", "hangs", "freezes", "processor"),
        ("it is slow and lags", "performance is smooth and fast"),
    ),
    Aspect(
        "software and app",
        ("app", "software", "firmware", "update", "crash", "crashes", "bug", "glitch"),
        ("the app keeps crashing", "after the update it stopped working"),
    ),
    Aspect(
        "build quality",
        ("build", "material", "plastic", "flimsy", "sturdy", "cheap feel", "finish", "quality"),
        ("it feels cheap and flimsy", "solid build and premium materials"),
    ),
    Aspect(
        "durability",
        (
            "broke",
            "broken",
            "stopped working",
            "died",
            "durable",
            "lasted",
            "fell apart",
            "cracked",
            "defective",
            "dead",
        ),
        ("it stopped working after a week", "broke within a month", "still working after a year"),
    ),
    Aspect(
        "comfort and fit",
        (
            "fit",
            "fits",
            "fitting",
            "comfortable",
            "comfort",
            "uncomfortable",
            "too tight",
            "too loose",
            "loose fit",
            "hurts",
            "ear pain",
            "ears hurt",
            "size",
            "sizing",
        ),
        ("it hurts my ears after an hour", "fits perfectly and is comfortable", "size runs small"),
    ),
    Aspect(
        "design and looks",
        ("design", "look", "looks", "colour", "color", "style", "stylish", "beautiful", "ugly"),
        ("it looks stylish", "the colour is different from the picture"),
    ),
    Aspect(
        "ease of use",
        (
            "easy to use",
            "setup",
            "set up",
            "instructions",
            "manual",
            "controls",
            "buttons",
            "touch controls",
            "user friendly",
        ),
        ("setup was easy", "the controls are confusing"),
    ),
    Aspect(
        "price and value",
        ("price", "value", "worth", "expensive", "cheap", "money", "costly", "overpriced", "budget"),
        ("good value for money", "too expensive for what you get"),
    ),
    Aspect(
        "delivery",
        ("delivery", "delivered", "shipping", "shipped", "courier", "arrived", "late", "dispatch"),
        ("delivery was late", "arrived on time"),
    ),
    Aspect(
        "packaging",
        ("packaging", "package", "packed", "box", "seal", "sealed", "damaged box"),
        ("the box was damaged", "nicely packed"),
    ),
    Aspect(
        "customer service",
        (
            "customer service",
            "support",
            "customer care",
            "refund",
            "return",
            "replacement",
            "warranty",
            "service center",
        ),
        ("customer support never replied", "replacement was quick"),
    ),
    Aspect(
        "authenticity and description",
        ("fake", "duplicate", "original", "genuine", "not as described", "different from", "counterfeit"),
        ("this is not the original product", "not as shown in the picture"),
    ),
    Aspect(
        "fragrance",
        ("smell", "fragrance", "scent", "odour", "odor", "perfume"),
        ("the smell is too strong", "lovely fragrance"),
    ),
    Aspect(
        "taste",
        ("taste", "flavour", "flavor", "tasty", "bland", "bitter"),
        ("it tastes bland", "great flavour"),
    ),
    Aspect(
        "skin and hair effect",
        ("skin", "hair", "rash", "irritation", "acne", "breakout", "itching", "moisturising", "moisturizing"),
        ("it caused a rash on my skin", "my hair feels soft"),
    ),
    Aspect(
        "quantity",
        ("quantity", "less quantity", "half empty", "ml", "grams", "small bottle"),
        ("the quantity is too less for the price", "the bottle was half empty"),
    ),
)

ASPECT_NAMES = tuple(a.name for a in ASPECTS)
OVERALL = "overall"
