from __future__ import annotations

from typing import Any, Dict, Literal, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Style = Literal["simple", "formal"]
EntityLike = Union["Entity", Dict[str, Any]]
EventObjectLike = Union["Entity", Dict[str, Any], str]

_BIOISH_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}

_STYLE_ALIASES: dict[str, Style] = {
    "simple": "simple",
    "plain": "simple",
    "default": "simple",
    "neutral": "simple",
    "basic": "simple",
    "formal": "formal",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _coerce_mapping(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("Expected a mapping-compatible object.")


def _entity_attr(obj: EntityLike | None, key: str) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, Entity):
        return _clean_optional_str(getattr(obj, key, None))
    if isinstance(obj, dict):
        return _clean_optional_str(obj.get(key))
    return None


def _set_entity_attr(obj: EntityLike, key: str, value: str) -> None:
    cleaned = value.strip()
    if not cleaned:
        return
    if isinstance(obj, Entity):
        setattr(obj, key, cleaned)
    elif isinstance(obj, dict):
        obj[key] = cleaned


def _best_name(obj: EntityLike | None) -> str:
    return _entity_attr(obj, "name") or "Unknown"


def _copy_if_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _fill_if_missing(target: Dict[str, Any], key: str, value: Any) -> None:
    cleaned = _clean_optional_str(value)
    if cleaned and not _clean_optional_str(target.get(key)):
        target[key] = cleaned


def _pick_first_str(*values: Any) -> Optional[str]:
    for value in values:
        cleaned = _clean_optional_str(value)
        if cleaned:
            return cleaned
    return None


# ---------------------------------------------------------------------------
# Shared entity model
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """
    Lightweight discourse entity used by wire/domain frames.

    This model is intentionally permissive:
    - required `name` for direct instantiation
    - optional metadata fields used by discourse/planning and routers
    - extra fields are preserved for forward compatibility
    """

    name: str = Field(..., min_length=1)
    qid: Optional[str] = None
    profession: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Entity.name must be a non-empty string.")
        return cleaned

    @field_validator("qid", "profession", "nationality", "gender", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> Any:
        return _clean_optional_str(value)


# ---------------------------------------------------------------------------
# Base frame
# ---------------------------------------------------------------------------


class BaseFrame(BaseModel):
    """
    Base semantic wire-frame.

    Stable nested contract:
      - `subject`: frame-specific
      - `properties`: semantic attribute bag
      - `meta`: diagnostics / provenance / request metadata

    Notes:
      - This file models the Pydantic wire/domain frames used by the API path.
      - Richer semantic dataclasses live separately in `semantics.types`.
    """

    context_id: Optional[str] = Field(
        default=None,
        description="UUID linking this frame to a discourse/session context.",
    )
    style: Style = Field(
        default="simple",
        description="Surface style hint consumed by planning/realization.",
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Frame-specific semantic properties.",
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque metadata for tracing/debugging/provenance.",
    )

    model_config = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_common_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw = dict(data)

        # Accept common synonyms sent by older callers.
        style_in = raw.get("style", raw.get("register"))
        if isinstance(style_in, str):
            normalized_style = _STYLE_ALIASES.get(style_in.strip().lower())
            if normalized_style is not None:
                raw["style"] = normalized_style

        if "properties" in raw:
            raw["properties"] = _coerce_mapping(raw.get("properties"))
        else:
            raw["properties"] = {}

        if "meta" in raw:
            raw["meta"] = _coerce_mapping(raw.get("meta"))
        else:
            raw["meta"] = {}

        raw["context_id"] = _clean_optional_str(raw.get("context_id"))
        return raw

    @field_validator("style", mode="before")
    @classmethod
    def _normalize_style(cls, value: Any) -> Style:
        cleaned = _clean_optional_str(value) or "simple"
        normalized = _STYLE_ALIASES.get(cleaned.lower())
        if normalized is None:
            raise ValueError("style must be one of: simple, formal.")
        return normalized

    @field_validator("context_id", mode="before")
    @classmethod
    def _normalize_context_id(cls, value: Any) -> Any:
        return _clean_optional_str(value)

    @field_validator("properties", "meta", mode="before")
    @classmethod
    def _normalize_dict_fields(cls, value: Any) -> Dict[str, Any]:
        return _coerce_mapping(value)


# ---------------------------------------------------------------------------
# Bio frame
# ---------------------------------------------------------------------------


class BioFrame(BaseFrame):
    """
    Biography/person wire-frame.

    Canonical payload shape:
        {
          "frame_type": "bio",
          "subject": {"name": "...", "qid": "...", "gender": "..."},
          "properties": {"profession": "...", "nationality": "..."},
          "meta": {...}
        }

    Still accepts legacy flat inputs such as:
        {
          "frame_type": "entity.person",
          "name": "Alan Turing",
          "profession": "mathematician",
          "nationality": "British",
          "gender": "m",
          "qid": "Q7251"
        }
    """

    frame_type: Literal["bio"] = "bio"
    subject: EntityLike = Field(..., description="Main discourse entity.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_bio_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw = dict(data)
        incoming_type = str(raw.get("frame_type") or "").strip().lower()

        # Start from any existing nested subject/properties.
        subject_in = raw.get("subject")
        properties_in = raw.get("properties")

        subject = _copy_if_mapping(subject_in)
        properties = _copy_if_mapping(properties_in)

        # If subject is not a mapping, allow Pydantic to parse Entity instances later.
        # We only normalize legacy flat payloads into nested dicts here.
        if not subject and isinstance(subject_in, Entity):
            pass

        # Merge legacy flat fields into the canonical nested structure.
        _fill_if_missing(subject, "name", raw.get("name"))
        _fill_if_missing(subject, "name", raw.get("label"))
        _fill_if_missing(subject, "qid", raw.get("qid"))
        _fill_if_missing(subject, "gender", raw.get("gender"))
        _fill_if_missing(subject, "gender", raw.get("sex"))

        _fill_if_missing(properties, "profession", raw.get("profession"))
        _fill_if_missing(properties, "profession", raw.get("occupation"))
        _fill_if_missing(properties, "nationality", raw.get("nationality"))
        _fill_if_missing(properties, "nationality", raw.get("citizenship"))

        # If the upstream subject already contains profession/nationality, keep them;
        # they remain readable through compatibility properties.
        if subject:
            raw["subject"] = subject
        if properties:
            raw["properties"] = properties

        # Canonicalize known bio/person aliases.
        if incoming_type in _BIOISH_FRAME_TYPES or not incoming_type:
            raw["frame_type"] = "bio"

        return raw

    @model_validator(mode="after")
    def _validate_subject_name(self) -> "BioFrame":
        if not self.name or self.name == "Unknown":
            raise ValueError(
                "BioFrame requires a subject with a non-empty `name`."
            )
        return self

    @property
    def name(self) -> str:
        """Compatibility bridge used by discourse and older render paths."""
        return _best_name(self.subject)

    @name.setter
    def name(self, value: str) -> None:
        _set_entity_attr(self.subject, "name", value)

    @property
    def gender(self) -> Optional[str]:
        return _entity_attr(self.subject, "gender")

    @property
    def qid(self) -> Optional[str]:
        return _entity_attr(self.subject, "qid")

    @property
    def profession(self) -> Optional[str]:
        return _pick_first_str(
            _entity_attr(self.subject, "profession"),
            self.properties.get("profession"),
            self.properties.get("occupation"),
        )

    @profession.setter
    def profession(self, value: str) -> None:
        cleaned = _clean_optional_str(value)
        if cleaned:
            self.properties["profession"] = cleaned

    @property
    def nationality(self) -> Optional[str]:
        return _pick_first_str(
            _entity_attr(self.subject, "nationality"),
            self.properties.get("nationality"),
            self.properties.get("citizenship"),
        )

    @nationality.setter
    def nationality(self, value: str) -> None:
        cleaned = _clean_optional_str(value)
        if cleaned:
            self.properties["nationality"] = cleaned

    @property
    def subject_name(self) -> str:
        return self.name

    @property
    def subject_qid(self) -> Optional[str]:
        return self.qid


# ---------------------------------------------------------------------------
# Event frame
# ---------------------------------------------------------------------------


class EventFrame(BaseFrame):
    """
    Event/state wire-frame.

    Stable shape:
      - subject: main participant/topic
      - event_object: entity/dict/string target or secondary participant
      - event_type: open semantic key
      - properties/meta: extension bags
    """

    frame_type: Literal["event"] = "event"
    subject: EntityLike
    event_object: EventObjectLike
    event_type: str = Field(
        default="participation",
        description="Event type key such as 'participation', 'birth', 'award'.",
    )
    date: Optional[str] = Field(default=None, description="Year or ISO-like date.")
    location: Optional[str] = Field(default=None, description="Location label or key.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_event_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw = dict(data)

        # Accept a few legacy aliases.
        if "event_object" not in raw:
            for alias in ("object", "target", "patient", "theme"):
                if alias in raw:
                    raw["event_object"] = raw[alias]
                    break

        if "event_type" not in raw:
            for alias in ("type", "kind"):
                value = raw.get(alias)
                if isinstance(value, str) and value.strip():
                    raw["event_type"] = value
                    break

        if "date" in raw:
            raw["date"] = _clean_optional_str(raw.get("date"))
        if "location" in raw:
            raw["location"] = _clean_optional_str(raw.get("location"))

        return raw

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("event_type must be a non-empty string.")
        return cleaned

    @field_validator("date", "location", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> Any:
        return _clean_optional_str(value)

    @property
    def name(self) -> str:
        return _best_name(self.subject)

    @property
    def gender(self) -> Optional[str]:
        return _entity_attr(self.subject, "gender")

    @property
    def qid(self) -> Optional[str]:
        return _entity_attr(self.subject, "qid")


# ---------------------------------------------------------------------------
# Relational frame
# ---------------------------------------------------------------------------


class RelationalFrame(BaseFrame):
    """
    Direct relationship between two entities.

    Uses `object` intentionally to preserve compatibility with existing callers.
    """

    frame_type: Literal["relational"] = "relational"
    subject: EntityLike
    relation: str = Field(..., description="Predicate key such as 'spouse_of'.")
    object: EntityLike

    @model_validator(mode="before")
    @classmethod
    def _normalize_relational_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw = dict(data)

        if "object" not in raw:
            for alias in ("target", "right", "other"):
                if alias in raw:
                    raw["object"] = raw[alias]
                    break

        if "relation" in raw:
            raw["relation"] = _clean_optional_str(raw.get("relation"))

        return raw

    @field_validator("relation")
    @classmethod
    def _validate_relation(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("relation must be a non-empty string.")
        return cleaned

    @property
    def name(self) -> str:
        return _best_name(self.subject)

    @property
    def gender(self) -> Optional[str]:
        return _entity_attr(self.subject, "gender")

    @property
    def qid(self) -> Optional[str]:
        return _entity_attr(self.subject, "qid")


# ---------------------------------------------------------------------------
# Public aliases
# ---------------------------------------------------------------------------

SemanticFrame = Union[BioFrame, EventFrame, RelationalFrame, BaseFrame]

__all__ = [
    "Style",
    "EntityLike",
    "EventObjectLike",
    "Entity",
    "BaseFrame",
    "BioFrame",
    "EventFrame",
    "RelationalFrame",
    "SemanticFrame",
]