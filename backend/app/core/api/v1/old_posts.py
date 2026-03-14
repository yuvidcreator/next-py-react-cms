"""Posts REST API — /api/v1/posts — equivalent to /wp-json/wp/v2/posts."""
from __future__ import annotations
import re
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db_session
from backend.app.core.models.post import Post
from backend.app.core.repositories.post_repo import PostRepository
from backend.app.core.hooks import hooks, CoreHooks
from backend.app.core.auth.dependencies import get_current_user, get_current_user_optional, validate_csrf, CurrentUser
from backend.app.core.api.schemas.post_schemas import (
    CreatePostRequest, UpdatePostRequest, PostResponse, PostListResponse,
    PostMetaResponse, AuthorEmbedded,
)

router = APIRouter(prefix="/posts", tags=["posts"])


def _post_to_response(post: Post) -> PostResponse:
    author_data = None
    if post.author:
        author_data = AuthorEmbedded(id=post.author.id, username=post.author.username,
                                      display_name=post.author.display_name or post.author.username)
    meta_list = [PostMetaResponse(key=m.meta_key, value=m.meta_value)
                 for m in (post.meta or []) if not m.meta_key.startswith("_")]
    return PostResponse(
        id=post.id, title=post.title, slug=post.slug, content=post.content,
        excerpt=post.excerpt, status=post.status, post_type=post.post_type,
        author=author_data, parent_id=post.parent_id, comment_status=post.comment_status,
        comment_count=post.comment_count, menu_order=post.menu_order, guid=post.guid,
        meta=meta_list, created_at=post.created_at, updated_at=post.updated_at,
    )


@router.get("", response_model=PostListResponse)
async def list_posts(
    page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(None), status: str = Query("publish"),
    post_type: str = Query("post"), author: int | None = Query(None),
    orderby: str = Query("date"), order: str = Query("desc"),
    db: AsyncSession = Depends(get_db_session),
):
    repo = PostRepository(db)
    query_args = {"post_type": post_type, "post_status": status, "posts_per_page": per_page,
                  "paged": page, "orderby": orderby, "order": order.upper()}
    if search: query_args["search"] = search
    if author: query_args["author"] = author
    result = await repo.query(query_args)
    posts_response = []
    for post in result["posts"]:
        post.content = await hooks.apply_filters(CoreHooks.THE_CONTENT, post.content)
        post.title = await hooks.apply_filters(CoreHooks.THE_TITLE, post.title)
        posts_response.append(_post_to_response(post))
    return PostListResponse(posts=posts_response, total=result["total"],
                            pages=result["pages"], current_page=result["current_page"])


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db_session)):
    repo = PostRepository(db)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.content = await hooks.apply_filters(CoreHooks.THE_CONTENT, post.content)
    post.title = await hooks.apply_filters(CoreHooks.THE_TITLE, post.title)
    return _post_to_response(post)


@router.post("", response_model=PostResponse, status_code=201)
async def create_post(
    body: CreatePostRequest,
    _csrf: None = Depends(validate_csrf),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if not user.can("edit_posts"):
        raise HTTPException(status_code=403, detail="Insufficient capability: edit_posts")
    repo = PostRepository(db)
    slug = body.slug or re.sub(r'[^\w\s-]', '', body.title.lower().strip())[:200].replace(' ', '-')
    post = Post(title=body.title, content=body.content, excerpt=body.excerpt, slug=slug,
                status=body.status, post_type=body.post_type, parent_id=body.parent_id,
                comment_status=body.comment_status, menu_order=body.menu_order, author_id=user.id)
    created = await repo.create_post(post)
    for key, value in body.meta.items():
        await repo.set_meta(created.id, key, value)
    return _post_to_response(created)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int, body: UpdatePostRequest,
    _csrf: None = Depends(validate_csrf),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    repo = PostRepository(db)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if body.title is not None: post.title = body.title
    if body.content is not None: post.content = body.content
    if body.excerpt is not None: post.excerpt = body.excerpt
    if body.slug is not None: post.slug = body.slug
    if body.status is not None:
        old = post.status; post.status = body.status
        if old != body.status:
            await hooks.do_action(CoreHooks.TRANSITION_POST_STATUS, new_status=body.status, old_status=old, post=post)
    updated = await repo.update_post(post)
    if body.meta:
        for k, v in body.meta.items(): await repo.set_meta(updated.id, k, v)
    return _post_to_response(updated)


@router.delete("/{post_id}")
async def delete_post(
    post_id: int, force: bool = Query(False),
    _csrf: None = Depends(validate_csrf),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if not user.can("delete_posts"):
        raise HTTPException(status_code=403, detail="Insufficient capability: delete_posts")
    repo = PostRepository(db)
    if force:
        if not await repo.delete(post_id, hook_name=CoreHooks.DELETE_POST):
            raise HTTPException(status_code=404, detail="Post not found")
        return {"deleted": True, "post_id": post_id}
    post = await repo.trash_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"trashed": True, "post_id": post_id}
