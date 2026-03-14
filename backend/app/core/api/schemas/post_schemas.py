"""
PyPress — Post API Schemas

Pydantic models for Posts REST API request/response validation.
These cover every field WordPress's WP_Post has, organized by use case:

    CreatePostRequest  → POST /api/v1/posts (new post from editor)
    UpdatePostRequest  → PATCH /api/v1/posts/:id (edit existing post)
    PostResponse       → GET /api/v1/posts/:id (full post data)
    PostListQuery      → GET /api/v1/posts?... (WP_Query params)
    PostListResponse   → Paginated list of PostResponse items
    BulkActionRequest  → POST /api/v1/posts/bulk (bulk publish/draft/trash)

WordPress equivalent: There are no formal schemas in WordPress — PHP
reads $_POST directly. Pydantic gives us automatic validation, OpenAPI
docs, and type safety that catches bugs before they reach the database.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# ── Request Schemas ──────────────────────────────────────────────────────

class CreatePostRequest(BaseModel):
    """POST /api/v1/posts — create a new post or page."""
    title: str = Field(..., min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=200, description="URL slug — auto-generated from title if omitted")
    content: str = ""
    excerpt: str = ""
    status: str = Field("draft", description="publish | draft | pending | private | future")
    post_type: str = Field("post", description="post | page | attachment | custom type")
    author_id: int | None = None
    featured_image_id: int | None = None
    category_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    comment_status: str = "open"
    parent_id: int | None = None
    menu_order: int = 0
    template: str = ""
    published_at: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class UpdatePostRequest(BaseModel):
    """PATCH /api/v1/posts/:id — partial update (all fields optional)."""
    title: str | None = Field(None, min_length=1, max_length=500)
    slug: str | None = Field(None, max_length=200)
    content: str | None = None
    excerpt: str | None = None
    status: str | None = None
    author_id: int | None = None
    featured_image_id: int | None = None
    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None
    comment_status: str | None = None
    parent_id: int | None = None
    menu_order: int | None = None
    template: str | None = None
    published_at: str | None = None
    meta: dict[str, Any] | None = None


class BulkActionRequest(BaseModel):
    """POST /api/v1/posts/bulk — bulk operations on multiple posts."""
    ids: list[int] = Field(..., min_length=1, description="Post IDs to act on")
    action: str = Field(..., description="publish | draft | trash | delete")


# ── Response Schemas ─────────────────────────────────────────────────────

class PostAuthorResponse(BaseModel):
    """Embedded author data in post responses."""
    id: int
    display_name: str
    avatar_url: str | None = None


class TermResponse(BaseModel):
    """Embedded term (category/tag) data in post responses."""
    id: int
    name: str
    slug: str
    taxonomy: str


class PostResponse(BaseModel):
    """Full post response — returned by GET, POST, PATCH."""
    id: int
    title: str
    slug: str
    content: str
    excerpt: str
    status: str
    post_type: str
    author: PostAuthorResponse
    featured_image: dict | None = None
    categories: list[TermResponse] = []
    tags: list[TermResponse] = []
    comment_status: str
    comment_count: int = 0
    parent_id: int | None = None
    menu_order: int = 0
    template: str = ""
    published_at: str | None = None
    created_at: str
    updated_at: str
    meta: dict[str, Any] = {}


class PostListResponse(BaseModel):
    """Paginated post list — returned by GET /api/v1/posts."""
    items: list[PostResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
