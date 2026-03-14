"""
PyPress — User API Schemas

Pydantic models for Users REST API. WordPress equivalent: WP_User class.

    CreateUserRequest  → POST /api/v1/users (admin creates user)
    UpdateUserRequest  → PATCH /api/v1/users/:id (edit profile/role)
    UserResponse       → Full user profile with capabilities
    UserListResponse   → Paginated list for the Users admin page
"""
from __future__ import annotations

from pydantic import BaseModel, Field, EmailStr


class CreateUserRequest(BaseModel):
    """POST /api/v1/users — create a new user account."""
    username: str = Field(..., min_length=3, max_length=60)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    role: str = Field("subscriber", description="administrator | editor | author | contributor | subscriber")
    bio: str = ""
    url: str = ""


class UpdateUserRequest(BaseModel):
    """PATCH /api/v1/users/:id — partial update."""
    email: str | None = Field(None, min_length=5, max_length=100)
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    bio: str | None = None
    url: str | None = None
    password: str | None = Field(None, min_length=6, max_length=128, description="Set new password")
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Full user profile returned by the API."""
    id: int
    username: str
    email: str
    display_name: str
    first_name: str = ""
    last_name: str = ""
    role: str
    avatar_url: str | None = None
    bio: str = ""
    url: str = ""
    is_active: bool = True
    oauth_provider: str | None = None
    post_count: int = 0
    capabilities: list[str] = []
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    """Paginated user list for the admin Users page."""
    items: list[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
