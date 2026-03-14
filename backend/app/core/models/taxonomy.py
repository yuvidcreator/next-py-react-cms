"""
Taxonomy Model — wp_terms + wp_term_taxonomy + wp_term_relationships.
Three-table polymorphic design for categories, tags, and custom taxonomies.
"""
from __future__ import annotations
from backend.app.core.models.post import Post
from sqlalchemy import Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.models.base import SlugMixin


class Term(Base, SlugMixin):
    __tablename__ = "pp_terms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    term_group: Mapped[int] = mapped_column(Integer, default=0)
    taxonomies: Mapped[list["TermTaxonomy"]] = relationship("TermTaxonomy", back_populates="term", cascade="all, delete-orphan")


class TermTaxonomy(Base):
    __tablename__ = "pp_term_taxonomy"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_terms.id", ondelete="CASCADE"), nullable=False)
    taxonomy: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pp_term_taxonomy.id", ondelete="SET NULL"), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    term: Mapped["Term"] = relationship("Term", back_populates="taxonomies")
    parent: Mapped["TermTaxonomy | None"] = relationship("TermTaxonomy", remote_side=[id], lazy="selectin")
    relationships: Mapped[list["TermRelationship"]] = relationship("TermRelationship", back_populates="term_taxonomy", cascade="all, delete-orphan")
    __table_args__ = (Index("idx_taxonomy_term", "taxonomy", "term_id", unique=True),)


class TermRelationship(Base):
    __tablename__ = "pp_term_relationships"
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_posts.id", ondelete="CASCADE"), primary_key=True)
    term_taxonomy_id: Mapped[int] = mapped_column(Integer, ForeignKey("pp_term_taxonomy.id", ondelete="CASCADE"), primary_key=True)
    term_order: Mapped[int] = mapped_column(Integer, default=0)
    post: Mapped["Post"] = relationship("Post", back_populates="term_relationships")
    term_taxonomy: Mapped["TermTaxonomy"] = relationship("TermTaxonomy", back_populates="relationships")
