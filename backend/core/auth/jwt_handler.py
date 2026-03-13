"""
JWT Token Handler — Creates, validates, and manages JWT tokens in httpOnly cookies.

SECURITY ARCHITECTURE:
  - Access tokens are stored in httpOnly cookies (JS cannot read them)
  - Refresh tokens are stored in httpOnly cookies with a separate path
  - CSRF tokens are generated per-session and validated on every mutation
  - Refresh token hashes are stored in pp_user_sessions for revocation
  - OAuth2.0 social login will also use this same cookie-based flow

Why httpOnly cookies instead of localStorage/Authorization headers:
  1. httpOnly cookies are immune to XSS attacks (JS can't read them)
  2. They're sent automatically by the browser on every request
  3. With SameSite=Lax, they're protected against CSRF from other sites
  4. We add an additional CSRF token for defense-in-depth

The flow:
  Login → Backend sets httpOnly cookie with access_token + refresh_token
  Every request → Browser sends cookies automatically → Backend validates
  Token refresh → Backend reads refresh cookie, issues new access cookie
  Logout → Backend clears both cookies + revokes session in DB
"""
from __future__ import annotations

import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError
from passlib.context import CryptContext

from backend.core.config import get_settings
from backend.core.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

# ── Password Hashing (bcrypt, not WordPress's phpass/MD5) ────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Creation ───────────────────────────────────────────────

def create_access_token(user_id: int, username: str, roles: list[str],
                        extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a short-lived JWT access token.
    This token proves "who the user is" and "what they can do".
    It's stored in an httpOnly cookie, never in JS-accessible storage.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": expires,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived refresh token.
    When the access token expires, the frontend silently uses this
    to get a new access token without forcing re-login.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    # Include a random jti (JWT ID) so each refresh token is unique
    # and can be individually revoked.
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises InvalidTokenError if expired, tampered, or malformed.
    """
    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError(f"Invalid token: {exc}")


# ── Refresh Token Hashing (for DB storage) ───────────────────────────
# We NEVER store raw refresh tokens in the database. We store their
# SHA-256 hash. When a refresh request comes in, we hash the incoming
# token and look up the hash in pp_user_sessions.

def hash_refresh_token(token: str) -> str:
    """Create a SHA-256 hash of a refresh token for safe DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── CSRF Token Management ────────────────────────────────────────────
# CSRF protection uses the "double-submit cookie" pattern:
#   1. On login, we set a CSRF token in a REGULAR (non-httpOnly) cookie
#   2. The frontend reads this cookie and sends it in X-CSRF-Token header
#   3. The backend compares the header value with the cookie value
#   4. An attacker from another domain can't read our cookies, so
#      they can't send the correct header, blocking CSRF attacks.

def generate_csrf_token(user_id: int) -> str:
    """
    Generate a CSRF token tied to a user session.
    This is stored in a regular cookie (readable by JS) and must be
    sent back as a header on every mutation (POST/PUT/DELETE) request.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.CSRF_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "csrf",
        "nonce": secrets.token_hex(8),
        "exp": expires,
    }
    return jwt.encode(payload, settings.CSRF_SECRET, algorithm=settings.JWT_ALGORITHM)


def validate_csrf_token(token: str) -> dict[str, Any]:
    """Validate a CSRF token. Raises InvalidTokenError on failure."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.CSRF_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError(f"Invalid CSRF token: {exc}")


# ── Cookie Helper Constants ──────────────────────────────────────────
# These are the cookie names used throughout the auth system.

ACCESS_TOKEN_COOKIE = "pypress_access_token"
REFRESH_TOKEN_COOKIE = "pypress_refresh_token"
CSRF_TOKEN_COOKIE = "pypress_csrf_token"
