"""
PyPress — Menus REST API Router

WordPress equivalent: nav-menus.php + the Customizer menu editor

Endpoints:
    GET    /api/v1/menus           — List all menus + theme locations
    GET    /api/v1/menus/:id       — Get single menu with items
    POST   /api/v1/menus           — Create new menu
    PATCH  /api/v1/menus/:id       — Update menu name/location
    DELETE /api/v1/menus/:id       — Delete menu
    PUT    /api/v1/menus/:id/items — Replace all items (after drag-and-drop)

The items endpoint is a full-replace (PUT not PATCH) because the drag-and-drop
menu builder sends the entire item tree at once — this is simpler and less
error-prone than trying to diff individual item moves.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth.dependencies import CurrentUser, require_capability
from app.core.api.schemas.menu_schemas import (
    CreateMenuRequest, UpdateMenuRequest, SaveMenuItemsRequest,
    MenuItemData, MenuResponse, MenuListResponse,
)

router = APIRouter(prefix="/menus", tags=["Menus"])


# =============================================================================
# IN-MEMORY MENU STORE (Replace with Phase 1 Menu + MenuItem models)
# =============================================================================
_NEXT_MENU_ID = 3
_NEXT_ITEM_ID = 20

def _slugify(text: str) -> str:
    return text.lower().strip().replace(" ", "-")[:200]

# Theme-registered menu locations (from the active theme's theme.json)
# WordPress equivalent: register_nav_menus() in the theme's functions.php
_THEME_LOCATIONS: dict[str, int | None] = {
    "primary": 1,     # Main navigation — assigned to menu #1
    "footer": 2,      # Footer links — assigned to menu #2
    "social": None,    # Social media links — unassigned
}

_MENUS: dict[int, dict] = {
    1: {
        "id": 1, "name": "Main Navigation", "slug": "main-navigation", "location": "primary",
        "items": [
            {"id": 1, "title": "Home", "url": "/", "target": "_self", "type": "custom", "object_id": None, "css_classes": "", "sort_order": 0, "children": []},
            {"id": 2, "title": "Blog", "url": "/blog", "target": "_self", "type": "custom", "object_id": None, "css_classes": "", "sort_order": 1, "children": []},
            {"id": 3, "title": "About", "url": "/about", "target": "_self", "type": "page", "object_id": 5, "css_classes": "", "sort_order": 2, "children": []},
            {"id": 4, "title": "Tutorials", "url": "/category/tutorials", "target": "_self", "type": "category", "object_id": 2, "css_classes": "", "sort_order": 3, "children": [
                {"id": 5, "title": "Python", "url": "/category/python-tutorials", "target": "_self", "type": "category", "object_id": 3, "css_classes": "", "sort_order": 0, "children": []},
                {"id": 6, "title": "React", "url": "/category/react-tutorials", "target": "_self", "type": "category", "object_id": 4, "css_classes": "", "sort_order": 1, "children": []},
            ]},
        ],
    },
    2: {
        "id": 2, "name": "Footer Links", "slug": "footer-links", "location": "footer",
        "items": [
            {"id": 10, "title": "Privacy Policy", "url": "/privacy", "target": "_self", "type": "custom", "object_id": None, "css_classes": "", "sort_order": 0, "children": []},
            {"id": 11, "title": "Terms of Service", "url": "/terms", "target": "_self", "type": "custom", "object_id": None, "css_classes": "", "sort_order": 1, "children": []},
            {"id": 12, "title": "Contact", "url": "/contact", "target": "_self", "type": "custom", "object_id": None, "css_classes": "", "sort_order": 2, "children": []},
        ],
    },
}


def _assign_ids_to_items(items: list[MenuItemData]) -> list[dict]:
    """Recursively assign IDs to new menu items and convert to dicts."""
    global _NEXT_ITEM_ID
    result = []
    for item in items:
        item_id = item.id or _NEXT_ITEM_ID
        if not item.id:
            _NEXT_ITEM_ID += 1
        result.append({
            "id": item_id, "title": item.title, "url": item.url,
            "target": item.target, "type": item.type,
            "object_id": item.object_id, "css_classes": item.css_classes,
            "sort_order": item.sort_order,
            "children": _assign_ids_to_items(item.children),
        })
    return result


def _items_to_response(items: list[dict]) -> list[MenuItemData]:
    """Convert stored item dicts to schema objects."""
    return [
        MenuItemData(
            id=item["id"], title=item["title"], url=item["url"],
            target=item["target"], type=item["type"],
            object_id=item.get("object_id"), css_classes=item.get("css_classes", ""),
            sort_order=item.get("sort_order", 0),
            children=_items_to_response(item.get("children", [])),
        )
        for item in items
    ]


def _to_menu_response(menu: dict) -> MenuResponse:
    return MenuResponse(
        id=menu["id"], name=menu["name"], slug=menu["slug"],
        location=menu.get("location", ""),
        items=_items_to_response(menu.get("items", [])),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=MenuListResponse)
async def list_menus(
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """
    List all menus and theme locations.
    WordPress equivalent: nav-menus.php — shows all menus and location assignments.

    Returns both the menu list and the theme location → menu mapping so
    the admin UI can show the "Theme Locations" panel.
    """
    return MenuListResponse(
        items=[_to_menu_response(m) for m in _MENUS.values()],
        locations=_THEME_LOCATIONS,
    )


@router.get("/{menu_id}", response_model=MenuResponse)
async def get_menu(
    menu_id: int,
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """Get a single menu with all its items."""
    menu = _MENUS.get(menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found.")
    return _to_menu_response(menu)


@router.post("", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
async def create_menu(
    body: CreateMenuRequest,
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """Create a new empty menu. WordPress equivalent: wp_create_nav_menu()."""
    global _NEXT_MENU_ID

    slug = _slugify(body.name)
    for m in _MENUS.values():
        if m["slug"] == slug:
            raise HTTPException(status_code=409, detail="A menu with this name already exists.")

    menu_id = _NEXT_MENU_ID
    _NEXT_MENU_ID += 1

    menu = {
        "id": menu_id, "name": body.name, "slug": slug,
        "location": body.location, "items": [],
    }
    _MENUS[menu_id] = menu

    # Assign to theme location if specified
    if body.location and body.location in _THEME_LOCATIONS:
        # Unassign any menu currently at this location
        for loc, mid in _THEME_LOCATIONS.items():
            if mid == menu_id:
                _THEME_LOCATIONS[loc] = None
        _THEME_LOCATIONS[body.location] = menu_id

    return _to_menu_response(menu)


@router.patch("/{menu_id}", response_model=MenuResponse)
async def update_menu(
    menu_id: int,
    body: UpdateMenuRequest,
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """Update menu name or location assignment."""
    menu = _MENUS.get(menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found.")

    if body.name is not None:
        menu["name"] = body.name
        menu["slug"] = _slugify(body.name)

    if body.location is not None:
        old_location = menu.get("location")
        # Unassign from old location
        if old_location and old_location in _THEME_LOCATIONS:
            _THEME_LOCATIONS[old_location] = None
        # Assign to new location
        menu["location"] = body.location
        if body.location in _THEME_LOCATIONS:
            _THEME_LOCATIONS[body.location] = menu_id

    return _to_menu_response(menu)


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """Delete a menu and unassign it from any theme location."""
    menu = _MENUS.get(menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found.")

    # Unassign from theme location
    for loc, mid in _THEME_LOCATIONS.items():
        if mid == menu_id:
            _THEME_LOCATIONS[loc] = None

    del _MENUS[menu_id]
    return {"message": f"Menu '{menu['name']}' deleted.", "id": menu_id}


@router.put("/{menu_id}/items", response_model=MenuResponse)
async def save_menu_items(
    menu_id: int,
    body: SaveMenuItemsRequest,
    user: CurrentUser = Depends(require_capability("edit_theme_options")),
):
    """
    Replace all items in a menu. WordPress equivalent: wp_update_nav_menu_item().

    This is a full-replace (PUT) rather than a partial update because the
    drag-and-drop menu builder sends the entire item tree at once. This is
    simpler and less error-prone than trying to diff individual item moves,
    deletions, and insertions.

    New items (without an id) are automatically assigned IDs by the server.
    """
    menu = _MENUS.get(menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found.")

    menu["items"] = _assign_ids_to_items(body.items)
    return _to_menu_response(menu)
