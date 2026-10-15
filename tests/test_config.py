from app.core.config import Settings


def test_csv_env_lists(monkeypatch):
    monkeypatch.setenv("API_KEYS", "a, b,c")
    monkeypatch.setenv("CORS_ORIGINS", '["https://x.dev"]')
    s = Settings(_env_file=None)
    assert s.api_keys == ["a", "b", "c"]
    assert s.cors_origins == ["https://x.dev"]


def test_canonical_labels():
    from app.core.model_loader import _canonical_labels

    assert _canonical_labels({0: "LABEL_0", 1: "LABEL_1"}) == ["NEGATIVE", "POSITIVE"]
    assert _canonical_labels({"0": "negative", "1": "positive"}) == ["NEGATIVE", "POSITIVE"]
