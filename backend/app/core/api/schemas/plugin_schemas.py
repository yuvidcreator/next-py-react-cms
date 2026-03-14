"""
PyPress — Plugin & Theme API Schemas

The extensibility system's data contracts. These schemas define:
  - Plugin manifests (plugin.json structure)
  - Theme manifests (theme.json structure)
  - Validation results from the security scanner
  - List/detail responses for the admin UI

WordPress equivalent: Plugin headers (parsed from PHP comments) and
theme's style.css headers. PyPress uses JSON manifests instead of
comment parsing — more structured, validatable, and IDE-friendly.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# =============================================================================
# PLUGIN SCHEMAS
# =============================================================================

class PluginManifest(BaseModel):
    """
    The plugin.json contract — every plugin must have this file.
    WordPress equivalent: Plugin header comments in the main PHP file.
    """
    name: str
    slug: str
    version: str
    description: str = ""
    author: str = ""
    author_url: str = ""
    plugin_url: str = ""
    license: str = "MIT"
    requires_pypress: str = ">=0.2.0"
    requires_python: str = ">=3.12"
    main_class: str = Field("", description="Python import path to the BasePlugin subclass")
    dependencies: list[str] = Field(default_factory=list, description="Other plugin slugs this depends on")
    admin_pages: list[PluginAdminPageDef] = Field(default_factory=list)
    settings_schema: dict[str, Any] = Field(default_factory=dict)


class PluginAdminPageDef(BaseModel):
    """Admin page registered by a plugin (like WordPress's add_menu_page)."""
    title: str
    slug: str
    icon: str = "Puzzle"
    parent: str | None = None
    capability: str = "manage_options"
    sort_order: int = 100


class ValidationIssue(BaseModel):
    """A single issue found during plugin/theme validation."""
    severity: str = Field(..., description="critical | warning | info")
    message: str
    file: str | None = None
    line: int | None = None


class ValidationResult(BaseModel):
    """Result of the plugin/theme security scanner."""
    is_valid: bool
    issues: list[ValidationIssue] = []
    manifest: PluginManifest | ThemeManifestResponse | None = None


class PluginResponse(BaseModel):
    """Plugin data returned by the API."""
    slug: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    author_url: str = ""
    is_active: bool = False
    admin_pages: list[PluginAdminPageDef] = []
    settings_url: str | None = None
    requires_pypress: str = ""
    requires_python: str = ""
    security_status: str = "ok"  # ok | warning | critical


class PluginListResponse(BaseModel):
    """List of all installed plugins."""
    items: list[PluginResponse]
    active_count: int
    total_count: int


class PluginUploadResponse(BaseModel):
    """Response after successful plugin upload + validation."""
    message: str
    plugin: PluginResponse
    validation: ValidationResult


# =============================================================================
# THEME SCHEMAS
# =============================================================================

class ThemeManifestResponse(BaseModel):
    """The theme.json contract."""
    name: str
    slug: str
    version: str
    description: str = ""
    author: str = ""
    screenshot_url: str | None = None
    supports: list[str] = []
    template_files: list[str] = []
    widget_areas: list[dict[str, str]] = []
    menu_locations: list[dict[str, str]] = []
    settings_schema: dict[str, Any] = {}


class ThemeResponse(BaseModel):
    """Theme data returned by the API."""
    slug: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    screenshot_url: str | None = None
    is_active: bool = False
    supports: list[str] = []
    template_files: list[str] = []


class ThemeListResponse(BaseModel):
    """All installed themes."""
    items: list[ThemeResponse]
    active_theme: str


class ThemeUploadResponse(BaseModel):
    """Response after theme upload + validation."""
    message: str
    theme: ThemeResponse
    validation: ValidationResult
