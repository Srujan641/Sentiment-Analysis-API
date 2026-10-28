"""Request and response models for the /v1 platform API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    name: str = Field(..., min_length=1, max_length=120)
    account_type: Literal["individual", "organization"] = "individual"
    organization_name: str | None = Field(None, max_length=120)

    @field_validator("name", "organization_name")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class OrgOut(_Out):
    id: str
    name: str
    account_type: str
    plan: str


class UserOut(_Out):
    id: str
    email: str
    name: str
    role: str


class MeResponse(BaseModel):
    user: UserOut
    organization: OrgOut


# ---------- keys ----------
class KeyCreate(BaseModel):
    name: str = Field("Default key", min_length=1, max_length=80)


class KeyOut(_Out):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class KeyCreated(KeyOut):
    key: str = Field(..., description="The full key. Shown only once; store it securely.")


# ---------- products ----------
class ProductIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brand: str | None = Field(None, max_length=120)
    category: str | None = Field(None, max_length=120)
    identifiers: dict[str, str] = Field(
        default_factory=dict, description='e.g. {"asin": "...", "app_id": "..."}'
    )
    links: list[str] = Field(default_factory=list, max_length=20)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    brand: str | None = Field(None, max_length=120)
    category: str | None = Field(None, max_length=120)
    identifiers: dict[str, str] | None = None
    links: list[str] | None = Field(None, max_length=20)


class ProductOut(BaseModel):
    id: str
    name: str
    brand: str | None
    category: str | None
    identifiers: dict[str, str]
    links: list[str]
    review_count: int
    archived: bool
    created_at: datetime


class ChangeIn(BaseModel):
    changed_on: date
    aspects: list[str] = Field(..., min_length=1, max_length=10)
    description: str = Field(..., min_length=3, max_length=1000)

    @field_validator("aspects")
    @classmethod
    def _norm(cls, v):
        out = [a.strip().lower() for a in v if a.strip()]
        if not out:
            raise ValueError("at least one aspect is required")
        return out


class ChangeOut(BaseModel):
    id: str
    changed_on: date
    aspects: list[str]
    description: str
    created_at: datetime


# ---------- reviews ----------
class ReviewIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    rating: float | None = Field(None, ge=0, le=5)
    reviewed_on: date | None = None
    external_id: str | None = Field(None, max_length=200)


class ReviewBatch(BaseModel):
    reviews: list[ReviewIn] = Field(..., min_length=1, max_length=1000)
    source: str = Field("api", pattern=r"^[a-z0-9_]{2,40}$")


class IngestResult(BaseModel):
    received: int
    added: int
    duplicates: int
    rejected: int
    remaining_this_month: int | None


class ReviewOut(_Out):
    id: str
    source: str
    text: str
    rating: float | None
    reviewed_on: date | None
    ingested_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewOut]
    total: int
    limit: int
    offset: int
