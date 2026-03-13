"""Media and Menu models — media attachments and navigation menus."""
from __future__ import annotations
from sqlalchemy import Integer, String, Text, ForeignKey, Index, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base
from backend.core.models.base import TimestampMixin


class Media(Base, TimestampMixin):
    __tablename__ = "pp_media"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_posts.id", ondelete="CASCADE"), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sizes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alt_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    __table_args__ = (Index("idx_media_mime", "mime_type"),)


class Menu(Base, TimestampMixin):
    __tablename__ = "pp_menus"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    items: Mapped[list["MenuItem"]] = relationship("MenuItem", back_populates="menu", cascade="all, delete-orphan", order_by="MenuItem.position")


class MenuItem(Base):
    __tablename__ = "pp_menu_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    menu_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_menus.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pp_menu_items.id", ondelete="SET NULL"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, default="custom")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    css_classes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    open_in_new_tab: Mapped[bool] = mapped_column(Boolean, default=False)
    menu: Mapped["Menu"] = relationship("Menu", back_populates="items")
    parent: Mapped["MenuItem | None"] = relationship("MenuItem", remote_side=[id], lazy="selectin")
    __table_args__ = (Index("idx_menuitem_menu_pos", "menu_id", "position"),)
