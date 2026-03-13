"""Model Base Mixins — reusable column sets (Composition over Inheritance)."""
from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SlugMixin:
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True, nullable=False)
