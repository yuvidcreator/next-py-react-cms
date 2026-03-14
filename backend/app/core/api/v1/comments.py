"""
PyPress — Comments REST API Router

WordPress equivalent: edit-comments.php + wp-comments-post.php

Endpoints:
    GET    /api/v1/comments           — List comments (with status counts)
    GET    /api/v1/comments/:id       — Get single comment
    POST   /api/v1/comments           — Create comment (admin reply)
    PATCH  /api/v1/comments/:id       — Update comment (edit/moderate)
    DELETE /api/v1/comments/:id       — Permanently delete comment
    POST   /api/v1/comments/bulk      — Bulk moderation (approve/spam/trash)

The list endpoint returns `counts: {approved: N, pending: N, spam: N, trash: N}`
so the admin UI can render status tabs with counts — exactly like WordPress.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth.dependencies import CurrentUser, get_current_user, require_capability
from app.core.api.schemas.comment_schemas import (
    CreateCommentRequest, UpdateCommentRequest, BulkCommentAction,
    CommentResponse, CommentListResponse,
)

router = APIRouter(prefix="/comments", tags=["Comments"])


# =============================================================================
# IN-MEMORY COMMENT STORE (Replace with Phase 1 Comment model)
# =============================================================================
_NEXT_COMMENT_ID = 10

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# Map post IDs to titles for the comment response
_POST_TITLES = {
    1: "Getting Started with PyPress",
    2: "How to Build a Plugin",
    3: "Theme Development Guide",
    4: "Understanding the Hook System",
    5: "About",
}

_COMMENTS: dict[int, dict] = {
    1: {"id": 1, "post_id": 1, "content": "Great intro to PyPress! Looking forward to more tutorials.", "author_name": "John Doe", "author_email": "john@example.com", "author_url": "https://johndoe.com", "author_ip": "192.168.1.10", "status": "approved", "parent_id": None, "user_id": None, "created_at": "2026-03-10T12:00:00Z"},
    2: {"id": 2, "post_id": 1, "content": "Thanks John! More tutorials are on the way.", "author_name": "Administrator", "author_email": "admin@pypress.local", "author_url": "", "author_ip": "127.0.0.1", "status": "approved", "parent_id": 1, "user_id": 1, "created_at": "2026-03-10T14:00:00Z"},
    3: {"id": 3, "post_id": 1, "content": "When will the plugin system documentation be ready?", "author_name": "Jane Smith", "author_email": "jane@example.com", "author_url": "", "author_ip": "192.168.1.20", "status": "approved", "parent_id": None, "user_id": None, "created_at": "2026-03-11T09:00:00Z"},
    4: {"id": 4, "post_id": 3, "content": "This theme guide is exactly what I needed. Very thorough!", "author_name": "Dev Alice", "author_email": "alice@dev.com", "author_url": "https://alice.dev", "author_ip": "10.0.0.5", "status": "approved", "parent_id": None, "user_id": None, "created_at": "2026-03-12T11:00:00Z"},
    5: {"id": 5, "post_id": 3, "content": "How do I create a child theme? Is it similar to WordPress?", "author_name": "Bob Builder", "author_email": "bob@example.com", "author_url": "", "author_ip": "10.0.0.6", "status": "approved", "parent_id": None, "user_id": None, "created_at": "2026-03-12T15:30:00Z"},
    6: {"id": 6, "post_id": 3, "content": "Yes Bob — child themes work the same way. Override specific templates while inheriting the rest.", "author_name": "Administrator", "author_email": "admin@pypress.local", "author_url": "", "author_ip": "127.0.0.1", "status": "approved", "parent_id": 5, "user_id": 1, "created_at": "2026-03-12T16:00:00Z"},
    7: {"id": 7, "post_id": 4, "content": "Could you explain the difference between actions and filters more?", "author_name": "New Dev", "author_email": "newdev@example.com", "author_url": "", "author_ip": "172.16.0.1", "status": "pending", "parent_id": None, "user_id": None, "created_at": "2026-03-13T10:00:00Z"},
    8: {"id": 8, "post_id": 1, "content": "Buy cheap products at spam-site.com!!!", "author_name": "Spammer", "author_email": "spam@evil.com", "author_url": "https://spam-site.com", "author_ip": "203.0.113.1", "status": "spam", "parent_id": None, "user_id": None, "created_at": "2026-03-13T20:00:00Z"},
    9: {"id": 9, "post_id": 3, "content": "Test comment — should be deleted", "author_name": "Test", "author_email": "test@test.com", "author_url": "", "author_ip": "127.0.0.1", "status": "trash", "parent_id": None, "user_id": None, "created_at": "2026-03-14T01:00:00Z"},
}


def _get_status_counts() -> dict[str, int]:
    """Count comments by status — powers the admin page status tabs."""
    counts: dict[str, int] = {"approved": 0, "pending": 0, "spam": 0, "trash": 0}
    for c in _COMMENTS.values():
        s = c["status"]
        if s in counts:
            counts[s] += 1
    return counts


def _to_comment_response(c: dict) -> CommentResponse:
    post_title = _POST_TITLES.get(c["post_id"], f"Post #{c['post_id']}")
    return CommentResponse(
        id=c["id"], post_id=c["post_id"], post_title=post_title,
        content=c["content"], author_name=c["author_name"],
        author_email=c["author_email"], author_url=c.get("author_url", ""),
        author_ip=c.get("author_ip", ""), status=c["status"],
        parent_id=c.get("parent_id"), user_id=c.get("user_id"),
        created_at=c["created_at"],
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=CommentListResponse)
async def list_comments(
    user: CurrentUser = Depends(require_capability("moderate_comments")),
    status: str | None = Query(None, description="approved | pending | spam | trash"),
    post_id: int | None = Query(None, description="Filter by post"),
    search: str | None = Query(None, description="Search in content, author name, email"),
    orderby: str = Query("date", description="date | author"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    List comments with status filtering and counts.
    WordPress equivalent: edit-comments.php

    Returns a `counts` dict with per-status totals so the admin UI
    can render tabs like "All (9) | Pending (1) | Approved (6) | Spam (1) | Trash (1)".
    """
    comments = list(_COMMENTS.values())

    if status:
        comments = [c for c in comments if c["status"] == status]
    else:
        # By default, exclude trashed comments
        comments = [c for c in comments if c["status"] != "trash"]

    if post_id:
        comments = [c for c in comments if c["post_id"] == post_id]

    if search:
        term = search.lower()
        comments = [c for c in comments if (
            term in c["content"].lower() or
            term in c["author_name"].lower() or
            term in c["author_email"].lower()
        )]

    sort_map = {"date": "created_at", "author": "author_name"}
    sort_key = sort_map.get(orderby, "created_at")
    comments.sort(key=lambda c: c.get(sort_key, ""), reverse=(order.lower() == "desc"))

    total = len(comments)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    comments = comments[start : start + per_page]

    return CommentListResponse(
        items=[_to_comment_response(c) for c in comments],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
        counts=_get_status_counts(),
    )


@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(
    comment_id: int,
    user: CurrentUser = Depends(require_capability("moderate_comments")),
):
    """Get a single comment."""
    comment = _COMMENTS.get(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")
    return _to_comment_response(comment)


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CreateCommentRequest,
    user: CurrentUser = Depends(require_capability("moderate_comments")),
):
    """
    Create a comment (admin reply). WordPress equivalent: wp_insert_comment().
    When an admin replies, the comment is auto-approved and tagged with their user_id.
    """
    global _NEXT_COMMENT_ID

    if body.post_id not in _POST_TITLES:
        raise HTTPException(status_code=404, detail="Post not found.")

    if body.parent_id and body.parent_id not in _COMMENTS:
        raise HTTPException(status_code=404, detail="Parent comment not found.")

    comment_id = _NEXT_COMMENT_ID
    _NEXT_COMMENT_ID += 1

    comment = {
        "id": comment_id,
        "post_id": body.post_id,
        "content": body.content,
        "author_name": body.author_name or "Administrator",
        "author_email": body.author_email or "",
        "author_url": body.author_url,
        "author_ip": "",
        "status": "approved",  # Admin replies are auto-approved
        "parent_id": body.parent_id,
        "user_id": user.id,
        "created_at": _now(),
    }
    _COMMENTS[comment_id] = comment

    return _to_comment_response(comment)


@router.patch("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    body: UpdateCommentRequest,
    user: CurrentUser = Depends(require_capability("moderate_comments")),
):
    """Update a comment's content or moderation status."""
    comment = _COMMENTS.get(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    for key, value in body.model_dump(exclude_unset=True).items():
        comment[key] = value

    return _to_comment_response(comment)


@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: int,
    user: CurrentUser = Depends(require_capability("moderate_comments")),
):
    """Permanently delete a comment. WordPress equivalent: wp_delete_comment(force=true)."""
    if comment_id not in _COMMENTS:
        raise HTTPException(status_code=404, detail="Comment not found.")

    del _COMMENTS[comment_id]
    return {"message": "Comment deleted.", "id": comment_id}


@router.post("/bulk")
async def bulk_comment_action(
    body: BulkCommentAction,
    user: CurrentUser = Depends(require_capability("moderate_comments")),
):
    """
    Bulk moderation: approve, spam, trash, or delete multiple comments.
    WordPress equivalent: The bulk actions dropdown on edit-comments.php.
    """
    affected = 0
    for comment_id in body.ids:
        comment = _COMMENTS.get(comment_id)
        if not comment:
            continue

        if body.action in ("approve", "spam", "trash"):
            comment["status"] = "approved" if body.action == "approve" else body.action
            affected += 1
        elif body.action == "delete":
            del _COMMENTS[comment_id]
            affected += 1

    return {"message": f"Bulk {body.action}: {affected} comment(s) affected.", "affected": affected}
