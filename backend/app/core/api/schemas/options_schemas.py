"""
PyPress — Options & Settings API Schemas

Two complementary interfaces:
    1. Options API (key-value) — like WordPress's get_option() / update_option()
       Plugins use this to store arbitrary settings.
    2. Settings API (structured) — typed site settings for the admin UI.
       The Settings pages use this for form-based editing.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# ── Options (key-value) ──────────────────────────────────────────────────

class OptionResponse(BaseModel):
    """Single option from pp_options table."""
    name: str
    value: Any
    autoload: bool = True


class UpdateOptionRequest(BaseModel):
    """Update a single option's value."""
    value: Any = Field(..., description="The option value (any JSON-serializable type)")
    autoload: bool = True


class BulkUpdateOptionsRequest(BaseModel):
    """Update multiple options at once (used by Settings pages)."""
    options: dict[str, Any] = Field(..., description="Map of option_name → value")


# ── Structured Settings ──────────────────────────────────────────────────

class GeneralSettingsResponse(BaseModel):
    """GET /api/v1/settings/general — site identity and basics."""
    site_title: str = "PyPress"
    site_tagline: str = "Just another PyPress site"
    site_url: str = "http://localhost"
    admin_email: str = "admin@pypress.local"
    timezone: str = "UTC"
    date_format: str = "F j, Y"
    time_format: str = "g:i a"
    language: str = "en_US"


class GeneralSettingsRequest(BaseModel):
    """PATCH /api/v1/settings/general — update site identity."""
    site_title: str | None = None
    site_tagline: str | None = None
    site_url: str | None = None
    admin_email: str | None = None
    timezone: str | None = None
    date_format: str | None = None
    time_format: str | None = None
    language: str | None = None


class ReadingSettingsResponse(BaseModel):
    """GET /api/v1/settings/reading — content display settings."""
    show_on_front: str = "posts"  # "posts" or "page"
    page_on_front: int = 0
    page_for_posts: int = 0
    posts_per_page: int = 10
    posts_per_rss: int = 10
    rss_use_excerpt: bool = False
    blog_public: bool = True


class ReadingSettingsRequest(BaseModel):
    show_on_front: str | None = None
    page_on_front: int | None = None
    page_for_posts: int | None = None
    posts_per_page: int | None = None
    posts_per_rss: int | None = None
    rss_use_excerpt: bool | None = None
    blog_public: bool | None = None


class WritingSettingsResponse(BaseModel):
    """GET /api/v1/settings/writing — content creation settings."""
    default_category: int = 1
    default_post_format: str = "standard"


class WritingSettingsRequest(BaseModel):
    default_category: int | None = None
    default_post_format: str | None = None


class PermalinkSettingsResponse(BaseModel):
    """GET /api/v1/settings/permalinks — URL structure."""
    permalink_structure: str = "/%postname%/"
    category_base: str = "category"
    tag_base: str = "tag"


class PermalinkSettingsRequest(BaseModel):
    permalink_structure: str | None = None
    category_base: str | None = None
    tag_base: str | None = None
