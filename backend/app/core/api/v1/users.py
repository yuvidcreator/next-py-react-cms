"""
PyPress — Users REST API Router

WordPress equivalent: users.php + user-new.php + user-edit.php

Endpoints:
    GET    /api/v1/users           — List users (filterable, paginated)
    GET    /api/v1/users/:id       — Get single user profile
    POST   /api/v1/users           — Create new user (admin only)
    PATCH  /api/v1/users/:id       — Update user profile/role
    DELETE /api/v1/users/:id       — Delete user (with content reassignment)

RBAC rules (matching WordPress exactly):
    - List users:   requires list_users capability
    - Create user:  requires create_users capability
    - Edit others:  requires edit_users capability
    - Delete user:  requires delete_users capability
    - Edit self:    any authenticated user can edit their own profile
    - Change roles: requires promote_users capability
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth.dependencies import CurrentUser, get_current_user, require_capability, get_capabilities_for_role
from app.core.auth.jwt_handler import hash_password
from app.core.api.schemas.user_schemas import (
    CreateUserRequest, UpdateUserRequest, UserResponse, UserListResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


# =============================================================================
# IN-MEMORY USER STORE (Replace with Phase 1 User model + UserRepository)
# =============================================================================
_NEXT_USER_ID = 4

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_USERS: dict[int, dict] = {
    1: {
        "id": 1, "username": "admin", "email": "admin@pypress.local",
        "password_hash": hash_password("admin"),
        "display_name": "Administrator", "first_name": "Admin", "last_name": "User",
        "role": "administrator", "avatar_url": None, "bio": "Site administrator.",
        "url": "", "is_active": True, "oauth_provider": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-03-14T09:00:00Z",
    },
    2: {
        "id": 2, "username": "editor", "email": "editor@pypress.local",
        "password_hash": hash_password("editor123"),
        "display_name": "Jane Editor", "first_name": "Jane", "last_name": "Editor",
        "role": "editor", "avatar_url": None, "bio": "Content editor.",
        "url": "", "is_active": True, "oauth_provider": None,
        "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-03-10T12:00:00Z",
    },
    3: {
        "id": 3, "username": "contributor", "email": "contrib@pypress.local",
        "password_hash": hash_password("contrib123"),
        "display_name": "Sam Contributor", "first_name": "Sam", "last_name": "Contributor",
        "role": "contributor", "avatar_url": None, "bio": "",
        "url": "", "is_active": True, "oauth_provider": None,
        "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-03-01T00:00:00Z",
    },
}

# Sync with auth router's demo users
from app.core.api.v1.auth import _DEMO_USERS
for uid, udata in _USERS.items():
    _DEMO_USERS[udata["username"]] = udata


def _get_post_count(user_id: int) -> int:
    """Count posts by this author. Replace with DB query."""
    from app.core.api.v1.posts import _POSTS
    return sum(1 for p in _POSTS.values() if p.get("author_id") == user_id)


def _to_user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"], username=user["username"], email=user["email"],
        display_name=user["display_name"], first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""), role=user["role"],
        avatar_url=user.get("avatar_url"), bio=user.get("bio", ""),
        url=user.get("url", ""), is_active=user.get("is_active", True),
        oauth_provider=user.get("oauth_provider"),
        post_count=_get_post_count(user["id"]),
        capabilities=get_capabilities_for_role(user["role"]),
        created_at=user["created_at"], updated_at=user["updated_at"],
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=UserListResponse)
async def list_users(
    user: CurrentUser = Depends(require_capability("list_users")),
    role: str | None = Query(None, description="Filter by role"),
    search: str | None = Query(None, description="Search in username, email, display name"),
    orderby: str = Query("username", description="username | email | role | registered"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    List users with filtering, search, and pagination.
    WordPress equivalent: users.php — the admin Users list table.
    """
    users = list(_USERS.values())

    if role:
        users = [u for u in users if u["role"] == role]

    if search:
        term = search.lower()
        users = [u for u in users if (
            term in u["username"].lower() or
            term in u["email"].lower() or
            term in u.get("display_name", "").lower()
        )]

    # Sort
    sort_map = {"username": "username", "email": "email", "role": "role", "registered": "created_at"}
    sort_key = sort_map.get(orderby, "username")
    users.sort(key=lambda u: u.get(sort_key, ""), reverse=(order.lower() == "desc"))

    # Paginate
    total = len(users)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    users = users[start : start + per_page]

    return UserListResponse(
        items=[_to_user_response(u) for u in users],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single user profile. WordPress equivalent: get_userdata()."""
    user = _USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _to_user_response(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    current_user: CurrentUser = Depends(require_capability("create_users")),
):
    """
    Create a new user account. WordPress equivalent: wp_insert_user().
    Only administrators can create users.
    """
    global _NEXT_USER_ID

    # Check uniqueness
    for u in _USERS.values():
        if u["username"] == body.username:
            raise HTTPException(status_code=409, detail="Username already exists.")
        if u["email"] == body.email:
            raise HTTPException(status_code=409, detail="Email already exists.")

    # Validate role
    valid_roles = {"administrator", "editor", "author", "contributor", "subscriber"}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    user_id = _NEXT_USER_ID
    _NEXT_USER_ID += 1
    now = _now()

    user = {
        "id": user_id,
        "username": body.username,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "display_name": body.display_name or body.username,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "role": body.role,
        "avatar_url": None,
        "bio": body.bio,
        "url": body.url,
        "is_active": True,
        "oauth_provider": None,
        "created_at": now,
        "updated_at": now,
    }
    _USERS[user_id] = user
    _DEMO_USERS[body.username] = user

    return _to_user_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Update a user's profile or role. WordPress equivalent: wp_update_user().

    RBAC rules:
      - Any user can edit their own profile (email, display_name, bio, password)
      - Only admins with edit_users capability can edit other users
      - Only admins with promote_users capability can change roles
    """
    user = _USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_self = current_user.id == user_id

    # Permission check: editing someone else requires edit_users
    if not is_self and not current_user.can("edit_users"):
        raise HTTPException(status_code=403, detail="You can only edit your own profile.")

    update_data = body.model_dump(exclude_unset=True)

    # Role changes require promote_users capability
    if "role" in update_data and not current_user.can("promote_users"):
        raise HTTPException(status_code=403, detail="You do not have permission to change user roles.")

    # Email uniqueness check
    if "email" in update_data:
        for u in _USERS.values():
            if u["email"] == update_data["email"] and u["id"] != user_id:
                raise HTTPException(status_code=409, detail="Email already in use.")

    # Hash new password if provided
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    # Apply updates
    for key, value in update_data.items():
        if key in user:
            user[key] = value

    user["updated_at"] = _now()

    return _to_user_response(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    reassign: int | None = Query(None, description="Reassign content to this user ID"),
    current_user: CurrentUser = Depends(require_capability("delete_users")),
):
    """
    Delete a user account. WordPress equivalent: wp_delete_user().

    If reassign is provided, all the user's posts are transferred to
    that user (like WordPress's "Attribute all content to" option).
    Otherwise, the user's content is deleted with them.

    Cannot delete yourself or the last administrator.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    user = _USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Prevent deleting the last admin
    admin_count = sum(1 for u in _USERS.values() if u["role"] == "administrator")
    if user["role"] == "administrator" and admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last administrator.")

    # Reassign content if requested
    if reassign:
        if reassign not in _USERS:
            raise HTTPException(status_code=400, detail="Reassign target user not found.")
        from app.core.api.v1.posts import _POSTS
        for post in _POSTS.values():
            if post["author_id"] == user_id:
                post["author_id"] = reassign

    del _USERS[user_id]
    _DEMO_USERS.pop(user["username"], None)

    return {"message": f"User '{user['username']}' deleted.", "id": user_id}
