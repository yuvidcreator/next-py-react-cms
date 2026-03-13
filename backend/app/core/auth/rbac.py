"""
RBAC System — WordPress-compatible Role-Based Access Control.

Roles: administrator, editor, author, contributor, subscriber
Each role has a defined set of capabilities (edit_posts, manage_options, etc.)
Plugins can add custom roles and capabilities via the hook system.
"""
from __future__ import annotations
from enum import Enum


class DefaultRole(str, Enum):
    ADMINISTRATOR = "administrator"
    EDITOR = "editor"
    AUTHOR = "author"
    CONTRIBUTOR = "contributor"
    SUBSCRIBER = "subscriber"


# WordPress's complete default capability map — EXACT same set
DEFAULT_ROLE_CAPABILITIES: dict[str, list[str]] = {
    "administrator": [
        "manage_options", "manage_links", "manage_categories",
        "moderate_comments", "unfiltered_html", "edit_dashboard",
        "update_plugins", "delete_plugins", "install_plugins",
        "update_themes", "install_themes", "switch_themes", "edit_themes",
        "activate_plugins", "edit_plugins",
        "create_users", "delete_users", "edit_users", "list_users",
        "promote_users", "remove_users", "export", "import",
        "edit_posts", "edit_others_posts", "edit_published_posts",
        "publish_posts", "edit_pages", "edit_others_pages",
        "edit_published_pages", "publish_pages",
        "delete_posts", "delete_others_posts", "delete_published_posts",
        "delete_pages", "delete_others_pages", "delete_published_pages",
        "delete_private_posts", "edit_private_posts", "read_private_posts",
        "delete_private_pages", "edit_private_pages", "read_private_pages",
        "upload_files", "read",
    ],
    "editor": [
        "edit_posts", "edit_others_posts", "edit_published_posts",
        "publish_posts", "edit_pages", "edit_others_pages",
        "edit_published_pages", "publish_pages",
        "delete_posts", "delete_others_posts", "delete_published_posts",
        "delete_pages", "delete_others_pages", "delete_published_pages",
        "delete_private_posts", "edit_private_posts", "read_private_posts",
        "delete_private_pages", "edit_private_pages", "read_private_pages",
        "manage_categories", "manage_links", "moderate_comments",
        "upload_files", "unfiltered_html", "read",
    ],
    "author": [
        "edit_posts", "edit_published_posts", "publish_posts",
        "delete_posts", "delete_published_posts", "upload_files", "read",
    ],
    "contributor": ["edit_posts", "delete_posts", "read"],
    "subscriber": ["read"],
}


class CapabilityChecker:
    """
    Checks user capabilities — equivalent to WordPress's current_user_can().
    Plugins can add custom roles via add_role() or capabilities via add_cap_to_role().
    """

    def __init__(self) -> None:
        self._role_caps: dict[str, set[str]] = {
            role: set(caps) for role, caps in DEFAULT_ROLE_CAPABILITIES.items()
        }

    def add_role(self, role: str, capabilities: list[str]) -> None:
        """Register a new role (like WordPress's add_role). Plugins use this."""
        self._role_caps[role] = set(capabilities)

    def remove_role(self, role: str) -> None:
        self._role_caps.pop(role, None)

    def add_cap_to_role(self, role: str, capability: str) -> None:
        if role in self._role_caps:
            self._role_caps[role].add(capability)

    def remove_cap_from_role(self, role: str, capability: str) -> None:
        if role in self._role_caps:
            self._role_caps[role].discard(capability)

    def user_can(self, user_roles: list[str], capability: str) -> bool:
        """Check if user (by roles) has a capability. Returns True if ANY role grants it."""
        for role in user_roles:
            if capability in self._role_caps.get(role, set()):
                return True
        return False

    def get_role_capabilities(self, role: str) -> set[str]:
        return self._role_caps.get(role, set()).copy()

    def get_all_roles(self) -> dict[str, set[str]]:
        return {role: caps.copy() for role, caps in self._role_caps.items()}


# Module-level singleton
capability_checker = CapabilityChecker()
