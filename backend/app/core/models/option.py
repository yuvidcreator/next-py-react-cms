"""Option Model — mirrors wp_options (global key-value settings store)."""
from __future__ import annotations
from sqlalchemy import Integer, String, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.core.database import Base


class Option(Base):
    __tablename__ = "pp_options"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(191), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    autoload: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
