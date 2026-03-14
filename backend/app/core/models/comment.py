"""Comment Model — mirrors wp_comments + wp_commentmeta."""
from __future__ import annotations
from sqlalchemy import Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.models.base import TimestampMixin


class Comment(Base, TimestampMixin):
    __tablename__ = "pp_comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pp_users.id", ondelete="SET NULL"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    author_email: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    author_url: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    author_ip: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    comment_type: Mapped[str] = mapped_column(String(20), default="comment")
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pp_comments.id", ondelete="CASCADE"), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    author: Mapped["User | None"] = relationship("User", back_populates="comments")
    parent: Mapped["Comment | None"] = relationship("Comment", remote_side=[id], lazy="selectin")
    meta: Mapped[list["CommentMeta"]] = relationship("CommentMeta", back_populates="comment", cascade="all, delete-orphan")
    __table_args__ = (Index("idx_comment_post", "post_id", "status"),)


class CommentMeta(Base):
    __tablename__ = "pp_commentmeta"
    meta_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_comments.id", ondelete="CASCADE"), nullable=False)
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meta_value: Mapped[str] = mapped_column(Text, nullable=True)
    comment: Mapped["Comment"] = relationship("Comment", back_populates="meta")
