"""
architect_http_api/schemas/entities.py

Pydantic models for the "entities" HTTP API.

These represent saved / curated entities that the frontend can browse,
inspect, and use as seeds for generation. The schema is intentionally
generic and tolerant of different frame families: an entity may carry
a canonical `frame_type` (e.g. "entity.person") and an arbitrary JSON
`frame_payload` that matches the underlying frame schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


EntityID = int


class APIModel(BaseModel):
    """
    Lightweight common base class.

    Kept local to avoid hard coupling to other schema modules; if you
    already have a shared API base class in `schemas.common`, you can
    replace this inheritance with that one.
    """

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class EntityBase(APIModel):
    """
    Fields shared by create / update / read for an entity.

    An "entity" is the conceptual subject of an article or profile
    (person, organization, place, creative work, etc.).
    """

    name: str = Field(..., description="Human-readable display name")
    slug: Optional[str] = Field(
        default=None,
        description=(
            "Optional URL-safe slug. If omitted on create, the backend "
            "may derive one from the name."
        ),
    )
    lang: str = Field(
        "en",
        description="ISO 639-1 language code for this entity's canonical article",
        examples=["en", "fr", "es"],
    )

    # Optional linkage into the frame inventory
    frame_type: Optional[str] = Field(
        default=None,
        description=(
            "Canonical frame_type string (e.g. 'entity.person', "
            "'entity.organization'). Used as a hint for downstream NLG."
        ),
    )

    # Canonical structured representation of the entity, in terms of
    # AbstractWiki frames. This is intentionally schemaless at the HTTP
    # boundary: validation happens deeper in the stack against the JSON
    # schemas in schemas/frames/.
    frame_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw JSON frame payload for this entity (if available).",
    )

    # Optional descriptive fields for UI
    short_description: Optional[str] = Field(
        default=None,
        description="One-line summary for list views (can be auto-generated).",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Free-form notes for curators / editors.",
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Optional tags / facets (e.g. ['science', '20th-century']).",
    )

    # Extra arbitrary metadata to keep the schema flexible.
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Arbitrary backend-defined metadata. Use this instead of "
            "adding one-off top-level fields."
        ),
    )


class EntityCreate(EntityBase):
    """
    Payload for creating a new entity.

    `name` is required; other fields are optional and may be filled by
    the backend (slug, timestamps, etc.).
    """

    # All fields from EntityBase are already appropriate for create.
    # We keep this class for explicitness and forward compatibility.
    pass


class EntityUpdate(APIModel):
    """
    Partial update payload.

    All fields are optional; only provided ones are patched.
    """

    name: Optional[str] = Field(
        default=None,
        description="New human-readable name.",
    )
    slug: Optional[str] = Field(
        default=None,
        description="New slug. If provided, must remain unique.",
    )
    lang: Optional[str] = Field(
        default=None,
        description="New canonical language code.",
    )
    frame_type: Optional[str] = Field(
        default=None,
        description="Update the canonical frame_type.",
    )
    frame_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Replace the stored frame payload.",
    )
    short_description: Optional[str] = Field(
        default=None,
        description="New one-line summary.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Replace or clear curator notes.",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Replace the tag list; send [] to clear.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Replace the metadata object; send {} to clear.",
    )


class Entity(EntityBase):
    """
    Full entity representation as returned by the API.
    """

    id: EntityID = Field(..., description="Database identifier")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")

    # Optional preview of the last generation associated with this entity.
    last_generation_summary: Optional[str] = Field(
        default=None,
        description=(
            "Short text or snippet from the most recent generation for this entity."
        ),
    )


class EntityListItem(APIModel):
    """
    Compact representation used in list endpoints.

    Keeps payload small for the main table / sidebar views.
    """

    id: EntityID
    name: str
    slug: Optional[str] = None
    lang: str = "en"
    frame_type: Optional[str] = None
    short_description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# List / collection wrappers
# ---------------------------------------------------------------------------


class EntityListResponse(APIModel):
    """
    Response model for paginated entity lists.

    The backend can still decide whether it wants cursor-based or
    offset-based pagination; this model simply exposes a common
    envelope shape to the frontend.
    """

    items: List[EntityListItem] = Field(
        default_factory=list,
        description="Page of entities.",
    )
    total: int = Field(
        ...,
        description="Total number of entities matching the query.",
    )
    page: int = Field(
        1,
        description="1-based index of the current page.",
    )
    page_size: int = Field(
        50,
        description="Maximum number of items per page.",
    )


class EntityDeleteResponse(APIModel):
    """
    Minimal response for successful deletion operations.
    """

    id: EntityID
    deleted: bool = Field(
        True,
        description="True if the entity was deleted.",
    )

