"""
PyPress — Plugins & Themes REST API Router

The extensibility engine — this is what makes PyPress a platform, not just a CMS.

Plugin Endpoints:
    GET    /api/v1/plugins              — List all plugins
    GET    /api/v1/plugins/:slug        — Get plugin details
    POST   /api/v1/plugins/upload       — Upload + validate plugin .zip
    POST   /api/v1/plugins/:slug/activate   — Activate a plugin
    POST   /api/v1/plugins/:slug/deactivate — Deactivate a plugin
    DELETE /api/v1/plugins/:slug        — Uninstall (delete) a plugin

Theme Endpoints:
    GET    /api/v1/themes               — List all themes
    GET    /api/v1/themes/:slug         — Get theme details
    POST   /api/v1/themes/upload        — Upload + validate theme .zip
    POST   /api/v1/themes/:slug/activate — Activate a theme
    DELETE /api/v1/themes/:slug         — Delete a theme

WordPress equivalent: plugins.php + themes.php + plugin-install.php
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth.dependencies import CurrentUser, require_capability
from app.core.api.schemas.plugin_schemas import (
    PluginResponse, PluginListResponse, PluginUploadResponse,
    ThemeResponse, ThemeListResponse, ThemeUploadResponse,
    ValidationResult, ValidationIssue, PluginAdminPageDef,
)

plugins_router = APIRouter(prefix="/plugins", tags=["Plugins"])
themes_router = APIRouter(prefix="/themes", tags=["Themes"])


# =============================================================================
# IN-MEMORY PLUGIN STORE (Replace with Phase 1 PluginLoader)
# =============================================================================
_PLUGINS: dict[str, dict] = {
    "hello-world": {
        "slug": "hello-world", "name": "Hello World", "version": "1.0.0",
        "description": "A demo plugin that demonstrates the PyPress plugin API. Adds a greeting filter and a custom REST endpoint.",
        "author": "PyPress Team", "author_url": "https://pypress.dev",
        "is_active": True, "security_status": "ok",
        "requires_pypress": ">=0.2.0", "requires_python": ">=3.12",
        "admin_pages": [
            {"title": "Hello World Settings", "slug": "hello-world-settings", "icon": "Smile", "parent": None, "capability": "manage_options", "sort_order": 100},
        ],
        "settings_url": "/admin/plugin/hello-world/settings",
    },
    "seo-pro": {
        "slug": "seo-pro", "name": "SEO Pro", "version": "2.1.0",
        "description": "Advanced SEO toolkit: meta tags, sitemaps, Open Graph, JSON-LD structured data, and search engine integration.",
        "author": "PyPress Team", "author_url": "https://pypress.dev",
        "is_active": False, "security_status": "ok",
        "requires_pypress": ">=0.2.0", "requires_python": ">=3.12",
        "admin_pages": [
            {"title": "SEO Dashboard", "slug": "seo-dashboard", "icon": "Search", "parent": None, "capability": "manage_options", "sort_order": 101},
            {"title": "SEO Settings", "slug": "seo-settings", "icon": "Settings", "parent": "seo-dashboard", "capability": "manage_options", "sort_order": 102},
        ],
        "settings_url": "/admin/plugin/seo-pro/settings",
    },
    "contact-form": {
        "slug": "contact-form", "name": "Contact Form", "version": "1.3.0",
        "description": "Simple drag-and-drop form builder with email notifications and spam protection.",
        "author": "Community", "author_url": "",
        "is_active": False, "security_status": "warning",
        "requires_pypress": ">=0.2.0", "requires_python": ">=3.12",
        "admin_pages": [],
        "settings_url": None,
    },
}


def _to_plugin_response(p: dict) -> PluginResponse:
    return PluginResponse(
        slug=p["slug"], name=p["name"], version=p["version"],
        description=p["description"], author=p["author"],
        author_url=p.get("author_url", ""), is_active=p["is_active"],
        admin_pages=[PluginAdminPageDef(**ap) for ap in p.get("admin_pages", [])],
        settings_url=p.get("settings_url"),
        requires_pypress=p.get("requires_pypress", ""),
        requires_python=p.get("requires_python", ""),
        security_status=p.get("security_status", "ok"),
    )


# =============================================================================
# PLUGIN ENDPOINTS
# =============================================================================

@plugins_router.get("", response_model=PluginListResponse)
async def list_plugins(user: CurrentUser = Depends(require_capability("activate_plugins"))):
    """List all installed plugins. WordPress equivalent: plugins.php."""
    items = [_to_plugin_response(p) for p in _PLUGINS.values()]
    return PluginListResponse(
        items=items,
        active_count=sum(1 for p in _PLUGINS.values() if p["is_active"]),
        total_count=len(_PLUGINS),
    )


@plugins_router.get("/{slug}", response_model=PluginResponse)
async def get_plugin(slug: str, user: CurrentUser = Depends(require_capability("activate_plugins"))):
    """Get single plugin details."""
    p = _PLUGINS.get(slug)
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found.")
    return _to_plugin_response(p)


@plugins_router.post("/upload", response_model=PluginUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_plugin(user: CurrentUser = Depends(require_capability("install_plugins"))):
    """
    Upload and validate a plugin .zip file.

    WordPress equivalent: plugin-install.php + wp_handle_upload()

    Phase 1 merge will add:
      - Real .zip file upload (multipart form)
      - Extraction to temp directory
      - plugin.json manifest validation
      - Python syntax checking (ast.parse)
      - Dangerous import scanning (os.system, subprocess, eval, exec)
      - Dependency CVE checking
      - Move to plugins/installed/{slug}/

    For now, simulates a successful upload of a demo plugin.
    """
    new_slug = f"demo-plugin-{len(_PLUGINS) + 1}"
    new_plugin = {
        "slug": new_slug, "name": f"Demo Plugin {len(_PLUGINS) + 1}",
        "version": "1.0.0",
        "description": "Uploaded via the admin panel.",
        "author": "Admin", "author_url": "",
        "is_active": False, "security_status": "ok",
        "requires_pypress": ">=0.2.0", "requires_python": ">=3.12",
        "admin_pages": [], "settings_url": None,
    }
    _PLUGINS[new_slug] = new_plugin

    return PluginUploadResponse(
        message=f"Plugin '{new_plugin['name']}' installed successfully.",
        plugin=_to_plugin_response(new_plugin),
        validation=ValidationResult(
            is_valid=True,
            issues=[
                ValidationIssue(severity="info", message="Plugin manifest (plugin.json) is valid."),
                ValidationIssue(severity="info", message="No dangerous imports detected."),
                ValidationIssue(severity="info", message="All Python files pass syntax check."),
            ],
        ),
    )


@plugins_router.post("/{slug}/activate")
async def activate_plugin(slug: str, user: CurrentUser = Depends(require_capability("activate_plugins"))):
    """
    Activate a plugin. WordPress equivalent: activate_plugin().

    Runs the plugin's activate() lifecycle hook, registers its hooks
    with the HookRegistry, runs any pending database migrations, and
    adds its admin pages to the sidebar.
    """
    p = _PLUGINS.get(slug)
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found.")
    if p["is_active"]:
        raise HTTPException(status_code=400, detail="Plugin is already active.")

    # Phase 1 merge: plugin_loader.activate(slug)
    # This runs: plugin.activate(), registers hooks, runs migrations
    p["is_active"] = True

    return {"message": f"Plugin '{p['name']}' activated.", "slug": slug}


@plugins_router.post("/{slug}/deactivate")
async def deactivate_plugin(slug: str, user: CurrentUser = Depends(require_capability("activate_plugins"))):
    """
    Deactivate a plugin. WordPress equivalent: deactivate_plugins().

    Runs the plugin's deactivate() lifecycle hook and unregisters
    its hooks from the HookRegistry. Does NOT delete the plugin files.
    """
    p = _PLUGINS.get(slug)
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found.")
    if not p["is_active"]:
        raise HTTPException(status_code=400, detail="Plugin is already inactive.")

    p["is_active"] = False

    return {"message": f"Plugin '{p['name']}' deactivated.", "slug": slug}


@plugins_router.delete("/{slug}")
async def delete_plugin(slug: str, user: CurrentUser = Depends(require_capability("delete_plugins"))):
    """
    Uninstall and delete a plugin. WordPress equivalent: delete_plugins().

    Runs the plugin's uninstall() lifecycle hook (cleanup DB tables, options),
    then removes the plugin files from plugins/installed/{slug}/.
    Cannot delete an active plugin — must deactivate first.
    """
    p = _PLUGINS.get(slug)
    if not p:
        raise HTTPException(status_code=404, detail="Plugin not found.")
    if p["is_active"]:
        raise HTTPException(status_code=400, detail="Deactivate the plugin before deleting.")

    del _PLUGINS[slug]
    return {"message": f"Plugin '{p['name']}' deleted.", "slug": slug}


# =============================================================================
# IN-MEMORY THEME STORE (Replace with Phase 1 ThemeLoader)
# =============================================================================
_ACTIVE_THEME = "developer-default"

_THEMES: dict[str, dict] = {
    "developer-default": {
        "slug": "developer-default", "name": "Developer Default", "version": "1.0.0",
        "description": "The default PyPress theme — clean, minimal, and developer-friendly. Supports all template types and widget areas.",
        "author": "PyPress Team", "screenshot_url": None,
        "supports": ["widgets", "menus", "custom-header", "custom-logo", "post-thumbnails"],
        "template_files": ["Index", "Single", "Page", "Archive", "Search", "NotFound", "Header", "Footer"],
    },
    "developer-starter": {
        "slug": "developer-starter", "name": "Developer Starter", "version": "0.5.0",
        "description": "A bare-bones starter theme for developers who want to build from scratch.",
        "author": "PyPress Team", "screenshot_url": None,
        "supports": ["widgets", "menus"],
        "template_files": ["Index", "Single", "Page"],
    },
}


def _to_theme_response(t: dict) -> ThemeResponse:
    return ThemeResponse(
        slug=t["slug"], name=t["name"], version=t["version"],
        description=t["description"], author=t["author"],
        screenshot_url=t.get("screenshot_url"),
        is_active=(t["slug"] == _ACTIVE_THEME),
        supports=t.get("supports", []),
        template_files=t.get("template_files", []),
    )


# =============================================================================
# THEME ENDPOINTS
# =============================================================================

@themes_router.get("", response_model=ThemeListResponse)
async def list_themes(user: CurrentUser = Depends(require_capability("switch_themes"))):
    """List all installed themes. WordPress equivalent: themes.php."""
    return ThemeListResponse(
        items=[_to_theme_response(t) for t in _THEMES.values()],
        active_theme=_ACTIVE_THEME,
    )


@themes_router.get("/{slug}", response_model=ThemeResponse)
async def get_theme(slug: str, user: CurrentUser = Depends(require_capability("switch_themes"))):
    t = _THEMES.get(slug)
    if not t:
        raise HTTPException(status_code=404, detail="Theme not found.")
    return _to_theme_response(t)


@themes_router.post("/upload", response_model=ThemeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_theme(user: CurrentUser = Depends(require_capability("install_themes"))):
    """Upload and validate a theme .zip. Simulated for now."""
    new_slug = f"custom-theme-{len(_THEMES) + 1}"
    new_theme = {
        "slug": new_slug, "name": f"Custom Theme {len(_THEMES) + 1}",
        "version": "1.0.0", "description": "Uploaded via admin panel.",
        "author": "Admin", "screenshot_url": None,
        "supports": ["widgets", "menus"],
        "template_files": ["Index", "Single", "Page"],
    }
    _THEMES[new_slug] = new_theme

    return ThemeUploadResponse(
        message=f"Theme '{new_theme['name']}' installed.",
        theme=_to_theme_response(new_theme),
        validation=ValidationResult(is_valid=True, issues=[
            ValidationIssue(severity="info", message="Theme manifest (theme.json) is valid."),
            ValidationIssue(severity="info", message="Required templates found: Index, Single, Page."),
        ]),
    )


@themes_router.post("/{slug}/activate")
async def activate_theme(slug: str, user: CurrentUser = Depends(require_capability("switch_themes"))):
    """Activate a theme. WordPress equivalent: switch_theme()."""
    global _ACTIVE_THEME
    if slug not in _THEMES:
        raise HTTPException(status_code=404, detail="Theme not found.")
    _ACTIVE_THEME = slug
    return {"message": f"Theme '{_THEMES[slug]['name']}' activated.", "slug": slug}


@themes_router.delete("/{slug}")
async def delete_theme(slug: str, user: CurrentUser = Depends(require_capability("delete_themes"))):
    """Delete a theme. Cannot delete the active theme."""
    if slug not in _THEMES:
        raise HTTPException(status_code=404, detail="Theme not found.")
    if slug == _ACTIVE_THEME:
        raise HTTPException(status_code=400, detail="Cannot delete the active theme. Switch to another theme first.")
    del _THEMES[slug]
    return {"message": f"Theme deleted.", "slug": slug}
