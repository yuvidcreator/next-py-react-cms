"""
Auth Dependencies — FastAPI dependency injection for authentication and authorization.

These dependencies are used by API routes to:
  1. Extract the current user from httpOnly cookies (get_current_user)
  2. Require a specific capability (require_capability)
  3. Validate CSRF tokens on mutation requests (validate_csrf)

Every authenticated API route uses these as Depends() parameters.

SECURITY MODEL:
  - Access token lives in httpOnly cookie → immune to XSS
  - CSRF token lives in regular cookie → JS reads it and sends as header
  - Mutations (POST/PUT/DELETE) require BOTH valid access token AND valid CSRF
  - Read operations (GET) only require valid access token
  - The combination of httpOnly + CSRF double-submit provides defense-in-depth
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.database import get_db_session
from backend.core.models.user import User, UserMeta
from backend.core.auth.jwt_handler import (
    decode_token, validate_csrf_token,
    ACCESS_TOKEN_COOKIE, CSRF_TOKEN_COOKIE,
)
from backend.core.auth.rbac import capability_checker
from backend.core.exceptions import (
    AuthenticationError, InvalidTokenError,
    InsufficientCapabilityError, CSRFValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    """
    Represents the authenticated user for the current request.
    This is what routes receive when they use Depends(get_current_user).
    """
    id: int
    username: str
    email: str
    display_name: str
    roles: list[str]
    capabilities: set[str]

    def can(self, capability: str) -> bool:
        """Check if this user has a specific capability."""
        return capability_checker.user_can(self.roles, capability)

    def is_admin(self) -> bool:
        return "administrator" in self.roles


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """
    FastAPI dependency that extracts and validates the current user
    from the httpOnly access token cookie.

    Usage in a route:
        @router.get("/posts")
        async def list_posts(user: CurrentUser = Depends(get_current_user)):
            if not user.can("edit_posts"):
                raise InsufficientCapabilityError("Cannot edit posts")

    The access token is in an httpOnly cookie, so the browser sends it
    automatically. No Authorization header needed. No JS involved.
    """
    # 1. Extract access token from httpOnly cookie
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise AuthenticationError("Authentication required. Please log in.")

    # 2. Decode and validate the JWT
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        raise AuthenticationError("Your session has expired. Please log in again.")

    # 3. Verify it's an access token (not a refresh token)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type.")

    # 4. Extract user info from the token
    user_id = int(payload["sub"])
    username = payload.get("username", "")
    roles = payload.get("roles", [])

    # 5. Verify the user still exists and is active in the database
    #    (in case they were deleted or deactivated after the token was issued)
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User account not found.")
    if user.status != 0:  # 0 = active in WordPress
        raise AuthenticationError("User account is disabled.")

    # 6. If roles weren't in the token (shouldn't happen, but defensive),
    #    load them from usermeta
    if not roles:
        roles = await _load_user_roles(db, user_id)

    # 7. Resolve all capabilities from the user's roles
    all_caps: set[str] = set()
    for role in roles:
        all_caps.update(capability_checker.get_role_capabilities(role))

    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name or user.username,
        roles=roles,
        capabilities=all_caps,
    )


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser | None:
    """
    Like get_current_user but returns None instead of raising an error
    when no user is authenticated. Used for routes that work for both
    authenticated and anonymous users (like viewing a public post).
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        return None
    try:
        return await get_current_user(request, db)
    except (AuthenticationError, InvalidTokenError):
        return None


async def validate_csrf(request: Request) -> None:
    """
    FastAPI dependency that validates the CSRF token on mutation requests.

    The CSRF token is stored in a REGULAR cookie (JS-readable) and must
    also be sent in the X-CSRF-Token header. This is the "double-submit
    cookie" pattern: an attacker from another domain can submit a form
    to our backend (the browser sends our cookies), but they can't READ
    our cookies to extract the CSRF token and set the header.

    Usage:
        @router.post("/posts")
        async def create_post(
            _csrf: None = Depends(validate_csrf),
            user: CurrentUser = Depends(get_current_user),
        ):
            ...

    Only applied to mutation methods (POST, PUT, PATCH, DELETE).
    GET and HEAD requests do not need CSRF validation.
    """
    # Skip CSRF check for safe methods
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # 1. Get the CSRF token from the cookie
    cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE)
    if not cookie_csrf:
        raise CSRFValidationError("CSRF cookie missing. Please refresh the page.")

    # 2. Get the CSRF token from the request header
    header_csrf = request.headers.get("X-CSRF-Token", "")
    if not header_csrf:
        raise CSRFValidationError("CSRF header missing. Include X-CSRF-Token header.")

    # 3. Verify both tokens match (the double-submit check)
    if cookie_csrf != header_csrf:
        raise CSRFValidationError("CSRF token mismatch.")

    # 4. Validate the token hasn't expired or been tampered with
    try:
        validate_csrf_token(header_csrf)
    except InvalidTokenError:
        raise CSRFValidationError("CSRF token expired. Please refresh the page.")


def require_capability(capability: str):
    """
    Factory function that creates a FastAPI dependency for capability checks.

    Usage:
        @router.delete("/posts/{id}")
        async def delete_post(
            user: CurrentUser = Depends(get_current_user),
            _cap: None = Depends(require_capability("delete_posts")),
        ):
            ...

    WordPress equivalent: current_user_can('delete_posts')
    """
    async def _check(user: CurrentUser = Depends(get_current_user)) -> None:
        if not user.can(capability):
            raise InsufficientCapabilityError(
                f"You do not have the '{capability}' capability required for this action."
            )
    return _check


# ── Internal Helpers ─────────────────────────────────────────────────

async def _load_user_roles(db: AsyncSession, user_id: int) -> list[str]:
    """Load user roles from usermeta (like WordPress reads wp_capabilities)."""
    stmt = select(UserMeta).where(
        UserMeta.user_id == user_id,
        UserMeta.meta_key == "pp_capabilities",
    )
    result = await db.execute(stmt)
    meta = result.scalar_one_or_none()

    if meta and meta.meta_value:
        try:
            caps_dict = json.loads(meta.meta_value)
            return [role for role, active in caps_dict.items() if active]
        except (json.JSONDecodeError, AttributeError):
            pass

    return ["subscriber"]  # Default role if nothing found
