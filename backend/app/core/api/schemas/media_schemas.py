"""
PyPress — Media API Schemas

WordPress stores media as attachment posts in wp_posts with metadata
in wp_postmeta (file path, dimensions, sizes). PyPress mirrors this
approach with a dedicated Media type for cleaner API contracts.

    UploadMediaResponse → POST /api/v1/media (after file upload)
    UpdateMediaRequest  → PATCH /api/v1/media/:id (edit alt text, caption)
    MediaResponse       → Full media item with sizes and usage info
    MediaListResponse   → Paginated grid for the Media Library page
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class MediaSizes(BaseModel):
    """Image thumbnail URLs at different sizes (like WordPress's registered image sizes)."""
    thumbnail: str | None = None
    medium: str | None = None
    large: str | None = None
    full: str


class UpdateMediaRequest(BaseModel):
    """PATCH /api/v1/media/:id — edit metadata without re-uploading the file."""
    title: str | None = None
    alt_text: str | None = None
    caption: str | None = None
    description: str | None = None


class MediaResponse(BaseModel):
    """Full media item response."""
    id: int
    title: str
    filename: str
    url: str
    mime_type: str
    file_size: int
    alt_text: str = ""
    caption: str = ""
    description: str = ""
    width: int | None = None
    height: int | None = None
    sizes: MediaSizes
    uploaded_by: dict  # {id, display_name}
    created_at: str
    updated_at: str


class MediaListResponse(BaseModel):
    """Paginated media list for the Media Library page."""
    items: list[MediaResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
