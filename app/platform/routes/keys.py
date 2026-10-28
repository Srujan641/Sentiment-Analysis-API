"""Self-serve API keys (ACC-4). Managed only by logged-in users, never by another key."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.deps import Principal, get_db, require_user
from app.platform.models import ApiKey
from app.platform.schemas import KeyCreate, KeyCreated, KeyOut
from app.platform.security import new_api_key

router = APIRouter(prefix="/keys", tags=["api keys"])
MAX_ACTIVE_KEYS = 10


@router.get("", response_model=list[KeyOut])
def list_keys(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(ApiKey).where(ApiKey.org_id == p.org.id).order_by(ApiKey.created_at.desc())
    ).all()


@router.post("", response_model=KeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(body: KeyCreate, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    active = db.scalars(select(ApiKey).where(ApiKey.org_id == p.org.id, ApiKey.revoked_at.is_(None))).all()
    if len(active) >= MAX_ACTIVE_KEYS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"At most {MAX_ACTIVE_KEYS} active keys; revoke one first"
        )
    full, prefix, key_hash = new_api_key()
    key = ApiKey(
        org_id=p.org.id, created_by=p.user.id, name=body.name.strip(), prefix=prefix, key_hash=key_hash
    )
    db.add(key)
    db.commit()
    return KeyCreated.model_validate({**KeyOut.model_validate(key).model_dump(), "key": full})


@router.delete("/{key_id}", response_model=KeyOut)
def revoke_key(key_id: str, p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    key = db.get(ApiKey, key_id)
    if key is None or key.org_id != p.org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        db.commit()
    return key
