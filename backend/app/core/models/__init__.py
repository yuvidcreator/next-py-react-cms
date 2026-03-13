"""
PyPress Core Models — SQLAlchemy ORM Definitions

WordPress equivalent: The wp_* table definitions that WordPress creates
via dbDelta() in wp-admin/includes/schema.php.

All models use the pp_ table prefix (like WordPress's wp_ prefix).

IMPORTANT FOR ALEMBIC: Every model class must be imported here (directly
or transitively) so that Alembic's autogenerate can detect schema changes.

When merging Phase 1 code, import all model classes here:
    from app.core.models.post import Post, PostMeta
    from app.core.models.user import User, UserMeta, UserSession
    from app.core.models.taxonomy import Term, TermTaxonomy, TermRelationship
    from app.core.models.comment import Comment
    from app.core.models.option import Option
    from app.core.models.media import Media
    from app.core.models.menu import Menu, MenuItem
"""
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.models.post import Post, PostMeta
from backend.app.core.models.user import User, UserMeta, UserSession
from backend.app.core.models.taxonomy import Term, TermTaxonomy, TermRelationship
from backend.app.core.models.comment import Comment, CommentMeta
from backend.app.core.models.option import Option
from backend.app.core.models.media import Media, Menu, MenuItem

__all__ = [
    "Post", "PostMeta", "User", "UserMeta", "UserSession",
    "Term", "TermTaxonomy", "TermRelationship",
    "Comment", "CommentMeta", "Option", "Media", "Menu", "MenuItem",
]


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base — all PyPress models inherit from this.

    WordPress equivalent: The base table creation logic in wp-admin/includes/schema.php
    that all wp_* tables share (charset, collation, engine settings).
    """
    pass