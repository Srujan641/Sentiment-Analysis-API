from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class Candidate:
    """A possible source for a product, shown to the user before they add it."""

    connector: str
    ref: str  # connector-specific id: "in:434613896" for an app, a URL for the web
    label: str
    url: str | None = None
    detail: str | None = None
    allowed: bool = True
    reason: str | None = None  # why it can't be used, when allowed is False


@dataclass
class RawReview:
    text: str
    rating: float | None = None
    reviewed_on: date | None = None
    external_id: str | None = None
    extra: dict = field(default_factory=dict)  # e.g. {"version": "27.4.0"}


class ConnectorError(Exception):
    """A source failed in an expected way (blocked, not found, quota); the message is shown to users."""


class Connector(Protocol):
    name: str
    label: str
    requires: str | None  # what must be configured, shown when unavailable

    def available(self) -> bool: ...

    def discover(self, query: str, limit: int = 5) -> list[Candidate]: ...

    def collect(self, ref: str, product_name: str, limit: int = 500) -> list[RawReview]: ...
