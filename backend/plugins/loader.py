"""Plugin Loader — discovers, validates, loads plugins from filesystem."""
from __future__ import annotations
import json, importlib, importlib.util, logging, sys
from pathlib import Path
from fastapi import APIRouter
from backend.plugins.base_plugin import BasePlugin, PluginManifest
from backend.core.hooks import hooks, CoreHooks
from backend.core.config import get_settings

logger = logging.getLogger(__name__)

class PluginLoadError(Exception): pass

class PluginLoader:
    def __init__(self, plugins_dir: Path | None = None):
        self._plugins_dir = plugins_dir or get_settings().PLUGINS_DIR
        self._loaded: dict[str, BasePlugin] = {}
        self._manifests: dict[str, PluginManifest] = {}
        self._load_errors: dict[str, str] = {}

    @property
    def loaded_plugins(self): return dict(self._loaded)
    @property
    def load_errors(self): return dict(self._load_errors)

    def discover_all(self) -> list[PluginManifest]:
        manifests = []; path = Path(self._plugins_dir)
        if not path.exists(): return manifests
        for d in sorted(path.iterdir()):
            if not d.is_dir() or d.name.startswith((".", "_")): continue
            mf = d / "plugin.json"
            if not mf.exists(): continue
            try:
                data = json.loads(mf.read_text())
                m = PluginManifest(name=data.get("name", d.name), slug=data.get("slug", d.name),
                    version=data.get("version", "0.0.1"), author=data.get("author", ""),
                    entry_point=data.get("entry_point", "main:Plugin"),
                    dependencies=data.get("dependencies", []),
                    settings_schema=data.get("settings_schema", {}),
                    has_admin=data.get("has_admin", False), has_frontend=data.get("has_frontend", False))
                manifests.append(m); self._manifests[m.slug] = m
            except Exception as e:
                self._load_errors[d.name] = str(e)
        return manifests

    async def load_plugin(self, slug: str) -> BasePlugin:
        if slug in self._loaded: return self._loaded[slug]
        manifest = self._manifests.get(slug)
        if not manifest: raise PluginLoadError(f"Plugin '{slug}' not found")
        plugin_dir = Path(self._plugins_dir) / slug
        try:
            mod_name, cls_name = manifest.entry_point.split(":")
            mod_path = plugin_dir / f"{mod_name}.py"
            spec = importlib.util.spec_from_file_location(f"pypress_plugins.{slug}.{mod_name}", mod_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            plugin_class = getattr(module, cls_name)
            if not issubclass(plugin_class, BasePlugin):
                raise PluginLoadError(f"'{cls_name}' must extend BasePlugin")
            instance = plugin_class(manifest)
            instance.register_hooks()
            self._loaded[slug] = instance
            return instance
        except Exception as e:
            self._load_errors[slug] = str(e)
            raise PluginLoadError(str(e)) from e

    async def load_active_plugins(self, active_slugs: list[str]) -> dict[str, BasePlugin]:
        if not self._manifests: self.discover_all()
        for slug in active_slugs:
            try: await self.load_plugin(slug)
            except PluginLoadError as e: logger.error("Skipping plugin '%s': %s", slug, e)
        await hooks.do_action(CoreHooks.PLUGINS_LOADED)
        return self._loaded

    def register_plugin_routes(self, parent_router: APIRouter) -> None:
        for slug, plugin in self._loaded.items():
            r = APIRouter(prefix=f"/plugins/{slug}", tags=[f"plugin:{slug}"])
            plugin.register_routes(r)
            if r.routes: parent_router.include_router(r)
