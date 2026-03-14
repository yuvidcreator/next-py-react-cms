"""
PyPress — Media REST API Router

WordPress equivalent: upload.php + wp-admin/async-upload.php

Endpoints:
    GET    /api/v1/media           — List media (filterable by type, paginated)
    GET    /api/v1/media/:id       — Get single media item
    POST   /api/v1/media           — Upload new file(s)
    PATCH  /api/v1/media/:id       — Update metadata (alt text, caption, title)
    DELETE /api/v1/media/:id       — Delete media file
    POST   /api/v1/media/bulk-delete — Delete multiple media items

WordPress equivalent: wp_handle_upload() + wp_insert_attachment() +
wp_generate_attachment_metadata()
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth.dependencies import CurrentUser, get_current_user, require_capability
from app.core.api.schemas.media_schemas import (
    UpdateMediaRequest, MediaResponse, MediaListResponse, MediaSizes,
)

router = APIRouter(prefix="/media", tags=["Media"])


# =============================================================================
# IN-MEMORY MEDIA STORE (Replace with filesystem + pp_posts attachment type)
# =============================================================================
_NEXT_MEDIA_ID = 5

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

_MEDIA: dict[int, dict] = {
    1: {
        "id": 1, "title": "PyPress Logo", "filename": "pypress-logo.png",
        "url": "/uploads/2026/03/pypress-logo.png", "mime_type": "image/png",
        "file_size": 45_200, "alt_text": "PyPress CMS Logo", "caption": "",
        "description": "The official PyPress brand logo.", "width": 512, "height": 512,
        "uploaded_by_id": 1, "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-03-01T00:00:00Z",
    },
    2: {
        "id": 2, "title": "Getting Started Header", "filename": "getting-started-header.jpg",
        "url": "/uploads/2026/03/getting-started-header.jpg", "mime_type": "image/jpeg",
        "file_size": 128_400, "alt_text": "Getting started with PyPress", "caption": "Welcome to PyPress",
        "description": "", "width": 1200, "height": 630,
        "uploaded_by_id": 1, "created_at": "2026-03-10T10:00:00Z", "updated_at": "2026-03-10T10:00:00Z",
    },
    3: {
        "id": 3, "title": "Plugin Architecture Diagram", "filename": "plugin-architecture.svg",
        "url": "/uploads/2026/03/plugin-architecture.svg", "mime_type": "image/svg+xml",
        "file_size": 8_100, "alt_text": "Plugin system architecture", "caption": "",
        "description": "Shows how plugins hook into the core system.", "width": 800, "height": 600,
        "uploaded_by_id": 1, "created_at": "2026-03-11T14:00:00Z", "updated_at": "2026-03-11T14:00:00Z",
    },
    4: {
        "id": 4, "title": "Project README", "filename": "README.pdf",
        "url": "/uploads/2026/03/README.pdf", "mime_type": "application/pdf",
        "file_size": 52_300, "alt_text": "", "caption": "",
        "description": "Project documentation in PDF format.", "width": None, "height": None,
        "uploaded_by_id": 1, "created_at": "2026-03-12T09:00:00Z", "updated_at": "2026-03-12T09:00:00Z",
    },
}

_AUTHORS = {1: {"id": 1, "display_name": "Administrator"}}


def _to_media_response(m: dict) -> MediaResponse:
    author = _AUTHORS.get(m["uploaded_by_id"], {"id": 0, "display_name": "Unknown"})
    base_url = m["url"]

    # Generate thumbnail URLs (simulated — Phase 1 will use Pillow for real resizing)
    sizes = MediaSizes(full=base_url)
    if m["mime_type"].startswith("image/") and m["mime_type"] != "image/svg+xml":
        name_parts = m["filename"].rsplit(".", 1)
        base = name_parts[0]
        ext = name_parts[1] if len(name_parts) > 1 else "jpg"
        dir_path = "/".join(base_url.split("/")[:-1])
        sizes.thumbnail = f"{dir_path}/{base}-150x150.{ext}"
        sizes.medium = f"{dir_path}/{base}-300x300.{ext}"
        sizes.large = f"{dir_path}/{base}-1024x1024.{ext}"

    return MediaResponse(
        id=m["id"], title=m["title"], filename=m["filename"],
        url=m["url"], mime_type=m["mime_type"], file_size=m["file_size"],
        alt_text=m.get("alt_text", ""), caption=m.get("caption", ""),
        description=m.get("description", ""),
        width=m.get("width"), height=m.get("height"),
        sizes=sizes, uploaded_by=author,
        created_at=m["created_at"], updated_at=m["updated_at"],
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=MediaListResponse)
async def list_media(
    user: CurrentUser = Depends(require_capability("upload_files")),
    mime_type: str | None = Query(None, description="Filter: image | video | audio | application | exact MIME"),
    search: str | None = Query(None, description="Search in title and filename"),
    orderby: str = Query("date", description="date | title | size"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(40, ge=1, le=100),
):
    """
    List media items with filtering and pagination.
    WordPress equivalent: wp.media.query() in the media library JS.
    """
    items = list(_MEDIA.values())

    if mime_type:
        if "/" in mime_type:
            items = [m for m in items if m["mime_type"] == mime_type]
        else:
            items = [m for m in items if m["mime_type"].startswith(mime_type + "/")]

    if search:
        term = search.lower()
        items = [m for m in items if term in m["title"].lower() or term in m["filename"].lower()]

    sort_map = {"date": "created_at", "title": "title", "size": "file_size"}
    sort_key = sort_map.get(orderby, "created_at")
    items.sort(key=lambda m: m.get(sort_key, ""), reverse=(order.lower() == "desc"))

    total = len(items)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    items = items[start : start + per_page]

    return MediaListResponse(
        items=[_to_media_response(m) for m in items],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
    )


@router.get("/{media_id}", response_model=MediaResponse)
async def get_media(
    media_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single media item. WordPress equivalent: wp_get_attachment_metadata()."""
    media = _MEDIA.get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    return _to_media_response(media)


@router.post("", response_model=MediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    user: CurrentUser = Depends(require_capability("upload_files")),
    title: str = Query("Untitled"),
    alt_text: str = Query(""),
    caption: str = Query(""),
):
    """
    Upload a media file. WordPress equivalent: wp_handle_upload() + wp_insert_attachment().

    NOTE: In this demo version, the actual file upload is simulated.
    Phase 1 merge will add real multipart form handling with:
      - File type validation (MIME checking with python-magic)
      - Image resizing with Pillow (generate thumbnail, medium, large sizes)
      - Storage to /app/uploads volume (or S3 via plugin)
      - Metadata extraction (EXIF for images, duration for video/audio)

    To test with real uploads, replace this endpoint with:
      async def upload_media(file: UploadFile = File(...), ...)
    """
    global _NEXT_MEDIA_ID

    media_id = _NEXT_MEDIA_ID
    _NEXT_MEDIA_ID += 1
    now = _now()

    media = {
        "id": media_id,
        "title": title or "Untitled",
        "filename": f"upload-{media_id}.jpg",
        "url": f"/uploads/2026/03/upload-{media_id}.jpg",
        "mime_type": "image/jpeg",
        "file_size": 0,
        "alt_text": alt_text,
        "caption": caption,
        "description": "",
        "width": None,
        "height": None,
        "uploaded_by_id": user.id,
        "created_at": now,
        "updated_at": now,
    }
    _MEDIA[media_id] = media

    return _to_media_response(media)


@router.patch("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_id: int,
    body: UpdateMediaRequest,
    user: CurrentUser = Depends(require_capability("upload_files")),
):
    """Update media metadata. WordPress equivalent: wp_update_post() for attachments."""
    media = _MEDIA.get(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")

    for key, value in body.model_dump(exclude_unset=True).items():
        media[key] = value
    media["updated_at"] = _now()

    return _to_media_response(media)


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    user: CurrentUser = Depends(require_capability("upload_files")),
):
    """
    Delete a media item. WordPress equivalent: wp_delete_attachment().
    In production, this also deletes the file from the filesystem/S3.
    """
    if media_id not in _MEDIA:
        raise HTTPException(status_code=404, detail="Media not found.")

    filename = _MEDIA[media_id]["filename"]
    del _MEDIA[media_id]

    return {"message": f"Media '{filename}' deleted.", "id": media_id}


@router.post("/bulk-delete")
async def bulk_delete_media(
    ids: list[int],
    user: CurrentUser = Depends(require_capability("upload_files")),
):
    """Delete multiple media items at once."""
    deleted = 0
    for media_id in ids:
        if media_id in _MEDIA:
            del _MEDIA[media_id]
            deleted += 1
    return {"message": f"{deleted} media item(s) deleted.", "deleted": deleted}
