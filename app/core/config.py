"""Application settings, loaded from environment variables (and an optional .env file)."""

import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- service ---
    app_name: str = "Sentiment Analysis API"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # --- model ---
    # A local directory (models/distilbert-sentiment) or a Hugging Face Hub id.
    model_name_or_path: str = "models/distilbert-sentiment"
    max_sequence_length: int = Field(default=256, ge=16, le=512)
    # Texts per forward pass. /batch accepts at most this many so it is always one pass.
    inference_batch_size: int = Field(default=32, ge=1, le=256)
    device: str = "auto"  # auto | cpu | cuda | mps
    # Below this confidence a prediction is flagged `uncertain` (mixed or sarcastic reviews land here).
    uncertainty_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    num_threads: int | None = None

    # --- request limits ---
    max_text_length: int = Field(default=5000, ge=1)
    max_job_texts: int = Field(default=1000, ge=1)
    job_ttl_seconds: int = Field(default=3600, ge=60)

    # --- auth & rate limiting ---
    api_keys: CsvList = Field(default_factory=list)
    require_api_key: bool = False
    rate_limit_anonymous: str = "60/minute"
    rate_limit_authenticated: str = "300/minute"
    rate_limit_storage_uri: str = "memory://"
    rate_limit_enabled: bool = True

    # --- CORS ---
    cors_origins: CsvList = Field(default_factory=lambda: ["*"])

    # --- monitoring / drift ---
    prediction_log_path: str | None = "data/predictions.jsonl"
    drift_reference_path: str = "models/distilbert-sentiment/reference_stats.json"
    drift_window: int = Field(default=1000, ge=50)

    # --- platform ---
    # SQLite for development and tests; Postgres in production
    # (postgresql+psycopg://user:pass@host/db). Same code either way.
    database_url: str = "sqlite:///data/reviewpulse.db"
    session_ttl_days: int = Field(default=14, ge=1, le=90)
    # Set true behind HTTPS so the session cookie is never sent over plain HTTP.
    cookie_secure: bool = False
    auth_rate_limit: str = "10/minute"  # signup / login attempts per IP

    # --- review sources ---
    firecrawl_api_key: str | None = None  # enables the web connector
    store_country: str = "in"  # app-store country for search and reviews

    @field_validator("api_keys", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
