"""
PyPress — Taxonomies REST API Router

Unified endpoint for categories, tags, and custom taxonomies.
WordPress uses the same tables for all — the `taxonomy` URL param discriminates.

Endpoints:
    GET    /api/v1/taxonomies/:taxonomy           — List terms (flat)
    GET    /api/v1/taxonomies/:taxonomy/tree       — Hierarchical tree (categories)
    GET    /api/v1/taxonomies/:taxonomy/:id        — Get single term
    POST   /api/v1/taxonomies/:taxonomy            — Create term
    PATCH  /api/v1/taxonomies/:taxonomy/:id        — Update term
    DELETE /api/v1/taxonomies/:taxonomy/:id        — Delete term
    POST   /api/v1/taxonomies/:taxonomy/merge      — Merge terms (tags)

WordPress equivalent: edit-tags.php, wp_insert_term(), wp_update_term(),
wp_delete_term(), wp_merge_terms()
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth.dependencies import CurrentUser, get_current_user, require_capability
from app.core.api.schemas.taxonomy_schemas import (
    CreateTermRequest, UpdateTermRequest, MergeTermsRequest,
    TermResponse, TermTreeResponse, TermListResponse,
)

router = APIRouter(prefix="/taxonomies", tags=["Taxonomies"])


# =============================================================================
# IN-MEMORY TAXONOMY STORE (Replace with Phase 1 Term + TermTaxonomy models)
# =============================================================================
_NEXT_TERM_ID = 8

def _slugify(text: str) -> str:
    return text.lower().strip().replace(" ", "-")[:200]

_TERMS: dict[int, dict] = {
    # Categories (hierarchical)
    1: {"id": 1, "name": "General", "slug": "general", "taxonomy": "category", "description": "General posts", "parent_id": None, "count": 1},
    2: {"id": 2, "name": "Tutorials", "slug": "tutorials", "taxonomy": "category", "description": "Step-by-step tutorials", "parent_id": None, "count": 3},
    3: {"id": 3, "name": "Python Tutorials", "slug": "python-tutorials", "taxonomy": "category", "description": "Python-specific tutorials", "parent_id": 2, "count": 1},
    4: {"id": 4, "name": "React Tutorials", "slug": "react-tutorials", "taxonomy": "category", "description": "React-specific tutorials", "parent_id": 2, "count": 0},
    # Tags (flat)
    5: {"id": 5, "name": "PyPress", "slug": "pypress", "taxonomy": "post_tag", "description": "", "parent_id": None, "count": 2},
    6: {"id": 6, "name": "Python", "slug": "python", "taxonomy": "post_tag", "description": "", "parent_id": None, "count": 3},
    7: {"id": 7, "name": "Themes", "slug": "themes", "taxonomy": "post_tag", "description": "", "parent_id": None, "count": 1},
}


def _to_term_response(term: dict) -> TermResponse:
    return TermResponse(
        id=term["id"], name=term["name"], slug=term["slug"],
        taxonomy=term["taxonomy"], description=term.get("description", ""),
        parent_id=term.get("parent_id"), count=term.get("count", 0),
    )


def _build_tree(terms: list[dict], parent_id: int | None = None) -> list[TermTreeResponse]:
    """Recursively build a hierarchical tree from flat term list."""
    children = []
    for term in terms:
        if term.get("parent_id") == parent_id:
            node = TermTreeResponse(
                id=term["id"], name=term["name"], slug=term["slug"],
                taxonomy=term["taxonomy"], description=term.get("description", ""),
                parent_id=term.get("parent_id"), count=term.get("count", 0),
                children=_build_tree(terms, parent_id=term["id"]),
            )
            children.append(node)
    return children


def _get_capability_for_taxonomy(taxonomy: str) -> str:
    """Map taxonomy type to required WordPress capability."""
    return "manage_categories" if taxonomy == "category" else "manage_categories"


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{taxonomy}", response_model=TermListResponse)
async def list_terms(
    taxonomy: str,
    user: CurrentUser = Depends(get_current_user),
    search: str | None = Query(None),
    parent_id: int | None = Query(None, description="Filter by parent (categories only)"),
    orderby: str = Query("name", description="name | count | id"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    hide_empty: bool = Query(False, description="Hide terms with count=0"),
):
    """
    List terms for a taxonomy. WordPress equivalent: get_terms().

    Supports filtering by parent (for categories), search, ordering,
    and optional hiding of empty terms.
    """
    terms = [t for t in _TERMS.values() if t["taxonomy"] == taxonomy]

    if search:
        term_lower = search.lower()
        terms = [t for t in terms if term_lower in t["name"].lower()]

    if parent_id is not None:
        terms = [t for t in terms if t.get("parent_id") == parent_id]

    if hide_empty:
        terms = [t for t in terms if t.get("count", 0) > 0]

    # Sort
    sort_map = {"name": "name", "count": "count", "id": "id"}
    sort_key = sort_map.get(orderby, "name")
    terms.sort(key=lambda t: t.get(sort_key, ""), reverse=(order.lower() == "desc"))

    # Paginate
    total = len(terms)
    total_pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    terms = terms[start : start + per_page]

    return TermListResponse(
        items=[_to_term_response(t) for t in terms],
        total=total, page=page, per_page=per_page, total_pages=total_pages,
    )


@router.get("/{taxonomy}/tree", response_model=list[TermTreeResponse])
async def get_term_tree(
    taxonomy: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get terms as a hierarchical tree (for categories).
    WordPress equivalent: wp_list_categories() with hierarchical=true.

    Returns nested structure where each term has a `children` array.
    Only meaningful for hierarchical taxonomies (categories).
    Tags return a flat list (each item has empty children).
    """
    terms = [t for t in _TERMS.values() if t["taxonomy"] == taxonomy]
    return _build_tree(terms, parent_id=None)


@router.get("/{taxonomy}/{term_id}", response_model=TermResponse)
async def get_term(
    taxonomy: str, term_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single term. WordPress equivalent: get_term()."""
    term = _TERMS.get(term_id)
    if not term or term["taxonomy"] != taxonomy:
        raise HTTPException(status_code=404, detail="Term not found.")
    return _to_term_response(term)


@router.post("/{taxonomy}", response_model=TermResponse, status_code=status.HTTP_201_CREATED)
async def create_term(
    taxonomy: str,
    body: CreateTermRequest,
    user: CurrentUser = Depends(require_capability("manage_categories")),
):
    """
    Create a new term. WordPress equivalent: wp_insert_term().

    For categories: parent_id creates hierarchy.
    For tags: parent_id is ignored.
    Slug is auto-generated from name if not provided.
    """
    global _NEXT_TERM_ID

    slug = body.slug or _slugify(body.name)

    # Uniqueness check within taxonomy
    for t in _TERMS.values():
        if t["taxonomy"] == taxonomy and t["slug"] == slug:
            raise HTTPException(status_code=409, detail=f"A term with slug '{slug}' already exists in this taxonomy.")

    # For tags, ignore parent_id
    parent_id = body.parent_id if taxonomy == "category" else None

    # Validate parent exists
    if parent_id and parent_id not in _TERMS:
        raise HTTPException(status_code=400, detail="Parent term not found.")

    term_id = _NEXT_TERM_ID
    _NEXT_TERM_ID += 1

    term = {
        "id": term_id, "name": body.name, "slug": slug,
        "taxonomy": taxonomy, "description": body.description,
        "parent_id": parent_id, "count": 0,
    }
    _TERMS[term_id] = term

    return _to_term_response(term)


@router.patch("/{taxonomy}/{term_id}", response_model=TermResponse)
async def update_term(
    taxonomy: str, term_id: int,
    body: UpdateTermRequest,
    user: CurrentUser = Depends(require_capability("manage_categories")),
):
    """Update a term. WordPress equivalent: wp_update_term()."""
    term = _TERMS.get(term_id)
    if not term or term["taxonomy"] != taxonomy:
        raise HTTPException(status_code=404, detail="Term not found.")

    update_data = body.model_dump(exclude_unset=True)

    # Slug uniqueness check
    if "slug" in update_data:
        for t in _TERMS.values():
            if t["taxonomy"] == taxonomy and t["slug"] == update_data["slug"] and t["id"] != term_id:
                raise HTTPException(status_code=409, detail="Slug already in use.")

    # Prevent circular parent references
    if "parent_id" in update_data and update_data["parent_id"] == term_id:
        raise HTTPException(status_code=400, detail="A term cannot be its own parent.")

    for key, value in update_data.items():
        term[key] = value

    return _to_term_response(term)


@router.delete("/{taxonomy}/{term_id}")
async def delete_term(
    taxonomy: str, term_id: int,
    user: CurrentUser = Depends(require_capability("manage_categories")),
):
    """
    Delete a term. WordPress equivalent: wp_delete_term().

    If the term has children (categories), their parent is set to None
    (promoted to top-level). Post relationships are removed.
    """
    term = _TERMS.get(term_id)
    if not term or term["taxonomy"] != taxonomy:
        raise HTTPException(status_code=404, detail="Term not found.")

    # Promote children to top-level
    for t in _TERMS.values():
        if t.get("parent_id") == term_id:
            t["parent_id"] = None

    # Remove from posts (update post category_ids/tag_ids)
    from app.core.api.v1.posts import _POSTS
    key = "category_ids" if taxonomy == "category" else "tag_ids"
    for post in _POSTS.values():
        if term_id in post.get(key, []):
            post[key].remove(term_id)

    del _TERMS[term_id]
    return {"message": f"Term '{term['name']}' deleted.", "id": term_id}


@router.post("/{taxonomy}/merge")
async def merge_terms(
    taxonomy: str,
    body: MergeTermsRequest,
    user: CurrentUser = Depends(require_capability("manage_categories")),
):
    """
    Merge multiple terms into one. WordPress equivalent: wp_merge_terms().

    All posts tagged with source terms will be re-tagged with the target term.
    Source terms are then deleted. Useful for cleaning up duplicate tags.
    """
    target = _TERMS.get(body.target_id)
    if not target or target["taxonomy"] != taxonomy:
        raise HTTPException(status_code=404, detail="Target term not found.")

    from app.core.api.v1.posts import _POSTS
    key = "category_ids" if taxonomy == "category" else "tag_ids"
    merged_count = 0

    for source_id in body.source_ids:
        source = _TERMS.get(source_id)
        if not source or source["taxonomy"] != taxonomy:
            continue
        if source_id == body.target_id:
            continue

        # Re-tag posts from source to target
        for post in _POSTS.values():
            ids = post.get(key, [])
            if source_id in ids:
                ids.remove(source_id)
                if body.target_id not in ids:
                    ids.append(body.target_id)

        # Delete source term
        del _TERMS[source_id]
        merged_count += 1

    # Update target count
    target["count"] = sum(1 for p in _POSTS.values() if body.target_id in p.get(key, []))

    return {
        "message": f"Merged {merged_count} term(s) into '{target['name']}'.",
        "merged": merged_count,
        "target": _to_term_response(target),
    }
