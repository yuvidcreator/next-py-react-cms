"""BasePlugin — ABC that every plugin extends. Template Method pattern for lifecycle."""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from backend.core.hooks import hooks, IHookable, IActivatable
if TYPE_CHECKING:
    from fastapi import APIRouter

logger = logging.getLogger(__name__)

@dataclass
class PluginManifest:
    name: str = ""; slug: str = ""; version: str = "0.0.1"; author: str = ""
    author_uri: str = ""; description: str = ""; requires_pypress: str = ""
    requires_python: str = ""; entry_point: str = "main:Plugin"
    dependencies: list[str] = field(default_factory=list)
    settings_schema: dict[str, Any] = field(default_factory=dict)
    has_admin: bool = False; has_frontend: bool = False; network_wide: bool = False

class BasePlugin(ABC, IHookable, IActivatable):
    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest; self.hooks = hooks; self._is_active = False
        self.logger = logging.getLogger(f"plugin.{manifest.slug}")

    @property
    def name(self) -> str: return self.manifest.name
    @property
    def slug(self) -> str: return self.manifest.slug
    @property
    def version(self) -> str: return self.manifest.version
    @property
    def is_active(self) -> bool: return self._is_active

    @abstractmethod
    def register_hooks(self) -> None: ...

    async def activate(self) -> None:
        self._is_active = True
        self.logger.info("Plugin activated: %s v%s", self.name, self.version)
    async def deactivate(self) -> None:
        self._is_active = False
        self.logger.info("Plugin deactivated: %s", self.name)
    async def uninstall(self) -> None:
        self.logger.info("Plugin uninstalled: %s", self.name)
    def register_routes(self, router: "APIRouter") -> None: pass
    def register_admin_pages(self) -> list[dict[str, Any]]: return []
