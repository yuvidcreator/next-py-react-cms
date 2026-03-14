# """
# Auth Dependencies — FastAPI dependency injection for authentication and authorization.

# These dependencies are used by API routes to:
#   1. Extract the current user from httpOnly cookies (get_current_user)
#   2. Require a specific capability (require_capability)
#   3. Validate CSRF tokens on mutation requests (validate_csrf)

# Every authenticated API route uses these as Depends() parameters.

# SECURITY MODEL:
#   - Access token lives in httpOnly cookie → immune to XSS
#   - CSRF token lives in regular cookie → JS reads it and sends as header
#   - Mutations (POST/PUT/DELETE) require BOTH valid access token AND valid CSRF
#   - Read operations (GET) only require valid access token
#   - The combination of httpOnly + CSRF double-submit provides defense-in-depth
# """
# from __future__ import annotations

# import json
# import logging
# from dataclasses import dataclass
# from typing import Any

# from fastapi import Request, Depends, HTTPException
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from backend.app.core.config import get_settings
# from backend.app.core.database import get_db_session
# from backend.app.core.models.user import User, UserMeta
# from backend.app.core.auth.jwt_handler import (
#     decode_token, validate_csrf_token,
#     ACCESS_TOKEN_COOKIE, CSRF_TOKEN_COOKIE,
# )
# from backend.app.core.auth.rbac import capability_checker
# from backend.app.core.exceptions import (
#     AuthenticationError, InvalidTokenError,
#     InsufficientCapabilityError, CSRFValidationError,
# )

# logger = logging.getLogger(__name__)


# @dataclass
# class CurrentUser:
#     """
#     Represents the authenticated user for the current request.
#     This is what routes receive when they use Depends(get_current_user).
#     """
#     id: int
#     username: str
#     email: str
#     display_name: str
#     roles: list[str]
#     capabilities: set[str]

#     def can(self, capability: str) -> bool:
#         """Check if this user has a specific capability."""
#         return capability_checker.user_can(self.roles, capability)

#     def is_admin(self) -> bool:
#         return "administrator" in self.roles


# async def get_current_user(
#     request: Request,
#     db: AsyncSession = Depends(get_db_session),
# ) -> CurrentUser:
#     """
#     FastAPI dependency that extracts and validates the current user
#     from the httpOnly access token cookie.

#     Usage in a route:
#         @router.get("/posts")
#         async def list_posts(user: CurrentUser = Depends(get_current_user)):
#             if not user.can("edit_posts"):
#                 raise InsufficientCapabilityError("Cannot edit posts")

#     The access token is in an httpOnly cookie, so the browser sends it
#     automatically. No Authorization header needed. No JS involved.
#     """
#     # 1. Extract access token from httpOnly cookie
#     token = request.cookies.get(ACCESS_TOKEN_COOKIE)
#     if not token:
#         raise AuthenticationError("Authentication required. Please log in.")

#     # 2. Decode and validate the JWT
#     try:
#         payload = decode_token(token)
#     except InvalidTokenError:
#         raise AuthenticationError("Your session has expired. Please log in again.")

#     # 3. Verify it's an access token (not a refresh token)
#     if payload.get("type") != "access":
#         raise AuthenticationError("Invalid token type.")

#     # 4. Extract user info from the token
#     user_id = int(payload["sub"])
#     username = payload.get("username", "")
#     roles = payload.get("roles", [])

#     # 5. Verify the user still exists and is active in the database
#     #    (in case they were deleted or deactivated after the token was issued)
#     stmt = select(User).where(User.id == user_id)
#     result = await db.execute(stmt)
#     user = result.scalar_one_or_none()

#     if user is None:
#         raise AuthenticationError("User account not found.")
#     if user.status != 0:  # 0 = active in WordPress
#         raise AuthenticationError("User account is disabled.")

#     # 6. If roles weren't in the token (shouldn't happen, but defensive),
#     #    load them from usermeta
#     if not roles:
#         roles = await _load_user_roles(db, user_id)

#     # 7. Resolve all capabilities from the user's roles
#     all_caps: set[str] = set()
#     for role in roles:
#         all_caps.update(capability_checker.get_role_capabilities(role))

#     return CurrentUser(
#         id=user.id,
#         username=user.username,
#         email=user.email,
#         display_name=user.display_name or user.username,
#         roles=roles,
#         capabilities=all_caps,
#     )


# async def get_current_user_optional(
#     request: Request,
#     db: AsyncSession = Depends(get_db_session),
# ) -> CurrentUser | None:
#     """
#     Like get_current_user but returns None instead of raising an error
#     when no user is authenticated. Used for routes that work for both
#     authenticated and anonymous users (like viewing a public post).
#     """
#     token = request.cookies.get(ACCESS_TOKEN_COOKIE)
#     if not token:
#         return None
#     try:
#         return await get_current_user(request, db)
#     except (AuthenticationError, InvalidTokenError):
#         return None


# async def validate_csrf(request: Request) -> None:
#     """
#     FastAPI dependency that validates the CSRF token on mutation requests.

#     The CSRF token is stored in a REGULAR cookie (JS-readable) and must
#     also be sent in the X-CSRF-Token header. This is the "double-submit
#     cookie" pattern: an attacker from another domain can submit a form
#     to our backend (the browser sends our cookies), but they can't READ
#     our cookies to extract the CSRF token and set the header.

#     Usage:
#         @router.post("/posts")
#         async def create_post(
#             _csrf: None = Depends(validate_csrf),
#             user: CurrentUser = Depends(get_current_user),
#         ):
#             ...

#     Only applied to mutation methods (POST, PUT, PATCH, DELETE).
#     GET and HEAD requests do not need CSRF validation.
#     """
#     # Skip CSRF check for safe methods
#     if request.method in ("GET", "HEAD", "OPTIONS"):
#         return

#     # 1. Get the CSRF token from the cookie
#     cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE)
#     if not cookie_csrf:
#         raise CSRFValidationError("CSRF cookie missing. Please refresh the page.")

#     # 2. Get the CSRF token from the request header
#     header_csrf = request.headers.get("X-CSRF-Token", "")
#     if not header_csrf:
#         raise CSRFValidationError("CSRF header missing. Include X-CSRF-Token header.")

#     # 3. Verify both tokens match (the double-submit check)
#     if cookie_csrf != header_csrf:
#         raise CSRFValidationError("CSRF token mismatch.")

#     # 4. Validate the token hasn't expired or been tampered with
#     try:
#         validate_csrf_token(header_csrf)
#     except InvalidTokenError:
#         raise CSRFValidationError("CSRF token expired. Please refresh the page.")


# def require_capability(capability: str):
#     """
#     Factory function that creates a FastAPI dependency for capability checks.

#     Usage:
#         @router.delete("/posts/{id}")
#         async def delete_post(
#             user: CurrentUser = Depends(get_current_user),
#             _cap: None = Depends(require_capability("delete_posts")),
#         ):
#             ...

#     WordPress equivalent: current_user_can('delete_posts')
#     """
#     async def _check(user: CurrentUser = Depends(get_current_user)) -> None:
#         if not user.can(capability):
#             raise InsufficientCapabilityError(
#                 f"You do not have the '{capability}' capability required for this action."
#             )
#     return _check


# # ── Internal Helpers ─────────────────────────────────────────────────

# async def _load_user_roles(db: AsyncSession, user_id: int) -> list[str]:
#     """Load user roles from usermeta (like WordPress reads wp_capabilities)."""
#     stmt = select(UserMeta).where(
#         UserMeta.user_id == user_id,
#         UserMeta.meta_key == "pp_capabilities",
#     )
#     result = await db.execute(stmt)
#     meta = result.scalar_one_or_none()

#     if meta and meta.meta_value:
#         try:
#             caps_dict = json.loads(meta.meta_value)
#             return [role for role, active in caps_dict.items() if active]
#         except (json.JSONDecodeError, AttributeError):
#             pass

#     return ["subscriber"]  # Default role if nothing found


"""
PyPress — Auth Dependencies (FastAPI Dependency Injection)

These dependencies are used by API endpoints to enforce authentication
and authorization. They read httpOnly cookies, validate JWT tokens,
and load user data from the database.

Usage in endpoints:
    @router.get("/posts")
    async def list_posts(user: CurrentUser = Depends(get_current_user)):
        # user is guaranteed to be authenticated
        ...

    @router.delete("/posts/{id}")
    async def delete_post(
        user: CurrentUser = Depends(require_capability("delete_posts"))
    ):
        # user is guaranteed to have the delete_posts capability
        ...

WordPress equivalent:
    get_current_user() → wp_get_current_user()
    require_capability("edit_posts") → current_user_can("edit_posts")
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError

from app.core.auth.jwt_handler import (
    ACCESS_TOKEN_COOKIE,
    CSRF_TOKEN_COOKIE,
    decode_token,
)

# ── RBAC: WordPress-Compatible Capability Sets ───────────────────────────
# Each role has a predefined set of capabilities, exactly matching WordPress.
# Plugins can add custom roles and capabilities in Phase 4.
ROLE_CAPABILITIES: dict[str, list[str]] = {
    "administrator": [
        "switch_themes", "edit_themes", "activate_plugins", "edit_plugins",
        "edit_users", "edit_files", "manage_options", "moderate_comments",
        "manage_categories", "manage_links", "upload_files", "import",
        "edit_posts", "edit_others_posts", "edit_published_posts",
        "publish_posts", "edit_pages", "read", "edit_others_pages",
        "edit_published_pages", "publish_pages", "delete_pages",
        "delete_others_pages", "delete_published_pages", "delete_posts",
        "delete_others_posts", "delete_published_posts", "delete_private_posts",
        "edit_private_posts", "read_private_posts", "delete_private_pages",
        "edit_private_pages", "read_private_pages", "unfiltered_html",
        "edit_dashboard", "update_plugins", "delete_plugins", "install_plugins",
        "update_themes", "install_themes", "delete_themes", "list_users",
        "create_users", "delete_users", "promote_users", "remove_users",
        "manage_privacy_options", "export",
    ],
    "editor": [
        "moderate_comments", "manage_categories", "manage_links",
        "upload_files", "edit_posts", "edit_others_posts",
        "edit_published_posts", "publish_posts", "edit_pages",
        "read", "edit_others_pages", "edit_published_pages",
        "publish_pages", "delete_pages", "delete_others_pages",
        "delete_published_pages", "delete_posts", "delete_others_posts",
        "delete_published_posts", "delete_private_posts", "edit_private_posts",
        "read_private_posts", "delete_private_pages", "edit_private_pages",
        "read_private_pages", "unfiltered_html",
    ],
    "author": [
        "upload_files", "edit_posts", "edit_published_posts",
        "publish_posts", "read", "delete_posts", "delete_published_posts",
    ],
    "contributor": [
        "edit_posts", "read", "delete_posts",
    ],
    "subscriber": [
        "read",
    ],
}


def get_capabilities_for_role(role: str) -> list[str]:
    """Get the capability list for a WordPress-compatible role."""
    return ROLE_CAPABILITIES.get(role, ROLE_CAPABILITIES["subscriber"])


# ── Type alias for the current user ─────────────────────────────────────
# This is a dict containing decoded JWT claims + capabilities.
# In Phase 3, this will become a proper User model from the database.
class CurrentUser:
    """Authenticated user extracted from the JWT access token cookie."""

    def __init__(self, payload: dict):
        self.id: int = int(payload["sub"])
        self.username: str = payload.get("username", "")
        roles: list[str] = payload.get("roles", [])
        self.role: str = roles[0] if roles else "subscriber"
        self.roles: list[str] = roles
        self.capabilities: list[str] = get_capabilities_for_role(self.role)

    def can(self, capability: str) -> bool:
        """Check if the user has a specific capability."""
        if self.role == "administrator":
            return True
        return capability in self.capabilities


# ── get_current_user dependency ──────────────────────────────────────────

async def get_current_user(
    pypress_access_token: Annotated[str | None, Cookie()] = None,
) -> CurrentUser:
    """
    Extract and validate the current user from the httpOnly access token cookie.

    The browser sends this cookie automatically with every request.
    If the cookie is missing or the token is invalid/expired, we raise 401.
    The Axios interceptor on the frontend catches 401 and attempts a
    silent token refresh before redirecting to login.

    WordPress equivalent: wp_get_current_user() which reads the auth
    cookie and loads the user from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not pypress_access_token:
        raise credentials_exception

    try:
        payload = decode_token(pypress_access_token)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    return CurrentUser(payload)


# ── require_capability dependency factory ────────────────────────────────

def require_capability(capability: str):
    """
    Factory that creates a FastAPI dependency requiring a specific capability.

    Usage:
        @router.delete("/posts/{id}")
        async def delete_post(
            user: CurrentUser = Depends(require_capability("delete_posts"))
        ):
            ...

    WordPress equivalent: current_user_can("delete_posts")
    """
    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.can(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to perform this action. Required: {capability}",
            )
        return user

    return _check
