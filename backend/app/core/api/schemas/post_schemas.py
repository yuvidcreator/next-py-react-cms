"""Post API Schemas — Pydantic models for request/response validation."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CreatePostRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="")
    excerpt: str = Field(default="")
    slug: str = Field(default="", max_length=200)
    status: str = Field(default="draft")
    post_type: str = Field(default="post")
    parent_id: int | None = None
    comment_status: str = Field(default="open")
    menu_order: int = Field(default=0)
    meta: dict[str, str] = Field(default_factory=dict)


class UpdatePostRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    excerpt: str | None = None
    slug: str | None = None
    status: str | None = None
    parent_id: int | None = None
    comment_status: str | None = None
    menu_order: int | None = None
    meta: dict[str, str] | None = None


class AuthorEmbedded(BaseModel):
    id: int
    username: str
    display_name: str
    model_config = ConfigDict(from_attributes=True)


class PostMetaResponse(BaseModel):
    key: str
    value: str | None


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    excerpt: str
    status: str
    post_type: str
    author: AuthorEmbedded | None = None
    parent_id: int | None = None
    comment_status: str
    comment_count: int
    menu_order: int
    guid: str
    meta: list[PostMetaResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    pages: int
    current_page: int
