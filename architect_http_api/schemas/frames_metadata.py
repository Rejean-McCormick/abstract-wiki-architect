# architect_http_api/schemas/frames_metadata.py
"""
Pydantic schemas describing the public “frames catalogue” metadata.

These models are used by the HTTP API layer to expose a structured
overview of all known frame families and frame types to the frontend.
They are intentionally UI-oriented and language-agnostic: they describe
what fields exist on each frame type, how they should be grouped, and
basic labels / descriptions, but they do not encode any rendering logic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from semantics.all_frames import FrameFamily, FrameType


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------


LangCode = str


class FieldKind(str, Enum):
    """
    Coarse input/control type for a frame field from the UI’s perspective.

    This is explicitly UI-facing and does not have to match the exact
    Python type used in the semantic dataclasses.
    """

    STRING = "string"  # short free-text
    TEXT = "text"  # multi-line free-text / markdown
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"  # constrained to a small finite set
    ENTITY = "entity"  # semantic Entity selector
    EVENT = "event"  # semantic Event selector
    TIME_SPAN = "time_span"  # semantic TimeSpan selector
    LIST = "list"  # homogeneous repeated values
    OBJECT = "object"  # nested structure / JSON blob


class LocalizedLabel(BaseModel):
    """
    Optional localization wrapper for labels and descriptions.

    Frontends that do not need localization can simply use `text` and
    ignore `translations`.
    """

    text: str = Field(..., description="Default (typically English) text.")
    translations: Dict[LangCode, str] = Field(
        default_factory=dict,
        description="Optional per-language overrides keyed by lang code (e.g. 'fr', 'sw').",
    )


# ---------------------------------------------------------------------------
# Field-level metadata
# ---------------------------------------------------------------------------


class FrameFieldMetadata(BaseModel):
    """
    UI-oriented description of a single frame field.

    This metadata is used by the frontend to build forms, show tooltips,
    and decide which input control to use.
    """

    name: str = Field(
        ...,
        description="Canonical field name as it appears in the JSON / dataclass.",
    )
    label: LocalizedLabel = Field(
        ...,
        description="Human-readable label for this field.",
    )
    description: Optional[LocalizedLabel] = Field(
        default=None,
        description="Optional longer help text / tooltip.",
    )

    kind: FieldKind = Field(
        FieldKind.STRING,
        description="Coarse UI control type for this field.",
    )

    required: bool = Field(
        False,
        description="Whether the field is logically required for this frame type.",
    )
    repeated: bool = Field(
        False,
        description="Whether the field is conceptually a list (even if empty).",
    )

    enum_values: Optional[List[str]] = Field(
        default=None,
        description="For ENUM kind: allowed string values.",
    )

    default: Any = Field(
        default=None,
        description="Logical default value used when the field is omitted.",
    )
    example: Any = Field(
        default=None,
        description="Example value suitable for sample payloads / docs.",
    )

    advanced: bool = Field(
        False,
        description=(
            "If true, hide this field behind an 'Advanced' toggle in UIs "
            "aimed at non-expert users."
        ),
    )

    group: Optional[str] = Field(
        default=None,
        description="Optional logical group name (e.g. 'identity', 'time', 'sources').",
    )
    order: int = Field(
        0,
        description="Optional stable ordering hint within a group or form.",
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form extension point for UI-specific metadata.",
    )


# ---------------------------------------------------------------------------
# Frame-type-level metadata
# ---------------------------------------------------------------------------


class FrameTypeMetadata(BaseModel):
    """
    Metadata for a single concrete frame type (identified by `frame_type`).

    This binds a `frame_type` string (e.g. 'bio', 'entity.gpe',
    'aggregate.timeline') to UI-facing labels, descriptions, and field
    metadata.
    """

    frame_type: FrameType = Field(
        ...,
        description="Canonical frame_type string as defined in semantics.all_frames.",
    )
    family: FrameFamily = Field(
        ...,
        description="Frame family identifier (e.g. 'entity', 'event', 'relational').",
    )

    title: LocalizedLabel = Field(
        ...,
        description="Human-readable name for this frame type.",
    )
    short_description: Optional[LocalizedLabel] = Field(
        default=None,
        description="1–2 sentence high-level description for selection UIs.",
    )
    long_description: Optional[LocalizedLabel] = Field(
        default=None,
        description="Optional longer documentation-style description.",
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags used for search and filtering in the UI.",
    )

    fields: List[FrameFieldMetadata] = Field(
        default_factory=list,
        description="Declared editable fields for this frame type in logical order.",
    )

    experimental: bool = Field(
        False,
        description=(
            "If true, this frame type is considered experimental / "
            "not yet production-ready."
        ),
    )
    deprecated: bool = Field(
        False,
        description="If true, this frame type is deprecated and should be hidden by default.",
    )

    examples: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Optional example JSON payloads for this frame type.",
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form extension point for caller- or UI-specific metadata.",
    )


# ---------------------------------------------------------------------------
# Family- and catalogue-level metadata
# ---------------------------------------------------------------------------


class FrameFamilyMetadata(BaseModel):
    """
    Grouping of frame types under a single frame family.

    This defines how the family itself is presented in the UI and lists
    all its member frame types.
    """

    family: FrameFamily = Field(
        ...,
        description="Canonical family identifier (e.g. 'entity', 'event', 'meta').",
    )
    label: LocalizedLabel = Field(
        ...,
        description="Human-readable label for this family.",
    )
    description: Optional[LocalizedLabel] = Field(
        default=None,
        description="Optional family-level description shown in navigation UIs.",
    )

    frame_types: List[FrameTypeMetadata] = Field(
        default_factory=list,
        description="All known frame types belonging to this family.",
    )

    order: int = Field(
        0,
        description="Optional ordering hint for families in the UI.",
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form extension point for caller- or UI-specific metadata.",
    )


class FramesCatalogue(BaseModel):
    """
    Top-level container returned by the frames catalogue endpoint.

    This is what the HTTP API typically returns from something like
    GET /frames/catalogue or GET /frames/metadata.
    """

    families: List[FrameFamilyMetadata] = Field(
        default_factory=list,
        description="All frame families and their member frame types.",
    )

    version: Optional[str] = Field(
        default=None,
        description=(
            "Optional semantic version or hash for the catalogue, to help "
            "with caching and client-side invalidation."
        ),
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="Timestamp when this catalogue snapshot was generated.",
    )

    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form extension point for service-level metadata.",
    )


__all__ = [
    "LangCode",
    "FieldKind",
    "LocalizedLabel",
    "FrameFieldMetadata",
    "FrameTypeMetadata",
    "FrameFamilyMetadata",
    "FramesCatalogue",
]
