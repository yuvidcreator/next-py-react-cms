"""Theme System — Template Hierarchy Resolver + Theme Management."""
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from backend.app.core.config import get_settings
from backend.app.core.hooks import hooks, CoreHooks

logger = logging.getLogger(__name__)

@dataclass
class ThemeManifest:
    name: str = ""; slug: str = ""; version: str = "1.0.0"; author: str = ""
    description: str = ""; screenshot: str = ""; parent_theme: str | None = None
    template_hierarchy: dict[str, str] = field(default_factory=dict)
    widget_areas: list[dict[str, str]] = field(default_factory=list)
    menu_locations: list[dict[str, str]] = field(default_factory=list)
    theme_supports: list[str] = field(default_factory=list)
    settings_schema: dict[str, Any] = field(default_factory=dict)

class TemplateResolver:
    """Resolves templates via WordPress's exact template hierarchy."""
    def __init__(self, manifest: ThemeManifest):
        self._manifest = manifest

    async def resolve(self, context: dict[str, Any]) -> str:
        hierarchy = self._build_hierarchy(context)
        for tpl in hierarchy:
            resolved = await hooks.apply_filters(CoreHooks.TEMPLATE_INCLUDE, tpl, context)
            if resolved: return resolved
        return "Index"

    def _build_hierarchy(self, ctx: dict[str, Any]) -> list[str]:
        t = ctx.get("type", "index")
        if t == "single":
            pt = ctx.get("post_type", "post"); s = ctx.get("slug", "")
            h = []
            if s: h.append(f"Single{pt.capitalize()}{s.capitalize()}")
            h.extend([f"Single{pt.capitalize()}", "Single", "Singular", "Index"])
            return h
        elif t == "page":
            s = ctx.get("slug", ""); custom = ctx.get("custom_template", "")
            h = []
            if custom: h.append(custom)
            if s: h.append(f"Page{s.capitalize()}")
            h.extend(["Page", "Singular", "Index"]); return h
        elif t == "category":
            s = ctx.get("slug", ""); h = []
            if s: h.append(f"Category{s.capitalize()}")
            h.extend(["Category", "Archive", "Index"]); return h
        elif t == "tag":
            s = ctx.get("slug", ""); h = []
            if s: h.append(f"Tag{s.capitalize()}")
            h.extend(["Tag", "Archive", "Index"]); return h
        elif t == "author":
            return ["Author", "Archive", "Index"]
        elif t == "search": return ["Search", "Archive", "Index"]
        elif t == "front_page": return ["FrontPage", "Home", "Index"]
        elif t == "404": return ["NotFound", "Index"]
        return ["Index"]

class WidgetAreaRegistry:
    def __init__(self): self._areas: dict[str, dict] = {}
    def register(self, area_id: str, name: str, description: str = ""):
        self._areas[area_id] = {"id": area_id, "name": name, "description": description, "widgets": []}
    def get_area(self, area_id: str): return self._areas.get(area_id)
    def get_all_areas(self): return dict(self._areas)

class ThemeLoader:
    def __init__(self, themes_dir: Path | None = None):
        self._themes_dir = themes_dir or get_settings().THEMES_DIR
        self._manifests: dict[str, ThemeManifest] = {}
        self._active_theme: ThemeManifest | None = None
        self._template_resolver: TemplateResolver | None = None
        self._widget_registry = WidgetAreaRegistry()

    @property
    def active_theme(self): return self._active_theme
    @property
    def template_resolver(self): return self._template_resolver
    @property
    def widget_registry(self): return self._widget_registry

    def discover_all(self) -> list[ThemeManifest]:
        manifests = []; path = Path(self._themes_dir)
        if not path.exists(): return manifests
        for d in sorted(path.iterdir()):
            if not d.is_dir() or d.name.startswith((".", "_")): continue
            mf = d / "theme.json"
            if not mf.exists(): continue
            try:
                data = json.loads(mf.read_text())
                m = ThemeManifest(name=data.get("name", d.name), slug=data.get("slug", d.name),
                    version=data.get("version", "1.0.0"), author=data.get("author", ""),
                    description=data.get("description", ""),
                    widget_areas=data.get("widget_areas", []),
                    menu_locations=data.get("menu_locations", []),
                    theme_supports=data.get("theme_supports", []),
                    template_hierarchy=data.get("template_hierarchy", {}),
                    settings_schema=data.get("settings_schema", {}))
                manifests.append(m); self._manifests[m.slug] = m
            except Exception as e: logger.error("Theme parse error %s: %s", d.name, e)
        return manifests

    async def activate_theme(self, slug: str) -> ThemeManifest:
        if slug not in self._manifests: self.discover_all()
        m = self._manifests.get(slug)
        if not m: raise ValueError(f"Theme '{slug}' not found")
        self._template_resolver = TemplateResolver(m)
        for area in m.widget_areas:
            self._widget_registry.register(area["id"], area["name"], area.get("description", ""))
        self._active_theme = m
        await hooks.do_action(CoreHooks.AFTER_SETUP_THEME, theme=m)
        logger.info("Theme activated: %s v%s", m.name, m.version)
        return m
