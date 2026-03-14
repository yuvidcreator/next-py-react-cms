# """
# JWT Token Handler — Creates, validates, and manages JWT tokens in httpOnly cookies.

# SECURITY ARCHITECTURE:
#   - Access tokens are stored in httpOnly cookies (JS cannot read them)
#   - Refresh tokens are stored in httpOnly cookies with a separate path
#   - CSRF tokens are generated per-session and validated on every mutation
#   - Refresh token hashes are stored in pp_user_sessions for revocation
#   - OAuth2.0 social login will also use this same cookie-based flow

# Why httpOnly cookies instead of localStorage/Authorization headers:
#   1. httpOnly cookies are immune to XSS attacks (JS can't read them)
#   2. They're sent automatically by the browser on every request
#   3. With SameSite=Lax, they're protected against CSRF from other sites
#   4. We add an additional CSRF token for defense-in-depth

# The flow:
#   Login → Backend sets httpOnly cookie with access_token + refresh_token
#   Every request → Browser sends cookies automatically → Backend validates
#   Token refresh → Backend reads refresh cookie, issues new access cookie
#   Logout → Backend clears both cookies + revokes session in DB
# """
# from __future__ import annotations

# import hashlib
# import secrets
# import logging
# from datetime import datetime, timedelta, timezone
# from typing import Any

# from jose import jwt, JWTError
# from passlib.context import CryptContext

# from backend.app.core.config import get_settings
# from backend.app.core.exceptions import InvalidTokenError

# logger = logging.getLogger(__name__)

# # ── Password Hashing (bcrypt, not WordPress's phpass/MD5) ────────────
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# def hash_password(password: str) -> str:
#     """Hash a plaintext password using bcrypt."""
#     return pwd_context.hash(password)


# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     """Verify a plaintext password against its bcrypt hash."""
#     return pwd_context.verify(plain_password, hashed_password)


# # ── JWT Token Creation ───────────────────────────────────────────────

# def create_access_token(user_id: int, username: str, roles: list[str],
#                         extra_claims: dict[str, Any] | None = None) -> str:
#     """
#     Create a short-lived JWT access token.
#     This token proves "who the user is" and "what they can do".
#     It's stored in an httpOnly cookie, never in JS-accessible storage.
#     """
#     settings = get_settings()
#     now = datetime.now(timezone.utc)
#     expires = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
#     payload = {
#         "sub": str(user_id),
#         "username": username,
#         "roles": roles,
#         "type": "access",
#         "iat": now,
#         "exp": expires,
#     }
#     if extra_claims:
#         payload.update(extra_claims)
#     return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# def create_refresh_token(user_id: int) -> str:
#     """
#     Create a long-lived refresh token.
#     When the access token expires, the frontend silently uses this
#     to get a new access token without forcing re-login.
#     """
#     settings = get_settings()
#     now = datetime.now(timezone.utc)
#     expires = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
#     # Include a random jti (JWT ID) so each refresh token is unique
#     # and can be individually revoked.
#     payload = {
#         "sub": str(user_id),
#         "type": "refresh",
#         "jti": secrets.token_hex(16),
#         "iat": now,
#         "exp": expires,
#     }
#     return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# def decode_token(token: str) -> dict[str, Any]:
#     """
#     Decode and validate a JWT token.
#     Raises InvalidTokenError if expired, tampered, or malformed.
#     """
#     settings = get_settings()
#     try:
#         return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
#     except JWTError as exc:
#         raise InvalidTokenError(f"Invalid token: {exc}")


# # ── Refresh Token Hashing (for DB storage) ───────────────────────────
# # We NEVER store raw refresh tokens in the database. We store their
# # SHA-256 hash. When a refresh request comes in, we hash the incoming
# # token and look up the hash in pp_user_sessions.

# def hash_refresh_token(token: str) -> str:
#     """Create a SHA-256 hash of a refresh token for safe DB storage."""
#     return hashlib.sha256(token.encode("utf-8")).hexdigest()


# # ── CSRF Token Management ────────────────────────────────────────────
# # CSRF protection uses the "double-submit cookie" pattern:
# #   1. On login, we set a CSRF token in a REGULAR (non-httpOnly) cookie
# #   2. The frontend reads this cookie and sends it in X-CSRF-Token header
# #   3. The backend compares the header value with the cookie value
# #   4. An attacker from another domain can't read our cookies, so
# #      they can't send the correct header, blocking CSRF attacks.

# def generate_csrf_token(user_id: int) -> str:
#     """
#     Generate a CSRF token tied to a user session.
#     This is stored in a regular cookie (readable by JS) and must be
#     sent back as a header on every mutation (POST/PUT/DELETE) request.
#     """
#     settings = get_settings()
#     now = datetime.now(timezone.utc)
#     expires = now + timedelta(minutes=settings.CSRF_TOKEN_EXPIRE_MINUTES)
#     payload = {
#         "sub": str(user_id),
#         "type": "csrf",
#         "nonce": secrets.token_hex(8),
#         "exp": expires,
#     }
#     return jwt.encode(payload, settings.CSRF_SECRET, algorithm=settings.JWT_ALGORITHM)


# def validate_csrf_token(token: str) -> dict[str, Any]:
#     """Validate a CSRF token. Raises InvalidTokenError on failure."""
#     settings = get_settings()
#     try:
#         return jwt.decode(token, settings.CSRF_SECRET, algorithms=[settings.JWT_ALGORITHM])
#     except JWTError as exc:
#         raise InvalidTokenError(f"Invalid CSRF token: {exc}")


# # ── Cookie Helper Constants ──────────────────────────────────────────
# # These are the cookie names used throughout the auth system.

# ACCESS_TOKEN_COOKIE = "pypress_access_token"
# REFRESH_TOKEN_COOKIE = "pypress_refresh_token"
# CSRF_TOKEN_COOKIE = "pypress_csrf_token"





"""
PyPress — JWT Token Handler

Creates, validates, and manages JWT tokens for the httpOnly cookie auth system.

Token types:
  - Access token:  Short-lived (15min default), contains user ID + roles
  - Refresh token: Long-lived (30d default), contains only user ID + type marker
  - CSRF token:    Not a JWT — a random string for the double-submit pattern

Password hashing uses bcrypt (not WordPress's MD5/phpass).
Refresh tokens are stored as SHA-256 hashes in the database (never raw).

WordPress equivalent: wp-includes/pluggable.php (wp_hash_password,
wp_check_password) + wp-includes/class-wp-session-tokens.php
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Cookie Names ─────────────────────────────────────────────────────────
# These constants are used by both the auth router (setting cookies) and
# the auth dependencies (reading cookies from incoming requests).
ACCESS_TOKEN_COOKIE = "pypress_access_token"
REFRESH_TOKEN_COOKIE = "pypress_refresh_token"
CSRF_TOKEN_COOKIE = "pypress_csrf_token"

# ── Password Hashing ────────────────────────────────────────────────────
# bcrypt with automatic salt generation. Cost factor 12 is a good balance
# between security and performance (~250ms per hash on modern hardware).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. WordPress equivalent: wp_hash_password()"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash. WordPress equivalent: wp_check_password()"""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token Creation ───────────────────────────────────────────────────

def _get_jwt_settings():
    """Lazy import to avoid circular dependency with config module."""
    from app.core.config import get_settings
    return get_settings()


def create_access_token(user_id: int, username: str, roles: list[str]) -> str:
    """
    Create a short-lived JWT access token.

    The token contains:
      - sub: user ID (string — JWT convention)
      - username: for display in error messages
      - roles: WordPress role names for RBAC
      - type: "access" (to distinguish from refresh tokens)
      - exp: expiration timestamp
      - iat: issued-at timestamp

    This token is stored in an httpOnly cookie — JavaScript CANNOT read it.
    The browser sends it automatically with every request.
    """
    settings = _get_jwt_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "type": "access",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived JWT refresh token.

    Contains only the user ID and type marker — no roles or permissions.
    This is intentional: when the token is refreshed, we look up the
    current roles from the database, so role changes take effect
    without requiring re-login.
    """
    settings = _get_jwt_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Raises JWTError if the token is expired, malformed, or has an
    invalid signature. The caller should catch this and return 401.
    """
    settings = _get_jwt_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


# ── Refresh Token Storage ────────────────────────────────────────────────

def hash_refresh_token(token: str) -> str:
    """
    SHA-256 hash a refresh token for database storage.

    We NEVER store raw refresh tokens in the database. If the database
    is compromised, the attacker gets hashes that can't be used to
    authenticate (they'd need the original token, which only exists
    in the user's httpOnly cookie).

    WordPress equivalent: WordPress stores session tokens as SHA-256
    hashes in usermeta — same pattern, different implementation.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ── CSRF Token ───────────────────────────────────────────────────────────

def generate_csrf_token(user_id: int) -> str:
    """
    Generate a CSRF token for the double-submit cookie pattern.

    This is NOT a JWT — it's a random string. The backend sets it as a
    regular cookie (NOT httpOnly), so JavaScript can read it and send
    it as an X-CSRF-Token header. The backend verifies that the cookie
    value matches the header value.

    A CSRF attacker can't read our cookies (same-origin policy), so they
    can't forge the header — the attack is prevented.
    """
    random_part = secrets.token_hex(16)
    return f"{user_id}:{random_part}"
