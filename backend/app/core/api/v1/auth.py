"""
PyPress — Auth REST API Router

Endpoints:
    POST /api/v1/auth/login    — Authenticate and set httpOnly cookies
    POST /api/v1/auth/refresh  — Silently rotate tokens (called by Axios interceptor)
    POST /api/v1/auth/logout   — Clear cookies and revoke session
    GET  /api/v1/auth/me       — Return current user profile + capabilities

SECURITY MODEL:
    - Tokens are NEVER returned in JSON response bodies
    - Access token → httpOnly, Secure, SameSite=Lax cookie
    - Refresh token → httpOnly, Secure, SameSite=Strict cookie (scoped to /auth)
    - CSRF token → Regular cookie (JS-readable for double-submit pattern)
    - Sessions tracked in DB for revocation support
    - Token rotation on refresh (old refresh token hash is replaced)

WordPress equivalent: wp-login.php + pluggable.php auth functions
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.auth.jwt_handler import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    CSRF_TOKEN_COOKIE,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    generate_csrf_token,
)
from app.core.auth.dependencies import (
    CurrentUser,
    get_current_user,
    get_capabilities_for_role,
)
from app.core.api.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    LogoutResponse,
    MeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# HELPERS: Cookie Management
# =============================================================================

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """
    Set all three auth cookies on an HTTP response.

    Cookie architecture:
      Access token:  httpOnly=True, SameSite=Lax, Path=/
      Refresh token: httpOnly=True, SameSite=Strict, Path=/api/v1/auth
      CSRF token:    httpOnly=False (JS reads it), SameSite=Lax, Path=/
    """
    settings = get_settings()
    secure = settings.COOKIE_SECURE
    domain = settings.COOKIE_DOMAIN or None

    # Access token — httpOnly (XSS-proof), sent with every request
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=domain,
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # Refresh token — httpOnly, restricted path (only sent to /auth endpoints)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        domain=domain,
        path="/api/v1/auth",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # CSRF token — NOT httpOnly (JS must read it for the X-CSRF-Token header)
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=domain,
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear all auth cookies — used during logout and failed refresh."""
    settings = get_settings()
    domain = settings.COOKIE_DOMAIN or None

    for cookie_name, path in [
        (ACCESS_TOKEN_COOKIE, "/"),
        (REFRESH_TOKEN_COOKIE, "/api/v1/auth"),
        (CSRF_TOKEN_COOKIE, "/"),
    ]:
        response.delete_cookie(
            key=cookie_name,
            domain=domain,
            path=path,
        )


# =============================================================================
# TEMPORARY: In-memory user store (until Phase 1 models are merged)
# =============================================================================
# This provides a working auth system before the full SQLAlchemy models
# and database are integrated. Replace with real DB queries when merging
# Phase 1 code (User model, UserSession model, etc.)
#
# The default admin account allows immediate testing after deployment.
# WordPress equivalent: the admin user created during wp-admin/install.php

from app.core.auth.jwt_handler import hash_password as _hash_pw

_DEMO_USERS: dict[str, dict] = {
    "admin": {
        "id": 1,
        "username": "admin",
        "email": "admin@pypress.local",
        "password_hash": _hash_pw("admin"),  # CHANGE IN PRODUCTION
        "display_name": "Administrator",
        "first_name": "Admin",
        "last_name": "User",
        "role": "administrator",
        "avatar_url": None,
        "bio": "",
        "url": "",
        "is_active": True,
        "oauth_provider": None,
        "status": 0,  # 0 = active (WordPress convention)
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
}

# In-memory session store (replace with pp_user_sessions table)
_SESSIONS: dict[str, dict] = {}


async def _find_user(username: str) -> dict | None:
    """Find a user by username or email. Replace with DB query."""
    # Check by username
    if username in _DEMO_USERS:
        return _DEMO_USERS[username]
    # Check by email
    for user_data in _DEMO_USERS.values():
        if user_data["email"] == username:
            return user_data
    return None


async def _get_user_by_id(user_id: int) -> dict | None:
    """Find a user by ID. Replace with DB query."""
    for user_data in _DEMO_USERS.values():
        if user_data["id"] == user_id:
            return user_data
    return None


async def _store_session(user_id: int, token_hash: str, request: Request) -> None:
    """Store a session record. Replace with DB insert into pp_user_sessions."""
    _SESSIONS[token_hash] = {
        "user_id": user_id,
        "refresh_token_hash": token_hash,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")[:500],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
    }


async def _verify_session(token_hash: str) -> dict | None:
    """Check if a session is valid. Replace with DB query."""
    session = _SESSIONS.get(token_hash)
    if session and session["is_active"]:
        return session
    return None


async def _revoke_session(token_hash: str) -> None:
    """Revoke a session. Replace with DB update."""
    if token_hash in _SESSIONS:
        _SESSIONS[token_hash]["is_active"] = False


async def _update_session(old_hash: str, new_hash: str) -> None:
    """Rotate session token hash. Replace with DB update."""
    if old_hash in _SESSIONS:
        session = _SESSIONS.pop(old_hash)
        session["refresh_token_hash"] = new_hash
        session["last_used_at"] = datetime.now(timezone.utc).isoformat()
        _SESSIONS[new_hash] = session


async def _count_active_sessions(user_id: int) -> int:
    """Count active sessions for a user. Replace with DB count."""
    return sum(
        1 for s in _SESSIONS.values()
        if s["user_id"] == user_id and s["is_active"]
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
):
    """
    Authenticate with username/email + password.

    On success:
      1. Creates a session record (for revocation support)
      2. Sets three cookies: access token, refresh token, CSRF token
      3. Returns user data in the response body (for immediate UI update)

    On failure:
      - Returns 401 with a generic error message
      - Does NOT reveal whether the username exists (prevents enumeration)

    WordPress equivalent: wp_signon() → wp_set_auth_cookie()
    """
    # Find user by username or email
    user = await _find_user(body.username)

    # Verify credentials — generic error message to prevent user enumeration
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # Check account status
    if user.get("status", 0) != 0 or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been disabled. Contact an administrator.",
        )

    roles = [user["role"]]

    # Create tokens
    access_token = create_access_token(user["id"], user["username"], roles)
    refresh_token = create_refresh_token(user["id"])
    csrf_token = generate_csrf_token(user["id"])

    # Store session for revocation support
    token_hash = hash_refresh_token(refresh_token)
    await _store_session(user["id"], token_hash, request)

    # Set httpOnly cookies — tokens NEVER appear in the JSON body
    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    logger.info(f"User '{user['username']}' logged in from {request.client.host if request.client else 'unknown'}")

    return LoginResponse(
        message="Login successful",
        user={
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "display_name": user["display_name"],
            "roles": roles,
        },
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
):
    """
    Silently refresh the access token using the refresh token cookie.

    Called automatically by the frontend's Axios interceptor on 401.
    Implements TOKEN ROTATION: new tokens are issued, old refresh token
    hash is replaced in the session store. This limits damage if a
    refresh token is compromised.

    WordPress equivalent: No direct equivalent — WordPress sessions don't
    have short-lived access tokens.
    """
    refresh_cookie = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token. Please log in.",
        )

    # Decode the refresh token
    try:
        payload = decode_token(refresh_cookie)
    except Exception:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please log in again.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user_id = int(payload["sub"])

    # Verify the session exists and is active
    old_hash = hash_refresh_token(refresh_cookie)
    session = await _verify_session(old_hash)
    if session is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked. Please log in again.",
        )

    # Load user
    user = await _get_user_by_id(user_id)
    if user is None or user.get("status", 0) != 0:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or disabled.",
        )

    roles = [user["role"]]

    # TOKEN ROTATION: Issue completely new tokens
    new_access = create_access_token(user["id"], user["username"], roles)
    new_refresh = create_refresh_token(user["id"])
    new_csrf = generate_csrf_token(user["id"])

    # Update session with new refresh token hash
    new_hash = hash_refresh_token(new_refresh)
    await _update_session(old_hash, new_hash)

    _set_auth_cookies(response, new_access, new_refresh, new_csrf)

    return RefreshResponse(message="Token refreshed successfully")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
):
    """
    Log out — clear all auth cookies and revoke the session.

    Even if an attacker somehow obtained the old tokens, they won't work
    because the session is marked inactive in the database.

    WordPress equivalent: wp_logout() → wp_clear_auth_cookie() +
    wp_destroy_current_session()
    """
    # Revoke the session
    refresh_cookie = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_cookie:
        token_hash = hash_refresh_token(refresh_cookie)
        await _revoke_session(token_hash)

    # Clear all cookies
    _clear_auth_cookies(response)

    return LogoutResponse(message="Logged out successfully")


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Return the current authenticated user's profile and capabilities.

    Called by the frontend on mount (App.tsx → fetchCurrentUser()) to
    check if the user's httpOnly cookies are still valid.

    The capabilities array is used by the frontend to:
      - Show/hide sidebar menu items based on permissions
      - Disable buttons the user can't use
      - Display role-appropriate content

    WordPress equivalent: wp_get_current_user() + current_user_can()
    """
    # Load full user data
    user_data = await _get_user_by_id(user.id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    active_sessions = await _count_active_sessions(user.id)

    return MeResponse(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        display_name=user_data["display_name"],
        first_name=user_data.get("first_name", ""),
        last_name=user_data.get("last_name", ""),
        role=user_data["role"],
        avatar_url=user_data.get("avatar_url"),
        bio=user_data.get("bio", ""),
        url=user_data.get("url", ""),
        is_active=user_data.get("is_active", True),
        oauth_provider=user_data.get("oauth_provider"),
        capabilities=get_capabilities_for_role(user_data["role"]),
        active_sessions=active_sessions,
        created_at=user_data.get("created_at", ""),
        updated_at=user_data.get("updated_at", ""),
    )
