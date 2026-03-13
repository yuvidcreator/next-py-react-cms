"""Post Repository — WP_Query equivalent with full filtering, search, pagination."""
from __future__ import annotations
from typing import Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.core.models.post import Post, PostMeta
from backend.core.models.taxonomy import TermRelationship, TermTaxonomy, Term
from backend.core.repositories.base import BaseRepository
from backend.core.hooks import hooks, CoreHooks


class PostRepository(BaseRepository[Post]):
    model = Post

    async def get_by_slug(self, slug: str, post_type: str = "post") -> Post | None:
        stmt = (select(Post).where(Post.slug == slug, Post.post_type == post_type)
                .options(selectinload(Post.meta), selectinload(Post.author)))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def query(self, args: dict[str, Any]) -> dict[str, Any]:
        """WP_Query equivalent — fires pre_get_posts and found_posts filters."""
        args = await hooks.apply_filters(CoreHooks.PRE_GET_POSTS, args)
        posts_per_page = args.get("posts_per_page", 10)
        paged = max(1, args.get("paged", 1))
        offset = (paged - 1) * posts_per_page

        stmt = select(Post).options(selectinload(Post.meta), selectinload(Post.author))
        conditions = []

        post_type = args.get("post_type", "post")
        conditions.append(Post.post_type.in_(post_type) if isinstance(post_type, list) else Post.post_type == post_type)
        post_status = args.get("post_status", "publish")
        conditions.append(Post.status.in_(post_status) if isinstance(post_status, list) else Post.status == post_status)

        if "author" in args:
            conditions.append(Post.author_id == args["author"])
        if args.get("search"):
            term = f"%{args['search']}%"
            conditions.append(or_(Post.title.ilike(term), Post.content.ilike(term)))

        date_query = args.get("date_query", {})
        if "after" in date_query:
            conditions.append(Post.created_at >= date_query["after"])
        if "before" in date_query:
            conditions.append(Post.created_at <= date_query["before"])

        if conditions:
            stmt = stmt.where(and_(*conditions))

        orderby = args.get("orderby", "date")
        order = args.get("order", "DESC").upper()
        col_map = {"date": Post.created_at, "title": Post.title, "modified": Post.updated_at,
                    "comment_count": Post.comment_count, "id": Post.id}
        order_col = col_map.get(orderby, Post.created_at)
        stmt = stmt.order_by(order_col.desc() if order == "DESC" else order_col.asc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        total = await hooks.apply_filters(CoreHooks.FOUND_POSTS, total, args)

        stmt = stmt.offset(offset).limit(posts_per_page)
        result = await self._session.execute(stmt)
        posts = list(result.scalars().unique().all())
        return {"posts": posts, "total": total, "pages": max(1, -(-total // posts_per_page)), "current_page": paged}

    async def get_meta(self, post_id: int, key: str) -> str | None:
        stmt = select(PostMeta.meta_value).where(PostMeta.post_id == post_id, PostMeta.meta_key == key).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def set_meta(self, post_id: int, key: str, value: str) -> PostMeta:
        stmt = select(PostMeta).where(PostMeta.post_id == post_id, PostMeta.meta_key == key)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.meta_value = value
            return existing
        meta = PostMeta(post_id=post_id, meta_key=key, meta_value=value)
        self._session.add(meta)
        await self._session.flush()
        return meta

    async def create_post(self, post: Post) -> Post:
        await hooks.do_action(CoreHooks.BEFORE_SAVE_POST, post=post)
        created = await self.create(post, hook_name=CoreHooks.SAVE_POST)
        await hooks.do_action(CoreHooks.AFTER_SAVE_POST, post=created)
        return created

    async def update_post(self, post: Post) -> Post:
        await hooks.do_action(CoreHooks.BEFORE_SAVE_POST, post=post)
        updated = await self.update(post, hook_name=CoreHooks.SAVE_POST)
        await hooks.do_action(CoreHooks.AFTER_SAVE_POST, post=updated)
        return updated

    async def trash_post(self, post_id: int) -> Post | None:
        post = await self.get_by_id(post_id)
        if not post:
            return None
        old_status = post.status
        post.status = "trash"
        await self.set_meta(post_id, "_wp_trash_meta_status", old_status)
        await hooks.do_action(CoreHooks.TRANSITION_POST_STATUS, new_status="trash", old_status=old_status, post=post)
        return await self.update_post(post)
