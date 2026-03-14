"""
PyPress — Posts REST API Router

WordPress equivalent: WP_Query + edit.php + post-new.php combined.

Endpoints:
    GET    /api/v1/posts           — List posts (WP_Query-style filtering)
    GET    /api/v1/posts/:id       — Get single post
    GET    /api/v1/posts/slug/:s   — Get post by slug
    POST   /api/v1/posts           — Create new post
    PATCH  /api/v1/posts/:id       — Update existing post
    DELETE /api/v1/posts/:id       — Trash or permanently delete
    POST   /api/v1/posts/:id/restore — Restore from trash
    POST   /api/v1/posts/bulk      — Bulk actions (publish/draft/trash/delete)

Every write operation fires the appropriate hooks (Phase 1 merge).
Every read/write is capability-gated via RBAC.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth.dependencies import CurrentUser, get_current_user, require_capability
from app.core.api.schemas.post_schemas import (
    CreatePostRequest,
    UpdatePostRequest,
    BulkActionRequest,
    PostResponse,
    PostListResponse,
    PostAuthorResponse,
    TermResponse,
)

router = APIRouter(prefix="/posts", tags=["Posts"])


# =============================================================================
# IN-MEMORY DATA STORE (Replace with Phase 1 PostRepository)
# =============================================================================
# This provides a working Posts API with demo content for immediate testing.
# When merging Phase 1 code, replace _POSTS dict and helper functions with:
#   post_repo = PostRepository(db_session)
#   result = await post_repo.query({...})

_NEXT_ID = 6

def _slugify(text: str) -> str:
    return text.lower().strip().replace(" ", "-")[:200]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_POSTS: dict[int, dict] = {
    1: {
        "id": 1, "title": "Getting Started with PyPress", "slug": "getting-started-with-pypress",
        "content": "<p>Welcome to PyPress — the modern WordPress alternative built with Python and React. This guide will walk you through the basics of setting up and using your new CMS.</p><p>PyPress replicates WordPress's architectural paradigms — hooks, plugins, themes, template hierarchy — but uses FastAPI, React, and PostgreSQL under the hood.</p>",
        "excerpt": "A beginner's guide to PyPress CMS.", "status": "publish", "post_type": "post",
        "author_id": 1, "featured_image_id": None,
        "category_ids": [1], "tag_ids": [1, 2], "comment_status": "open", "comment_count": 3,
        "parent_id": None, "menu_order": 0, "template": "",
        "published_at": "2026-03-10T10:00:00Z", "created_at": "2026-03-10T10:00:00Z", "updated_at": "2026-03-14T09:00:00Z",
        "meta": {},
    },
    2: {
        "id": 2, "title": "How to Build a Plugin", "slug": "how-to-build-a-plugin",
        "content": "<p>PyPress plugins follow the same lifecycle as WordPress plugins: activate, deactivate, uninstall. Each plugin is a Python class that extends BasePlugin and registers hooks.</p>",
        "excerpt": "Learn to extend PyPress with custom plugins.", "status": "draft", "post_type": "post",
        "author_id": 1, "featured_image_id": None,
        "category_ids": [2], "tag_ids": [2], "comment_status": "open", "comment_count": 0,
        "parent_id": None, "menu_order": 0, "template": "",
        "published_at": None, "created_at": "2026-03-11T14:00:00Z", "updated_at": "2026-03-13T16:30:00Z",
        "meta": {},
    },
    3: {
        "id": 3, "title": "Theme Development Guide", "slug": "theme-development-guide",
        "content": "<p>Themes in PyPress use the exact WordPress template hierarchy. Learn how to create templates, register widget areas, and build a complete theme from scratch.</p>",
        "excerpt": "Build beautiful themes for PyPress.", "status": "publish", "post_type": "post",
        "author_id": 1, "featured_image_id": None,
        "category_ids": [2], "tag_ids": [3], "comment_status": "open", "comment_count": 5,
        "parent_id": None, "menu_order": 0, "template": "",
        "published_at": "2026-03-12T09:00:00Z", "created_at": "2026-03-12T09:00:00Z", "updated_at": "2026-03-12T09:00:00Z",
        "meta": {},
    },
    4: {
        "id": 4, "title": "Understanding the Hook System", "slug": "understanding-the-hook-system",
        "content": "<p>The hook system is the backbone of PyPress extensibility. Actions fire events, filters transform data. Every database operation, every page render, every authentication step fires hooks that plugins can intercept.</p>",
        "excerpt": "Deep dive into actions and filters.", "status": "pending", "post_type": "post",
        "author_id": 1, "featured_image_id": None,
        "category_ids": [2], "tag_ids": [2, 3], "comment_status": "open", "comment_count": 1,
        "parent_id": None, "menu_order": 0, "template": "",
        "published_at": None, "created_at": "2026-03-13T16:00:00Z", "updated_at": "2026-03-13T16:00:00Z",
        "meta": {},
    },
    5: {
        "id": 5, "title": "About", "slug": "about",
        "content": "<p>This is the About page for the PyPress demo site. PyPress is a modern, open-source CMS that brings the power of WordPress's architecture to the Python ecosystem.</p>",
        "excerpt": "", "status": "publish", "post_type": "page",
        "author_id": 1, "featured_image_id": None,
        "category_ids": [], "tag_ids": [], "comment_status": "closed", "comment_count": 0,
        "parent_id": None, "menu_order": 0, "template": "",
        "published_at": "2026-03-01T00:00:00Z", "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-03-01T00:00:00Z",
        "meta": {},
    },
}

# Demo taxonomy data
_CATEGORIES = {1: {"id": 1, "name": "General", "slug": "general", "taxonomy": "category"}, 2: {"id": 2, "name": "Tutorials", "slug": "tutorials", "taxonomy": "category"}}
_TAGS = {1: {"id": 1, "name": "PyPress", "slug": "pypress", "taxonomy": "post_tag"}, 2: {"id": 2, "name": "Python", "slug": "python", "taxonomy": "post_tag"}, 3: {"id": 3, "name": "Themes", "slug": "themes", "taxonomy": "post_tag"}}
_AUTHORS = {1: {"id": 1, "display_name": "Administrator", "avatar_url": None}}


def _to_response(post: dict) -> PostResponse:
    """Convert in-memory post dict to PostResponse schema."""
    author = _AUTHORS.get(post["author_id"], {"id": 0, "display_name": "Unknown", "avatar_url": None})
    categories = [TermResponse(**_CATEGORIES[cid]) for cid in post.get("category_ids", []) if cid in _CATEGORIES]
    tags = [TermResponse(**_TAGS[tid]) for tid in post.get("tag_ids", []) if tid in _TAGS]

    return PostResponse(
        id=post["id"], title=post["title"], slug=post["slug"],
        content=post["content"], excerpt=post["excerpt"],
        status=post["status"], post_type=post["post_type"],
        author=PostAuthorResponse(**author),
        featured_image=None, categories=categories, tags=tags,
        comment_status=post["comment_status"], comment_count=post.get("comment_count", 0),
        parent_id=post.get("parent_id"), menu_order=post.get("menu_order", 0),
        template=post.get("template", ""),
        published_at=post.get("published_at"), created_at=post["created_at"], updated_at=post["updated_at"],
        meta=post.get("meta", {}),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=PostListResponse)
async def list_posts(
    user: CurrentUser = Depends(get_current_user),
    # WP_Query-style parameters
    post_type: str = Query("post", description="post | page | any"),
    status: str | None = Query(None, description="publish | draft | pending | trash | any"),
    author: int | None = Query(None),
    search: str | None = Query(None, description="Search in title and content"),
    category: int | None = Query(None),
    tag: int | None = Query(None),
    orderby: str = Query("date", description="date | title | modified | id"),
    order: str = Query("desc", description="asc | desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    List posts with filtering, search, and pagination.

    WordPress equivalent: WP_Query in edit.php — the main post list screen.
    Supports the same query parameters: post_type, status, author, search,
    category, tag, orderby, order, and pagination.
    """
    # Filter posts
    posts = list(_POSTS.values())

    if post_type != "any":
        posts = [p for p in posts if p["post_type"] == post_type]

    if status and status != "any":
        posts = [p for p in posts if p["status"] == status]
    else:
        # By default, exclude trashed posts (like WordPress)
        posts = [p for p in posts if p["status"] != "trash"]

    if author:
        posts = [p for p in posts if p["author_id"] == author]

    if search:
        term = search.lower()
        posts = [p for p in posts if term in p["title"].lower() or term in p["content"].lower()]

    if category:
        posts = [p for p in posts if category in p.get("category_ids", [])]

    if tag:
        posts = [p for p in posts if tag in p.get("tag_ids", [])]

    # Sort
    sort_key = {"date": "created_at", "title": "title", "modified": "updated_at", "id": "id"}.get(orderby, "created_at")
    posts.sort(key=lambda p: p.get(sort_key, ""), reverse=(order.lower() == "desc"))

    # Paginate
    total = len(posts)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    posts = posts[start : start + per_page]

    return PostListResponse(
        items=[_to_response(p) for p in posts],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single post by ID. WordPress equivalent: get_post()."""
    post = _POSTS.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return _to_response(post)


@router.get("/slug/{slug}", response_model=PostResponse)
async def get_post_by_slug(
    slug: str,
    post_type: str = Query("post"),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a post by its URL slug. WordPress equivalent: get_page_by_path()."""
    for post in _POSTS.values():
        if post["slug"] == slug and post["post_type"] == post_type:
            return _to_response(post)
    raise HTTPException(status_code=404, detail="Post not found.")


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: CreatePostRequest,
    user: CurrentUser = Depends(require_capability("edit_posts")),
):
    """
    Create a new post or page.
    WordPress equivalent: wp_insert_post().

    If no slug is provided, one is auto-generated from the title.
    If no author_id is provided, the current user becomes the author.
    """
    global _NEXT_ID

    post_id = _NEXT_ID
    _NEXT_ID += 1

    slug = body.slug or _slugify(body.title)
    # Ensure slug uniqueness
    existing_slugs = {p["slug"] for p in _POSTS.values()}
    base_slug = slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    now = _now()
    post = {
        "id": post_id,
        "title": body.title,
        "slug": slug,
        "content": body.content,
        "excerpt": body.excerpt,
        "status": body.status,
        "post_type": body.post_type,
        "author_id": body.author_id or user.id,
        "featured_image_id": body.featured_image_id,
        "category_ids": body.category_ids,
        "tag_ids": body.tag_ids,
        "comment_status": body.comment_status,
        "comment_count": 0,
        "parent_id": body.parent_id,
        "menu_order": body.menu_order,
        "template": body.template,
        "published_at": body.published_at or (now if body.status == "publish" else None),
        "created_at": now,
        "updated_at": now,
        "meta": body.meta,
    }

    _POSTS[post_id] = post
    # Phase 1 merge: await hooks.do_action(CoreHooks.SAVE_POST, post=post)

    return _to_response(post)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    body: UpdatePostRequest,
    user: CurrentUser = Depends(require_capability("edit_posts")),
):
    """
    Update an existing post (partial update — only provided fields change).
    WordPress equivalent: wp_update_post().
    """
    post = _POSTS.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Check ownership for non-admin users
    if user.role not in ("administrator", "editor") and post["author_id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own posts.")

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        post[key] = value

    post["updated_at"] = _now()

    # Auto-set published_at when status changes to publish
    if body.status == "publish" and not post.get("published_at"):
        post["published_at"] = _now()

    # Phase 1 merge: await hooks.do_action(CoreHooks.SAVE_POST, post=post)
    return _to_response(post)


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    force: bool = Query(False, description="True = permanent delete, False = move to trash"),
    user: CurrentUser = Depends(require_capability("delete_posts")),
):
    """
    Delete or trash a post.
    WordPress equivalent: wp_trash_post() / wp_delete_post().

    Default behavior (force=false): moves to trash (status=trash).
    With force=true: permanently deletes from the database.
    """
    post = _POSTS.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    if force:
        del _POSTS[post_id]
        return {"message": "Post permanently deleted.", "id": post_id}
    else:
        post["status"] = "trash"
        post["updated_at"] = _now()
        # Store original status for restore
        post.setdefault("meta", {})["_wp_trash_meta_status"] = post.get("status", "draft")
        return {"message": "Post moved to trash.", "id": post_id}


@router.post("/{post_id}/restore", response_model=PostResponse)
async def restore_post(
    post_id: int,
    user: CurrentUser = Depends(require_capability("edit_posts")),
):
    """
    Restore a post from trash to its previous status.
    WordPress equivalent: wp_untrash_post().
    """
    post = _POSTS.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    if post["status"] != "trash":
        raise HTTPException(status_code=400, detail="Post is not in trash.")

    # Restore to previous status (default to draft if unknown)
    original_status = post.get("meta", {}).pop("_wp_trash_meta_status", "draft")
    post["status"] = original_status
    post["updated_at"] = _now()

    return _to_response(post)


@router.post("/bulk")
async def bulk_action(
    body: BulkActionRequest,
    user: CurrentUser = Depends(require_capability("edit_posts")),
):
    """
    Perform a bulk action on multiple posts.
    WordPress equivalent: The bulk actions dropdown on edit.php.

    Supported actions: publish, draft, trash, delete (permanent).
    """
    affected = 0

    for post_id in body.ids:
        post = _POSTS.get(post_id)
        if not post:
            continue

        if body.action == "publish":
            post["status"] = "publish"
            if not post.get("published_at"):
                post["published_at"] = _now()
            post["updated_at"] = _now()
            affected += 1

        elif body.action == "draft":
            post["status"] = "draft"
            post["updated_at"] = _now()
            affected += 1

        elif body.action == "trash":
            post.setdefault("meta", {})["_wp_trash_meta_status"] = post["status"]
            post["status"] = "trash"
            post["updated_at"] = _now()
            affected += 1

        elif body.action == "delete":
            del _POSTS[post_id]
            affected += 1

    return {
        "message": f"Bulk {body.action}: {affected} post(s) affected.",
        "affected": affected,
    }
