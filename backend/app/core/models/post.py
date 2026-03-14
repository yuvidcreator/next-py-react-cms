"""Post Model — mirrors wp_posts + wp_postmeta. Everything is a post (posts, pages, attachments, custom types)."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.models.base import TimestampMixin, SlugMixin


class Post(Base, TimestampMixin, SlugMixin):
    __tablename__ = "pp_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    comment_status: Mapped[str] = mapped_column(String(20), default="open")
    ping_status: Mapped[str] = mapped_column(String(20), default="open")
    post_type: Mapped[str] = mapped_column(String(20), nullable=False, default="post", index=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pp_posts.id", ondelete="SET NULL"), nullable=True)
    menu_order: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_users.id", ondelete="CASCADE"), nullable=False)
    guid: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    publish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[list["PostMeta"]] = relationship("PostMeta", back_populates="post", cascade="all, delete-orphan", lazy="selectin")
    author: Mapped["User"] = relationship("User", back_populates="posts", lazy="selectin")
    parent: Mapped["Post | None"] = relationship("Post", remote_side=[id], lazy="selectin")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="post", cascade="all, delete-orphan", lazy="noload")
    term_relationships: Mapped[list["TermRelationship"]] = relationship("TermRelationship", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_post_type_status", "post_type", "status"),
        Index("idx_author_id", "author_id"),
        Index("idx_post_type_date", "post_type", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, type='{self.post_type}', title='{self.title[:50]}')>"


class PostMeta(Base):
    """EAV pattern — arbitrary key-value metadata on posts (wp_postmeta)."""
    __tablename__ = "pp_postmeta"

    meta_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_posts.id", ondelete="CASCADE"), nullable=False)
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meta_value: Mapped[str] = mapped_column(Text, nullable=True)
    post: Mapped["Post"] = relationship("Post", back_populates="meta")

    __table_args__ = (Index("idx_postmeta_post_key", "post_id", "meta_key"),)
