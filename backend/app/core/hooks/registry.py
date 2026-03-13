"""
PyPress Hook System — Observer pattern with priority queues.
Direct equivalent of WordPress's add_action/add_filter/do_action/apply_filters.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Union
from collections import defaultdict
from enum import IntEnum

logger = logging.getLogger(__name__)

HookCallback = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class HookPriority(IntEnum):
    EARLIEST = 1
    EARLY = 5
    NORMAL = 10
    LATE = 15
    LATEST = 20
    FINAL = 100


@dataclass(order=True)
class HookEntry:
    priority: int
    registration_order: int
    callback: HookCallback = field(compare=False)
    accepted_args: int = field(default=0, compare=False)
    source: str = field(default="core", compare=False)


class HookRegistry:
    """Central registry for all actions and filters — WordPress's Plugin API."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookEntry]] = defaultdict(list)
        self._registration_counter: int = 0
        self._currently_executing: str | None = None

    def add_action(self, hook_name: str, callback: HookCallback,
                   priority: int = HookPriority.NORMAL, accepted_args: int = 0,
                   source: str = "core") -> None:
        self._register(hook_name, callback, priority, accepted_args, source)

    def add_filter(self, hook_name: str, callback: HookCallback,
                   priority: int = HookPriority.NORMAL, accepted_args: int = 0,
                   source: str = "core") -> None:
        self._register(hook_name, callback, priority, accepted_args, source)

    def _register(self, hook_name: str, callback: HookCallback,
                  priority: int, accepted_args: int, source: str) -> None:
        entry = HookEntry(
            priority=priority, registration_order=self._registration_counter,
            callback=callback, accepted_args=accepted_args, source=source,
        )
        self._registration_counter += 1
        self._hooks[hook_name].append(entry)
        self._hooks[hook_name].sort()

    def remove_action(self, hook_name: str, callback: HookCallback,
                      priority: int = HookPriority.NORMAL) -> bool:
        return self._remove(hook_name, callback, priority)

    def remove_filter(self, hook_name: str, callback: HookCallback,
                      priority: int = HookPriority.NORMAL) -> bool:
        return self._remove(hook_name, callback, priority)

    def _remove(self, hook_name: str, callback: HookCallback, priority: int) -> bool:
        hooks_list = self._hooks.get(hook_name, [])
        for i, entry in enumerate(hooks_list):
            if entry.callback is callback and entry.priority == priority:
                hooks_list.pop(i)
                return True
        return False

    def remove_all(self, hook_name: str) -> None:
        self._hooks.pop(hook_name, None)

    async def do_action(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        hooks_list = self._hooks.get(hook_name, [])
        if not hooks_list:
            return
        previous = self._currently_executing
        self._currently_executing = hook_name
        try:
            for entry in hooks_list:
                try:
                    result = entry.callback(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    logger.error("Error in action '%s' callback '%s' (source: %s): %s",
                                 hook_name, entry.callback.__name__, entry.source, exc, exc_info=True)
        finally:
            self._currently_executing = previous

    async def apply_filters(self, hook_name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        hooks_list = self._hooks.get(hook_name, [])
        if not hooks_list:
            return value
        previous = self._currently_executing
        self._currently_executing = hook_name
        try:
            for entry in hooks_list:
                try:
                    result = entry.callback(value, *args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    if result is not None:
                        value = result
                except Exception as exc:
                    logger.error("Error in filter '%s' callback '%s' (source: %s): %s",
                                 hook_name, entry.callback.__name__, entry.source, exc, exc_info=True)
        finally:
            self._currently_executing = previous
        return value

    def has_action(self, hook_name: str) -> bool:
        return bool(self._hooks.get(hook_name))

    def has_filter(self, hook_name: str) -> bool:
        return self.has_action(hook_name)

    def get_all_hooks(self) -> dict[str, int]:
        return {name: len(entries) for name, entries in self._hooks.items()}

    @property
    def currently_executing(self) -> str | None:
        return self._currently_executing


# Module-level singleton (like WordPress's global $wp_filter)
hooks = HookRegistry()
