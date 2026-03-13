"""User Model — mirrors wp_users + wp_usermeta. Includes OAuth2.0 fields for future social login."""
from __future__ import annotations
from sqlalchemy import Integer, String, Text, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base
from backend.core.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "pp_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    nicename: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    status: Mapped[int] = mapped_column(Integer, default=0)  # 0 = active
    activation_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # ── OAuth2.0 Social Login Fields (Future — Phase 9+) ────
    # When a user signs up via Google/GitHub/Facebook, we store the provider
    # and their unique ID from that provider. The password_hash stays empty
    # for OAuth-only users (they authenticate via the provider, not password).
    oauth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    oauth_provider_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # A user CAN have both a password AND an OAuth link (they signed up with
    # email/password, then later linked their Google account).
    oauth_avatar_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # ── Relationships ────────────────────────────────────────
    meta: Mapped[list["UserMeta"]] = relationship("UserMeta", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", lazy="noload")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="author", lazy="noload")
    sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan", lazy="noload")

    __table_args__ = (Index("idx_user_nicename", "nicename"),
                      Index("idx_user_oauth", "oauth_provider", "oauth_provider_id"))

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"


class UserMeta(Base):
    """User metadata (wp_usermeta) — stores roles, capabilities, preferences."""
    __tablename__ = "pp_usermeta"

    umeta_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_users.id", ondelete="CASCADE"), nullable=False)
    meta_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    meta_value: Mapped[str] = mapped_column(Text, nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="meta")

    __table_args__ = (Index("idx_usermeta_user_key", "user_id", "meta_key"),)


class UserSession(Base):
    """
    Active user sessions — tracks JWT refresh tokens for session management.

    This table lets administrators:
    - See all active sessions for a user
    - Force-logout specific sessions (revoke refresh tokens)
    - Detect session hijacking (IP/user-agent changes)

    WordPress stores sessions in usermeta under 'session_tokens'.
    We use a dedicated table for better querying and cleanup.
    """
    __tablename__ = "pp_user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_users.id", ondelete="CASCADE"), nullable=False)
    # The refresh token hash — we NEVER store raw refresh tokens in the DB.
    # We store a SHA-256 hash and compare incoming tokens against it.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    last_used_at: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (Index("idx_session_user", "user_id", "is_active"),)
