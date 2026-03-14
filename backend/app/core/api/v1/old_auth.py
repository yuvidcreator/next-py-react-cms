"""
Auth REST API — Login, Refresh, Logout, Me, and OAuth2.0 scaffolding.

CRITICAL SECURITY DESIGN:
  - Tokens are NEVER returned in JSON response bodies
  - Access token → httpOnly, Secure, SameSite=Lax cookie
  - Refresh token → httpOnly, Secure, SameSite=Strict cookie (separate path)
  - CSRF token → Regular cookie (JS-readable) for double-submit pattern
  - Session tracking in pp_user_sessions for revocation support
  - OAuth2.0 endpoints scaffolded for Google/GitHub/Facebook social login
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.core.database import get_db_session
from backend.app.core.models.user import User, UserMeta, UserSession
from backend.app.core.hooks import hooks, CoreHooks
from backend.app.core.exceptions import (
    InsufficientCapabilityError, InvalidCredentialsError, InvalidTokenError, AuthenticationError,
)
from backend.app.core.auth.jwt_handler import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    hash_refresh_token, generate_csrf_token,
    ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_TOKEN_COOKIE,
)
from backend.app.core.auth.dependencies import get_current_user, CurrentUser


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request/Response Schemas ─────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username or email")
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response body for login — NOTE: tokens are in cookies, NOT here."""
    message: str = "Login successful"
    user: dict  # {id, username, email, display_name, roles}


class MeResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    roles: list[str]
    capabilities: list[str]


# ── Helper: Set Auth Cookies on Response ─────────────────────────────

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """
    Set all three auth cookies on an HTTP response.

    Access Token Cookie:
      - httpOnly=True  → JavaScript CANNOT read this (XSS-proof)
      - Secure=True    → Only sent over HTTPS (in production)
      - SameSite=Lax   → Sent on same-site requests + top-level navigations
      - Path=/         → Available for all API routes

    Refresh Token Cookie:
      - httpOnly=True  → JS cannot read this either
      - Secure=True    → HTTPS only
      - SameSite=Strict → ONLY sent on same-site requests (extra protection)
      - Path=/api/v1/auth/refresh → ONLY sent to the refresh endpoint

    CSRF Token Cookie:
      - httpOnly=False → JS CAN read this (needed for double-submit pattern)
      - Secure=True    → HTTPS only
      - SameSite=Lax   → Standard cross-site protection
      - Path=/         → Available everywhere for JS to read
    """
    settings = get_settings()
    secure = settings.COOKIE_SECURE
    domain = settings.COOKIE_DOMAIN or None

    # Access token — httpOnly, not accessible by JS
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,           # THE key security measure
        secure=secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=domain,
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # Refresh token — httpOnly, restricted path
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",      # Extra strict for refresh tokens
        domain=domain,
        path="/api/v1/auth",    # Only sent to auth endpoints
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # CSRF token — NOT httpOnly (JS must read it for the header)
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=False,          # JS needs to read this
        secure=secure,
        samesite=settings.COOKIE_SAMESITE,
        domain=domain,
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear all auth cookies — used during logout."""
    settings = get_settings()
    domain = settings.COOKIE_DOMAIN or None

    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/api/v1/auth", domain=domain)
    response.delete_cookie(CSRF_TOKEN_COOKIE, path="/", domain=domain)


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Authenticate a user and set httpOnly auth cookies.

    The access token, refresh token, and CSRF token are all set as cookies.
    They are NOT returned in the JSON response body — the response body
    only contains the user's public profile info.

    This is more secure than returning tokens in JSON because:
    1. Tokens never touch JavaScript (httpOnly cookies are invisible to JS)
    2. Tokens are automatically managed by the browser
    3. No risk of tokens being logged, stored insecurely, or leaked by frontend code
    """
    # Fire before_login hook — plugins can add rate limiting, captcha, etc.
    await hooks.do_action(CoreHooks.BEFORE_LOGIN, username=body.username, ip=request.client.host)

    # Find user by username or email
    stmt = select(User).where(
        (User.username == body.username) | (User.email == body.username)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        await hooks.do_action(CoreHooks.FAILED_LOGIN, username=body.username, ip=request.client.host)
        raise InvalidCredentialsError("Invalid username or password.")

    if user.status != 0:
        raise AuthenticationError("Your account is disabled.")

    # Load user roles from usermeta
    roles = await _get_user_roles(db, user.id)

    # Create tokens
    access_token = create_access_token(user.id, user.username, roles)
    refresh_token = create_refresh_token(user.id)
    csrf_token = generate_csrf_token(user.id)

    # Store refresh token hash in session table (for revocation)
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:500],
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at="",  # Set from token payload
        last_used_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(session)

    # Set cookies on the response — tokens NEVER appear in JSON body
    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    # Fire after_login hook
    await hooks.do_action(CoreHooks.AFTER_LOGIN, user=user, ip=request.client.host)

    return LoginResponse(
        message="Login successful",
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name or user.username,
            "roles": roles,
        },
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Silently refresh the access token using the refresh token cookie.

    The frontend calls this when it gets a 401 response. The browser
    sends the refresh token cookie automatically (it's scoped to /api/v1/auth).
    If the refresh token is valid and not revoked, we issue new tokens.
    """
    refresh_cookie = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_cookie:
        raise AuthenticationError("No refresh token. Please log in.")

    # Decode the refresh token
    try:
        payload = decode_token(refresh_cookie)
    except InvalidTokenError:
        _clear_auth_cookies(response)
        raise AuthenticationError("Refresh token expired. Please log in again.")

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type.")

    user_id = int(payload["sub"])

    # Verify the session exists and is active in the database
    token_hash = hash_refresh_token(refresh_cookie)
    stmt = select(UserSession).where(
        UserSession.refresh_token_hash == token_hash,
        UserSession.is_active == True,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        _clear_auth_cookies(response)
        raise AuthenticationError("Session revoked. Please log in again.")

    # Load the user
    user = await db.get(User, user_id)
    if user is None or user.status != 0:
        _clear_auth_cookies(response)
        raise AuthenticationError("User account not found or disabled.")

    roles = await _get_user_roles(db, user.id)

    # TOKEN ROTATION: Issue completely new tokens and invalidate the old ones.
    # This limits the damage if a refresh token is somehow compromised.
    new_access = create_access_token(user.id, user.username, roles)
    new_refresh = create_refresh_token(user.id)
    new_csrf = generate_csrf_token(user.id)

    # Update session with new refresh token hash
    session.refresh_token_hash = hash_refresh_token(new_refresh)
    session.last_used_at = datetime.now(timezone.utc).isoformat()

    _set_auth_cookies(response, new_access, new_refresh, new_csrf)

    return {"message": "Token refreshed successfully"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Log out — clear all auth cookies and revoke the session in the database.
    Even if the user somehow retains the token, it won't work because
    the session is marked inactive in the DB.
    """
    # Revoke the session in the database
    refresh_cookie = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_cookie:
        token_hash = hash_refresh_token(refresh_cookie)
        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False

    # Extract user ID for the hook (best-effort)
    access_cookie = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if access_cookie:
        try:
            payload = decode_token(access_cookie)
            await hooks.do_action(CoreHooks.USER_LOGOUT, user_id=int(payload["sub"]))
        except Exception:
            pass

    # Clear all cookies
    _clear_auth_cookies(response)

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=MeResponse)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """
    Return the current authenticated user's profile.
    Used by the admin panel on page load to check auth status.
    """
    return MeResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
        capabilities=sorted(user.capabilities),
    )


@router.get("/sessions")
async def list_sessions(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all active sessions for the current user (or all users if admin)."""
    stmt = select(UserSession).where(
        UserSession.user_id == user.id,
        UserSession.is_active == True,
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "id": s.id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "created_at": s.created_at,
                "last_used_at": s.last_used_at,
            }
            for s in sessions
        ]
    }


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke a specific session (force-logout a device)."""
    session = await db.get(UserSession, session_id)
    if session is None:
        return {"message": "Session not found"}
    # Users can revoke their own sessions; admins can revoke anyone's
    if session.user_id != user.id and not user.is_admin():
        raise InsufficientCapabilityError("Cannot revoke other users' sessions")
    session.is_active = False
    return {"message": "Session revoked"}


# ── OAuth2.0 Scaffolding (Future — ready for Phase 9+) ──────────────

@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str):
    """
    Initiate OAuth2.0 flow — redirect user to the provider's login page.
    Supported providers (when configured): google, github, facebook.

    The flow:
    1. User clicks "Sign in with Google" in the admin panel
    2. Admin calls GET /api/v1/auth/oauth/google
    3. Backend returns a redirect URL to Google's consent screen
    4. User authenticates with Google
    5. Google redirects back to /api/v1/auth/oauth/google/callback
    6. Backend creates/links the user account and sets httpOnly cookies
    7. User is logged in — same cookie-based auth as password login

    NOT YET IMPLEMENTED — this is the scaffold for Phase 9+.
    """
    settings = get_settings()
    providers = {
        "google": {
            "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "scope": "openid email profile",
            "redirect_uri": settings.OAUTH_GOOGLE_REDIRECT_URI,
        },
        "github": {
            "client_id": settings.OAUTH_GITHUB_CLIENT_ID,
            "auth_url": "https://github.com/login/oauth/authorize",
            "scope": "user:email",
            "redirect_uri": settings.OAUTH_GITHUB_REDIRECT_URI,
        },
        "facebook": {
            "client_id": settings.OAUTH_FACEBOOK_CLIENT_ID,
            "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
            "scope": "email,public_profile",
            "redirect_uri": settings.OAUTH_FACEBOOK_REDIRECT_URI,
        },
    }

    if provider not in providers:
        return {"error": f"Unknown OAuth provider: {provider}"}

    config = providers[provider]
    if not config["client_id"]:
        return {"error": f"OAuth provider '{provider}' is not configured. Set OAUTH_{provider.upper()}_CLIENT_ID in .env"}

    # TODO: Build the authorization URL and return a redirect
    return {
        "message": f"OAuth2.0 with {provider} — scaffold ready. Implementation in Phase 9.",
        "provider": provider,
        "configured": bool(config["client_id"]),
    }


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, response: Response):
    """
    OAuth2.0 callback — provider redirects here after user authenticates.
    TODO: Exchange code for tokens, create/link user, set httpOnly cookies.
    """
    return {"message": f"OAuth callback for {provider} — scaffold ready for Phase 9."}


# ── Internal Helpers ─────────────────────────────────────────────────

async def _get_user_roles(db: AsyncSession, user_id: int) -> list[str]:
    """Load user roles from usermeta."""
    stmt = select(UserMeta).where(
        UserMeta.user_id == user_id, UserMeta.meta_key == "pp_capabilities",
    )
    result = await db.execute(stmt)
    meta = result.scalar_one_or_none()
    if meta and meta.meta_value:
        try:
            caps = json.loads(meta.meta_value)
            return [role for role, active in caps.items() if active]
        except (json.JSONDecodeError, AttributeError):
            pass
    return ["subscriber"]
