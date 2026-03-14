"""
PyPress — Taxonomy API Schemas

Pydantic models for the unified taxonomy system (Categories + Tags + custom).
WordPress uses the same DB tables for all taxonomies — the `taxonomy` column
discriminates between category, post_tag, and custom taxonomies.

    CreateTermRequest   → POST /api/v1/taxonomies/:taxonomy
    UpdateTermRequest   → PATCH /api/v1/taxonomies/:taxonomy/:id
    TermResponse        → Single term with count and parent info
    TermTreeResponse    → Hierarchical term (for categories with children)
    TermListResponse    → Paginated flat list
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateTermRequest(BaseModel):
    """Create a new term (category, tag, or custom taxonomy term)."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=200, description="Auto-generated from name if omitted")
    description: str = ""
    parent_id: int | None = Field(None, description="Parent term ID (categories only — ignored for tags)")


class UpdateTermRequest(BaseModel):
    """Partial update of a term."""
    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=200)
    description: str | None = None
    parent_id: int | None = None


class MergeTermsRequest(BaseModel):
    """Merge multiple terms into one (for tags). WordPress equivalent: wp_merge_terms()."""
    source_ids: list[int] = Field(..., min_length=1, description="Terms to merge FROM (will be deleted)")
    target_id: int = Field(..., description="Term to merge INTO (will be kept)")


class TermResponse(BaseModel):
    """Single taxonomy term with metadata."""
    id: int
    name: str
    slug: str
    taxonomy: str
    description: str = ""
    parent_id: int | None = None
    count: int = 0


class TermTreeResponse(TermResponse):
    """Hierarchical term with nested children (for category tree view)."""
    children: list["TermTreeResponse"] = []


class TermListResponse(BaseModel):
    """Paginated term list."""
    items: list[TermResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
