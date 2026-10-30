"""Platform data model.

Every customer-owned row carries `org_id`; all reads and writes are scoped by it.
Individuals get a personal organization, so one code path serves both account types.
Reviewer identities are never stored (requirements ING-8, NFR-6).
"""

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class AccountType(enum.StrEnum):
    individual = "individual"
    organization = "organization"


class Role(enum.StrEnum):
    owner = "owner"
    member = "member"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    plan: Mapped[str] = mapped_column(String(20), default="free")  # see app/platform/plans.py
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="org")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.owner)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    org: Mapped[Organization] = relationship(back_populates="users")


class WebSession(Base):
    """Website login sessions. Only a hash of the cookie value is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ApiKey(Base):
    """API keys. The full key is shown once at creation; only its SHA-256 hash is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(16))  # e.g. "rp_live_a1b2" for display
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120))
    identifiers: Mapped[str | None] = mapped_column(Text)  # JSON: {"asin": ..., "gtin": ..., "app_id": ...}
    links: Mapped[str | None] = mapped_column(Text)  # JSON list of URLs
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    changes: Mapped[list["ProductChange"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductChange.changed_on"
    )


class ProductChange(Base):
    """A change the brand shipped (supplier, packaging, firmware...). Drives fix verification."""

    __tablename__ = "product_changes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    changed_on: Mapped[date] = mapped_column(Date)
    aspects: Mapped[str] = mapped_column(Text)  # JSON list, e.g. ["battery life"]
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    product: Mapped[Product] = relationship(back_populates="changes")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "content_hash", name="uq_review_product_content"),
        Index("ix_reviews_product_date", "product_id", "reviewed_on"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(
        String(40)
    )  # upload | api | app_store | google_play | youtube | reddit | web
    external_id: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Float)
    reviewed_on: Mapped[date | None] = mapped_column(Date)
    language: Mapped[str | None] = mapped_column(String(12))
    content_hash: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageCounter(Base):
    """Monthly usage per organization and metric, e.g. ("2026-10", "reviews_ingested")."""

    __tablename__ = "usage_counters"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM
    metric: Mapped[str] = mapped_column(String(40), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Analysis(Base):
    """One analysis run (quick or full) of a product's reviews; the report is stored as JSON."""

    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_product_created", "product_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))  # quick | full
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued | running | complete | failed
    stage: Mapped[str | None] = mapped_column(String(60))
    error: Mapped[str | None] = mapped_column(Text)
    review_count: Mapped[int | None] = mapped_column(Integer)
    report: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductSource(Base):
    """A place reviews are collected from for a product: an app, a web page, a video..."""

    __tablename__ = "product_sources"
    __table_args__ = (UniqueConstraint("product_id", "connector", "ref", name="uq_source_product_ref"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    connector: Mapped[str] = mapped_column(String(30))
    ref: Mapped[str] = mapped_column(String(500))
    label: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(1000))
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_added: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CollectionRun(Base):
    """One "collect now" job across a product's sources; per-source results stored as JSON."""

    __tablename__ = "collection_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    stage: Mapped[str | None] = mapped_column(String(200))
    results: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Research(Base):
    """A personal product research: link or name in, summary and competitors out."""

    __tablename__ = "researches"
    __table_args__ = (Index("ix_researches_org_created", "org_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    query: Mapped[str] = mapped_column(Text)  # what the user typed or pasted
    product_name: Mapped[str | None] = mapped_column(String(300))
    identified_from: Mapped[str | None] = mapped_column(
        String(60)
    )  # amazon_link | flipkart_link | web_page | name
    status: Mapped[str] = mapped_column(String(12), default="queued")
    stage: Mapped[str | None] = mapped_column(String(200))
    error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
