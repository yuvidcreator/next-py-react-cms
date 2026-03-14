"""
PyPress — Options & Settings REST API Router

Two complementary APIs:
    1. /api/v1/options — Raw key-value store (like WordPress get_option/update_option)
    2. /api/v1/settings — Structured settings for admin pages

Endpoints:
    GET    /api/v1/options/:name       — Get a single option
    PUT    /api/v1/options/:name       — Set a single option
    DELETE /api/v1/options/:name       — Delete an option
    POST   /api/v1/options/bulk        — Update multiple options at once

    GET    /api/v1/settings/general    — General settings
    PATCH  /api/v1/settings/general    — Update general settings
    GET    /api/v1/settings/reading    — Reading settings
    PATCH  /api/v1/settings/reading    — Update reading settings
    GET    /api/v1/settings/writing    — Writing settings
    PATCH  /api/v1/settings/writing    — Update writing settings
    GET    /api/v1/settings/permalinks — Permalink settings
    PATCH  /api/v1/settings/permalinks — Update permalink settings

WordPress equivalent: wp-admin/options-general.php and friends.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth.dependencies import get_current_user, require_capability, CurrentUser
from app.core.api.schemas.options_schemas import (
    OptionResponse, UpdateOptionRequest, BulkUpdateOptionsRequest,
    GeneralSettingsResponse, GeneralSettingsRequest,
    ReadingSettingsResponse, ReadingSettingsRequest,
    WritingSettingsResponse, WritingSettingsRequest,
    PermalinkSettingsResponse, PermalinkSettingsRequest,
)

# ── Routers ──────────────────────────────────────────────────────────────
options_router = APIRouter(prefix="/options", tags=["Options"])
settings_router = APIRouter(prefix="/settings", tags=["Settings"])


# =============================================================================
# IN-MEMORY OPTIONS STORE (Replace with pp_options table)
# =============================================================================
_OPTIONS: dict[str, dict] = {
    "site_title": {"name": "site_title", "value": "PyPress", "autoload": True},
    "site_tagline": {"name": "site_tagline", "value": "Just another PyPress site", "autoload": True},
    "site_url": {"name": "site_url", "value": "http://localhost", "autoload": True},
    "admin_email": {"name": "admin_email", "value": "admin@pypress.local", "autoload": True},
    "timezone": {"name": "timezone", "value": "UTC", "autoload": True},
    "date_format": {"name": "date_format", "value": "F j, Y", "autoload": True},
    "time_format": {"name": "time_format", "value": "g:i a", "autoload": True},
    "language": {"name": "language", "value": "en_US", "autoload": True},
    "show_on_front": {"name": "show_on_front", "value": "posts", "autoload": True},
    "page_on_front": {"name": "page_on_front", "value": 0, "autoload": True},
    "page_for_posts": {"name": "page_for_posts", "value": 0, "autoload": True},
    "posts_per_page": {"name": "posts_per_page", "value": 10, "autoload": True},
    "posts_per_rss": {"name": "posts_per_rss", "value": 10, "autoload": True},
    "rss_use_excerpt": {"name": "rss_use_excerpt", "value": False, "autoload": True},
    "blog_public": {"name": "blog_public", "value": True, "autoload": True},
    "default_category": {"name": "default_category", "value": 1, "autoload": True},
    "default_post_format": {"name": "default_post_format", "value": "standard", "autoload": True},
    "permalink_structure": {"name": "permalink_structure", "value": "/%postname%/", "autoload": True},
    "category_base": {"name": "category_base", "value": "category", "autoload": True},
    "tag_base": {"name": "tag_base", "value": "tag", "autoload": True},
    "active_theme": {"name": "active_theme", "value": "developer_default", "autoload": True},
    "active_plugins": {"name": "active_plugins", "value": ["hello_world"], "autoload": True},
}

def _get_opt(name: str, default=None):
    opt = _OPTIONS.get(name)
    return opt["value"] if opt else default

def _set_opt(name: str, value, autoload: bool = True):
    _OPTIONS[name] = {"name": name, "value": value, "autoload": autoload}


# =============================================================================
# OPTIONS ENDPOINTS (key-value)
# =============================================================================

@options_router.get("/{name}", response_model=OptionResponse)
async def get_option(name: str, user: CurrentUser = Depends(get_current_user)):
    """Get a single option by name. WordPress equivalent: get_option()."""
    opt = _OPTIONS.get(name)
    if not opt:
        raise HTTPException(status_code=404, detail=f"Option '{name}' not found.")
    return OptionResponse(**opt)


@options_router.put("/{name}", response_model=OptionResponse)
async def update_option(
    name: str, body: UpdateOptionRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    """Set a single option. WordPress equivalent: update_option()."""
    _set_opt(name, body.value, body.autoload)
    return OptionResponse(name=name, value=body.value, autoload=body.autoload)


@options_router.delete("/{name}")
async def delete_option(
    name: str,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    """Delete an option. WordPress equivalent: delete_option()."""
    if name not in _OPTIONS:
        raise HTTPException(status_code=404, detail=f"Option '{name}' not found.")
    del _OPTIONS[name]
    return {"message": f"Option '{name}' deleted."}


@options_router.post("/bulk")
async def bulk_update_options(
    body: BulkUpdateOptionsRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    """Update multiple options at once. Used by Settings pages on save."""
    for name, value in body.options.items():
        _set_opt(name, value)
    return {"message": f"{len(body.options)} option(s) updated.", "updated": list(body.options.keys())}


# =============================================================================
# SETTINGS ENDPOINTS (structured)
# =============================================================================

@settings_router.get("/general", response_model=GeneralSettingsResponse)
async def get_general_settings(user: CurrentUser = Depends(get_current_user)):
    return GeneralSettingsResponse(
        site_title=_get_opt("site_title", "PyPress"),
        site_tagline=_get_opt("site_tagline", ""),
        site_url=_get_opt("site_url", "http://localhost"),
        admin_email=_get_opt("admin_email", "admin@pypress.local"),
        timezone=_get_opt("timezone", "UTC"),
        date_format=_get_opt("date_format", "F j, Y"),
        time_format=_get_opt("time_format", "g:i a"),
        language=_get_opt("language", "en_US"),
    )

@settings_router.patch("/general", response_model=GeneralSettingsResponse)
async def update_general_settings(
    body: GeneralSettingsRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        _set_opt(field, value)
    return await get_general_settings(user)

@settings_router.get("/reading", response_model=ReadingSettingsResponse)
async def get_reading_settings(user: CurrentUser = Depends(get_current_user)):
    return ReadingSettingsResponse(
        show_on_front=_get_opt("show_on_front", "posts"),
        page_on_front=_get_opt("page_on_front", 0),
        page_for_posts=_get_opt("page_for_posts", 0),
        posts_per_page=_get_opt("posts_per_page", 10),
        posts_per_rss=_get_opt("posts_per_rss", 10),
        rss_use_excerpt=_get_opt("rss_use_excerpt", False),
        blog_public=_get_opt("blog_public", True),
    )

@settings_router.patch("/reading", response_model=ReadingSettingsResponse)
async def update_reading_settings(
    body: ReadingSettingsRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        _set_opt(field, value)
    return await get_reading_settings(user)

@settings_router.get("/writing", response_model=WritingSettingsResponse)
async def get_writing_settings(user: CurrentUser = Depends(get_current_user)):
    return WritingSettingsResponse(
        default_category=_get_opt("default_category", 1),
        default_post_format=_get_opt("default_post_format", "standard"),
    )

@settings_router.patch("/writing", response_model=WritingSettingsResponse)
async def update_writing_settings(
    body: WritingSettingsRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        _set_opt(field, value)
    return await get_writing_settings(user)

@settings_router.get("/permalinks", response_model=PermalinkSettingsResponse)
async def get_permalink_settings(user: CurrentUser = Depends(get_current_user)):
    return PermalinkSettingsResponse(
        permalink_structure=_get_opt("permalink_structure", "/%postname%/"),
        category_base=_get_opt("category_base", "category"),
        tag_base=_get_opt("tag_base", "tag"),
    )

@settings_router.patch("/permalinks", response_model=PermalinkSettingsResponse)
async def update_permalink_settings(
    body: PermalinkSettingsRequest,
    user: CurrentUser = Depends(require_capability("manage_options")),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        _set_opt(field, value)
    return await get_permalink_settings(user)
