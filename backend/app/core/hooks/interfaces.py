"""Hook Interfaces — ABCs for hookable components (Interface Segregation Principle)."""
from abc import ABC, abstractmethod
from typing import Any


class IHookable(ABC):
    @abstractmethod
    def register_hooks(self) -> None: ...

class IActivatable(ABC):
    @abstractmethod
    async def activate(self) -> None: ...
    @abstractmethod
    async def deactivate(self) -> None: ...

class IRenderable(ABC):
    @abstractmethod
    def render(self, context: dict[str, Any] | None = None) -> dict[str, Any]: ...
