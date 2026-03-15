"""
PyPress — Admin Menu API

Serves the dynamic sidebar menu by merging core menu items with
plugin-registered admin pages.

Endpoint:
    GET /api/v1/admin/menu — Returns the complete admin menu tree

WordPress equivalent: The admin menu system built by wp-admin/menu.php
combined with add_menu_page() / add_submenu_page() calls from plugins.

The frontend Sidebar component calls this endpoint on mount and whenever
plugins are activated/deactivated. It receives the full menu and renders
it directly, replacing the static ADMIN_MENU config.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


# =============================================================================
# CORE MENU DEFINITION (mirrors the static frontend ADMIN_MENU config)
# =============================================================================
CORE_MENU = [
    {"id": "dashboard", "label": "Dashboard", "icon": "LayoutDashboard", "path": "/", "capability": "read", "order": 2, "children": [], "divider_before": False, "source": "core"},
    {"id": "posts", "label": "Posts", "icon": "FileText", "path": "/posts", "capability": "edit_posts", "order": 5, "divider_before": True, "source": "core", "children": [
        {"id": "posts-all", "label": "All Posts", "path": "/posts", "capability": "edit_posts"},
        {"id": "posts-new", "label": "Add New", "path": "/posts/new", "capability": "edit_posts"},
        {"id": "posts-categories", "label": "Categories", "path": "/categories", "capability": "manage_categories"},
        {"id": "posts-tags", "label": "Tags", "path": "/tags", "capability": "manage_categories"},
    ]},
    {"id": "pages", "label": "Pages", "icon": "File", "path": "/pages", "capability": "edit_pages", "order": 10, "divider_before": False, "source": "core", "children": [
        {"id": "pages-all", "label": "All Pages", "path": "/pages", "capability": "edit_pages"},
        {"id": "pages-new", "label": "Add New", "path": "/pages/new", "capability": "edit_pages"},
    ]},
    {"id": "media", "label": "Media", "icon": "Image", "path": "/media", "capability": "upload_files", "order": 15, "divider_before": False, "source": "core", "children": []},
    {"id": "comments", "label": "Comments", "icon": "MessageSquare", "path": "/comments", "capability": "moderate_comments", "order": 20, "divider_before": False, "source": "core", "children": []},
    {"id": "users", "label": "Users", "icon": "Users", "path": "/users", "capability": "list_users", "order": 40, "divider_before": True, "source": "core", "children": [
        {"id": "users-all", "label": "All Users", "path": "/users", "capability": "list_users"},
        {"id": "users-new", "label": "Add New", "path": "/users/new", "capability": "create_users"},
    ]},
    {"id": "plugins", "label": "Plugins", "icon": "Puzzle", "path": "/plugins", "capability": "activate_plugins", "order": 50, "divider_before": True, "source": "core", "children": []},
    {"id": "themes", "label": "Themes", "icon": "Palette", "path": "/themes", "capability": "switch_themes", "order": 55, "divider_before": False, "source": "core", "children": []},
    {"id": "menus", "label": "Menus", "icon": "Menu", "path": "/menus", "capability": "edit_theme_options", "order": 60, "divider_before": False, "source": "core", "children": []},
    {"id": "widgets", "label": "Widgets", "icon": "PanelLeft", "path": "/widgets", "capability": "edit_theme_options", "order": 65, "divider_before": False, "source": "core", "children": []},
    {"id": "settings", "label": "Settings", "icon": "Settings", "path": "/settings", "capability": "manage_options", "order": 80, "divider_before": True, "source": "core", "children": [
        {"id": "settings-general", "label": "General", "path": "/settings", "capability": "manage_options"},
        {"id": "settings-reading", "label": "Reading", "path": "/settings/reading", "capability": "manage_options"},
        {"id": "settings-writing", "label": "Writing", "path": "/settings/writing", "capability": "manage_options"},
        {"id": "settings-permalinks", "label": "Permalinks", "path": "/settings/permalinks", "capability": "manage_options"},
    ]},
    {"id": "tools", "label": "Tools", "icon": "Wrench", "path": "/tools", "capability": "edit_posts", "order": 85, "divider_before": False, "source": "core", "children": [
        {"id": "tools-main", "label": "Available Tools", "path": "/tools", "capability": "edit_posts"},
        {"id": "tools-import", "label": "Import", "path": "/tools/import", "capability": "import"},
        {"id": "tools-export", "label": "Export", "path": "/tools/export", "capability": "export"},
    ]},
]


def _get_plugin_menu_items() -> list[dict]:
    """
    Fetch admin pages registered by active plugins.

    WordPress equivalent: The loop in wp-admin/menu.php that calls
    each plugin's add_menu_page() / add_submenu_page() registrations.

    Replace with Phase 1's PluginLoader.get_active_admin_pages() when merging.
    """
    from app.core.api.v1.plugins_themes import _PLUGINS

    items = []
    for plugin in _PLUGINS.values():
        if not plugin["is_active"]:
            continue
        for page in plugin.get("admin_pages", []):
            if page.get("parent"):
                # Sub-page — will be attached to a parent menu item
                continue
            items.append({
                "id": f"plugin-{plugin['slug']}-{page['slug']}",
                "label": page["title"],
                "icon": page.get("icon", "Puzzle"),
                "path": f"/plugin/{plugin['slug']}/{page['slug']}",
                "capability": page.get("capability", "manage_options"),
                "order": page.get("sort_order", 100),
                "divider_before": False,
                "source": f"plugin:{plugin['slug']}",
                "children": [
                    {
                        "id": f"plugin-{plugin['slug']}-{sub['slug']}",
                        "label": sub["title"],
                        "path": f"/plugin/{plugin['slug']}/{sub['slug']}",
                        "capability": sub.get("capability", "manage_options"),
                    }
                    for sub in plugin.get("admin_pages", [])
                    if sub.get("parent") == page["slug"]
                ],
            })
    return items


def _filter_by_capability(menu: list[dict], user: CurrentUser) -> list[dict]:
    """Filter menu items by user capabilities (like WordPress's capability-based menu)."""
    filtered = []
    for item in menu:
        if not user.can(item["capability"]):
            continue
        # Filter children too
        item_copy = dict(item)
        if item_copy.get("children"):
            item_copy["children"] = [
                child for child in item_copy["children"]
                if user.can(child.get("capability", "read"))
            ]
        filtered.append(item_copy)
    return filtered


# =============================================================================
# ENDPOINT
# =============================================================================

@router.get("/menu")
async def get_admin_menu(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get the complete admin menu for the current user.

    Merges core menu items with plugin-registered pages,
    sorts by order, and filters by the user's capabilities.

    The frontend Sidebar calls this on mount and when plugins change.
    """
    # Start with core menu
    menu = [dict(item) for item in CORE_MENU]

    # Inject plugin pages
    plugin_items = _get_plugin_menu_items()

    # Insert plugin items at the correct position based on order
    menu.extend(plugin_items)

    # Sort by order
    menu.sort(key=lambda item: item.get("order", 999))

    # Filter by user capabilities
    menu = _filter_by_capability(menu, user)

    return {
        "items": menu,
        "plugin_count": len(plugin_items),
    }
