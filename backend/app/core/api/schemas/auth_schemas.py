"""
PyPress — Auth API Schemas (Pydantic)

Request and response models for authentication endpoints.
These are validated automatically by FastAPI — invalid requests get a
422 Unprocessable Entity response with details about what's wrong.

WordPress equivalent: WordPress validates auth data inline in wp_signon().
Pydantic separates validation from business logic (Single Responsibility).
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login — request body."""
    username: str = Field(
        ..., min_length=1, max_length=150,
        description="Username or email address"
    )
    password: str = Field(
        ..., min_length=1, max_length=128,
        description="Account password"
    )


class LoginResponse(BaseModel):
    """
    POST /api/v1/auth/login — response body.

    NOTE: Tokens are in httpOnly cookies, NOT in this response.
    The user dict is provided so the frontend can populate the UI
    immediately without a separate GET /auth/me call.
    """
    message: str = "Login successful"
    user: dict  # {id, username, email, display_name, roles}


class RefreshResponse(BaseModel):
    """POST /api/v1/auth/refresh — response body."""
    message: str = "Token refreshed successfully"


class LogoutResponse(BaseModel):
    """POST /api/v1/auth/logout — response body."""
    message: str = "Logged out successfully"


class MeResponse(BaseModel):
    """
    GET /api/v1/auth/me — response body.

    Returns the full user profile including the WordPress-compatible
    capabilities array. The admin panel uses this to:
      1. Display the user's name and avatar in the topbar
      2. Check capabilities to show/hide admin menu items
      3. Enforce per-page access control
    """
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
    capabilities: list[str] = []
    active_sessions: int = 0
    created_at: str = ""
    updated_at: str = ""
