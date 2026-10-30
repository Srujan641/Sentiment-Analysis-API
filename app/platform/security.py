"""Passwords (Argon2id), API keys and session tokens (random, stored only as SHA-256 hashes)."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

KEY_PREFIX = "rp_live_"
_hasher = PasswordHasher()
# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Return (full_key, display_prefix, key_hash)."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[: len(KEY_PREFIX) + 4], sha256(key)


def new_session_token() -> tuple[str, str]:
    """Return (cookie_value, token_hash)."""
    token = secrets.token_urlsafe(32)
    return token, sha256(token)
