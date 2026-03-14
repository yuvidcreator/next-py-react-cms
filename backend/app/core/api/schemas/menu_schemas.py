"""
PyPress — Menu API Schemas

WordPress menus: wp_nav_menu + wp_nav_menu_items. A Menu is a named
container assigned to a theme location. MenuItems are the individual
links, nested for dropdown support.

    CreateMenuRequest    → POST /api/v1/menus
    UpdateMenuRequest    → PATCH /api/v1/menus/:id
    SaveMenuItemsRequest → PUT /api/v1/menus/:id/items (full replace)
    MenuItemData         → Single menu item with nesting support
    MenuResponse         → Full menu with all items
    MenuListResponse     → All menus for the Menus admin page
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MenuItemData(BaseModel):
    """A single menu item — supports nesting for dropdown menus."""
    id: int | None = None  # None for new items (server assigns ID)
    title: str
    url: str = ""
    target: str = "_self"  # _self | _blank
    type: str = "custom"  # custom | post | page | category | tag
    object_id: int | None = None  # The linked post/page/category ID
    css_classes: str = ""
    sort_order: int = 0
    children: list["MenuItemData"] = []


class CreateMenuRequest(BaseModel):
    """Create a new navigation menu."""
    name: str = Field(..., min_length=1, max_length=200)
    location: str = Field("", description="Theme location slug (e.g., 'primary', 'footer')")


class UpdateMenuRequest(BaseModel):
    """Update menu name or location assignment."""
    name: str | None = None
    location: str | None = None


class SaveMenuItemsRequest(BaseModel):
    """Replace all items in a menu (sent after drag-and-drop reordering)."""
    items: list[MenuItemData]


class MenuResponse(BaseModel):
    """Full menu with all items (nested)."""
    id: int
    name: str
    slug: str
    location: str
    items: list[MenuItemData] = []


class MenuListResponse(BaseModel):
    """All menus (for the Menus admin page)."""
    items: list[MenuResponse]
    locations: dict[str, int | None]  # {location_slug: assigned_menu_id}
