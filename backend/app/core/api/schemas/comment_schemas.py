"""
PyPress — Comment API Schemas

WordPress's comment system supports nested threads, moderation statuses,
guest commenting, and bulk actions. These schemas cover all of that.

    CreateCommentRequest → POST /api/v1/comments (admin reply or guest comment)
    UpdateCommentRequest → PATCH /api/v1/comments/:id (edit content/status)
    BulkCommentAction    → POST /api/v1/comments/bulk (approve/spam/trash)
    CommentResponse      → Full comment with post title and author info
    CommentListResponse  → Paginated list for the Comments admin page
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateCommentRequest(BaseModel):
    """Create a new comment (admin reply or imported comment)."""
    post_id: int
    content: str = Field(..., min_length=1, max_length=10000)
    author_name: str = Field("", max_length=200)
    author_email: str = Field("", max_length=200)
    author_url: str = ""
    parent_id: int | None = Field(None, description="Parent comment ID for threaded replies")
    status: str = Field("pending", description="approved | pending | spam | trash")


class UpdateCommentRequest(BaseModel):
    """Partial update — edit comment content or change moderation status."""
    content: str | None = Field(None, min_length=1, max_length=10000)
    status: str | None = Field(None, description="approved | pending | spam | trash")
    author_name: str | None = None
    author_email: str | None = None
    author_url: str | None = None


class BulkCommentAction(BaseModel):
    """Bulk moderation action on multiple comments."""
    ids: list[int] = Field(..., min_length=1)
    action: str = Field(..., description="approve | spam | trash | delete")


class CommentResponse(BaseModel):
    """Full comment data for the admin panel."""
    id: int
    post_id: int
    post_title: str
    content: str
    author_name: str
    author_email: str
    author_url: str
    author_ip: str = ""
    status: str
    parent_id: int | None = None
    user_id: int | None = None
    created_at: str


class CommentListResponse(BaseModel):
    """Paginated comment list for the admin Comments page."""
    items: list[CommentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    counts: dict[str, int] = {}  # {approved: N, pending: N, spam: N, trash: N}
