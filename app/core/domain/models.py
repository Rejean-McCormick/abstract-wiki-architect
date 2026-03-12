# app/core/domain/models.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# Authoritative frame definitions live here.
from app.core.domain.frame import BaseFrame, BioFrame, Entity, EventFrame, RelationalFrame

# -----------------------------
# Frames (canonical + compat)
# -----------------------------

# Canonical semantic frames from the domain package.
SemanticFrame = Union[BioFrame, EventFrame, RelationalFrame, BaseFrame]

# Backward-compatible wire discriminator.
FrameType = str

_BIOISH_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}

_EVENTISH_FRAME_TYPES = {
    "event",
    "eventive",
    "event.transitive",
    "event.intransitive",
    "event.ditransitive",
}

_RELATIONISH_FRAME_TYPES = {
    "relational",
    "relation",
    "attribute_property",
    "membership_affiliation",
    "ownership_control",
    "part_whole_composition",
    "role_position_office",
}

_CANONICAL_BIO_FRAME_TYPE = "bio"
_CANONICAL_EVENT_FRAME_TYPE = "event"
_CANONICAL_RELATIONAL_FRAME_TYPE = "relational"


def _clean_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value).strip() or None


def _clean_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_frame_type(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


class Frame(BaseModel):
    """
    Backward-compatible wire/domain frame used by existing tests, routers, and
    the legacy engine contract.

    This model is intentionally permissive at the boundary. It accepts:
      1) current nested payloads:
         {
           "frame_type": "bio",
           "subject": {...},
           "properties": {...},
           "meta": {...}
         }

      2) older flat person payloads:
         {
           "frame_type": "entity.person",
           "name": "Alan Turing",
           "profession": "mathematician",
           "nationality": "British",
           "gender": "m",
           "qid": "Q7251"
         }

      3) semantics-style bio payloads:
         {
           "frame_type": "bio",
           "main_entity": {...},
           "primary_profession_lemmas": [...],
           "nationality_lemmas": [...]
         }

    The normalization goal is simple:
    - `subject`, `properties`, and `meta` are always dicts
    - bio-ish payloads end up with a normalized `subject`
    - common flat legacy fields are preserved
    """

    frame_type: FrameType

    # Stable normalized shape used by older runtime code.
    subject: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    # Common compatibility fields.
    context_id: Optional[str] = None
    style: str = "simple"

    # Legacy flat fields that callers/tests may still send/read.
    name: Optional[str] = None
    profession: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    qid: Optional[str] = None

    # Event / relational compatibility fields.
    event_object: Any = None
    event_type: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    relation: Optional[str] = None
    object: Any = None

    # Semantics-style compatibility fields.
    main_entity: Optional[Dict[str, Any]] = None
    primary_profession_lemmas: list[str] = Field(default_factory=list)
    nationality_lemmas: list[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data

        raw: Dict[str, Any] = dict(data)
        frame_type = _normalize_frame_type(raw.get("frame_type"))
        frame_type_lc = frame_type.lower()

        # Always normalize the stable dict containers.
        raw["subject"] = _clean_mapping(raw.get("subject"))
        raw["properties"] = _clean_mapping(raw.get("properties"))
        raw["meta"] = _clean_mapping(raw.get("meta"))
        raw["attributes"] = _clean_mapping(raw.get("attributes"))
        raw["extra"] = _clean_mapping(raw.get("extra"))

        # semantics.types-style payloads sometimes use `main_entity`
        # instead of `subject`.
        main_entity = _clean_mapping(raw.get("main_entity"))
        if main_entity and not raw["subject"]:
            raw["subject"] = dict(main_entity)
        if main_entity:
            raw["main_entity"] = main_entity

        # Merge flat legacy person fields into subject.
        for key in ("name", "profession", "nationality", "gender", "qid"):
            value = _clean_optional_str(raw.get(key))
            if value:
                raw[key] = value
                raw["subject"].setdefault(key, value)

        # Promote semantics-style profession / nationality lists into
        # compatibility properties when useful.
        prof_lemmas = raw.get("primary_profession_lemmas")
        if isinstance(prof_lemmas, list):
            prof_lemmas = [str(x).strip() for x in prof_lemmas if str(x).strip()]
            raw["primary_profession_lemmas"] = prof_lemmas
            if prof_lemmas:
                raw["properties"].setdefault("primary_profession_lemmas", prof_lemmas)
                raw["properties"].setdefault("profession", prof_lemmas[0])

        nat_lemmas = raw.get("nationality_lemmas")
        if isinstance(nat_lemmas, list):
            nat_lemmas = [str(x).strip() for x in nat_lemmas if str(x).strip()]
            raw["nationality_lemmas"] = nat_lemmas
            if nat_lemmas:
                raw["properties"].setdefault("nationality_lemmas", nat_lemmas)
                raw["properties"].setdefault("nationality", nat_lemmas[0])

        # Also expose common bio slots through `properties` for older engines.
        for key in ("profession", "nationality", "gender", "qid", "name"):
            value = raw["subject"].get(key)
            if value is not None:
                raw["properties"].setdefault(key, value)

        # Require usable subject information for biography-like payloads.
        if frame_type_lc in _BIOISH_FRAME_TYPES and not raw["subject"]:
            raise ValueError(
                "Bio/person frames require `subject`, `main_entity`, or flat "
                "person fields such as `name`, `profession`, `nationality`, "
                "`gender`, `qid`."
            )

        return raw

    @field_validator("frame_type", mode="before")
    @classmethod
    def _normalize_frame_type_field(cls, value: Any) -> str:
        return _normalize_frame_type(value)

    @field_validator("style", mode="before")
    @classmethod
    def _normalize_style(cls, value: Any) -> str:
        style = _clean_optional_str(value) or "simple"
        return style if style in {"simple", "formal"} else "simple"

    @property
    def normalized_frame_type(self) -> str:
        value = self.frame_type.strip().lower()
        if value in _BIOISH_FRAME_TYPES:
            return _CANONICAL_BIO_FRAME_TYPE
        if value in _EVENTISH_FRAME_TYPES:
            return _CANONICAL_EVENT_FRAME_TYPE
        if value in _RELATIONISH_FRAME_TYPES:
            return _CANONICAL_RELATIONAL_FRAME_TYPE
        return value or self.frame_type

    @property
    def subject_name(self) -> Optional[str]:
        value = self.subject.get("name")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def subject_qid(self) -> Optional[str]:
        value = self.subject.get("qid")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def is_bio_like(self) -> bool:
        return self.normalized_frame_type == _CANONICAL_BIO_FRAME_TYPE

    @property
    def is_event_like(self) -> bool:
        return self.normalized_frame_type == _CANONICAL_EVENT_FRAME_TYPE

    @property
    def is_relation_like(self) -> bool:
        return self.normalized_frame_type == _CANONICAL_RELATIONAL_FRAME_TYPE

    def to_bio_frame(self) -> BioFrame:
        """
        Best-effort conversion into the canonical BioFrame model.

        This is intentionally narrow: only use it when the caller knows the
        payload is biography-like.
        """
        if not self.is_bio_like:
            raise ValueError(
                f"Cannot convert frame_type={self.frame_type!r} to BioFrame."
            )

        return BioFrame(
            frame_type="bio",
            subject=dict(self.subject),
            context_id=self.context_id,
            style=self.style,  # frame.py currently constrains this
            meta={**self.meta, "properties": dict(self.properties)},
        )

    def to_event_frame(self) -> EventFrame:
        """
        Best-effort conversion into the canonical EventFrame model.
        """
        if not self.is_event_like:
            raise ValueError(
                f"Cannot convert frame_type={self.frame_type!r} to EventFrame."
            )

        return EventFrame(
            frame_type="event",
            subject=dict(self.subject),
            event_object=self.event_object,
            event_type=self.event_type or "participation",
            date=self.date,
            location=self.location,
            context_id=self.context_id,
            style=self.style,
            meta={**self.meta, "properties": dict(self.properties)},
        )

    def to_relational_frame(self) -> RelationalFrame:
        """
        Best-effort conversion into the canonical RelationalFrame model.
        """
        if not self.is_relation_like:
            raise ValueError(
                f"Cannot convert frame_type={self.frame_type!r} to RelationalFrame."
            )

        if not self.relation:
            raise ValueError("Relational frames require `relation`.")

        return RelationalFrame(
            frame_type="relational",
            subject=dict(self.subject),
            relation=self.relation,
            object=self.object,
            context_id=self.context_id,
            style=self.style,
            meta={**self.meta, "properties": dict(self.properties)},
        )

    def to_canonical_frame(self) -> SemanticFrame:
        """
        Convert this compatibility frame to the nearest canonical frame model.

        Unknown frame types are returned as a generic BaseFrame, preserving
        boundary data in `meta`.
        """
        if self.is_bio_like:
            return self.to_bio_frame()
        if self.is_event_like:
            return self.to_event_frame()
        if self.is_relation_like:
            return self.to_relational_frame()

        return BaseFrame(
            context_id=self.context_id,
            style=self.style,
            meta={
                **self.meta,
                "frame_type": self.frame_type,
                "subject": dict(self.subject),
                "properties": dict(self.properties),
            },
        )


# --- Enums ---------------------------------------------------------------


class LanguageStatus(str, Enum):
    """Lifecycle status of a language in the system."""

    PLANNED = "planned"
    SCAFFOLDED = "scaffolded"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"


class GrammarType(str, Enum):
    """The type of grammar engine backing a language."""

    RGL = "rgl"
    CONTRIB = "contrib"
    FACTORY = "factory"


# --- Entities / Value Objects -------------------------------------------


class Language(BaseModel):
    """
    Represents a supported language in the system.
    """

    code: str = Field(
        ...,
        min_length=2,
        max_length=3,
        pattern=r"^[a-z]{2,3}$",
        description="ISO 639-1 or ISO 639-3 code (e.g. 'en', 'fra').",
    )
    name: str = Field(..., min_length=1, description="English language name.")
    family: Optional[str] = Field(None, description="Language family label.")
    status: LanguageStatus = LanguageStatus.PLANNED
    grammar_type: GrammarType = GrammarType.FACTORY

    build_strategy: str = Field(
        "fast",
        pattern=r"^(fast|full)$",
        description="Build strategy.",
    )
    last_build_time: Optional[datetime] = None
    error_log: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("code", mode="before")
    @classmethod
    def _normalize_code(cls, value: Any) -> str:
        code = _clean_optional_str(value)
        if not code:
            raise ValueError("Language code is required.")
        return code.lower()


class SurfaceResult(BaseModel):
    """
    Canonical renderer output for the planner-first runtime.

    This is the target internal response shape for:
        ConstructionPlan -> SurfaceResult

    It intentionally remains compatible with the existing API response shape,
    where only `text`, `lang_code`, and `debug_info` are required by callers.
    """

    text: str
    lang_code: str

    # Planner/runtime metadata
    construction_id: Optional[str] = None
    renderer_backend: Optional[str] = None
    fallback_used: bool = False
    tokens: list[str] = Field(default_factory=list)

    # Observability / debug
    debug_info: Dict[str, Any] = Field(default_factory=dict)
    generation_time_ms: float = 0.0

    model_config = ConfigDict(extra="ignore")

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        if value is None:
            raise ValueError("text is required.")
        return str(value)

    @field_validator("lang_code", mode="before")
    @classmethod
    def _normalize_lang_code(cls, value: Any) -> str:
        code = _clean_optional_str(value)
        if not code:
            raise ValueError("lang_code is required.")
        return code.lower()

    @model_validator(mode="after")
    def _sync_debug_info(self) -> "SurfaceResult":
        debug = dict(self.debug_info or {})

        if self.construction_id and "construction_id" not in debug:
            debug["construction_id"] = self.construction_id
        if self.renderer_backend and "renderer_backend" not in debug:
            debug["renderer_backend"] = self.renderer_backend
        if "lang_code" not in debug:
            debug["lang_code"] = self.lang_code
        if "fallback_used" not in debug:
            debug["fallback_used"] = self.fallback_used

        self.debug_info = debug
        return self


class Sentence(SurfaceResult):
    """
    Backward-compatible public result model.

    Legacy code and tests still import/use `Sentence`. New planner-runtime code
    should prefer `SurfaceResult`, but both serialize the same stable API shape.
    """

    pass


class LexiconEntry(BaseModel):
    """Represents a single lexical entry."""

    lemma: str
    pos: str
    features: Dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    confidence: float = 1.0

    model_config = ConfigDict(extra="ignore")

    @field_validator("lemma", "pos", "source", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        text = _clean_optional_str(value)
        if not text:
            raise ValueError("Field must be a non-empty string.")
        return text

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, value: Any) -> float:
        if value is None:
            return 1.0
        return float(value)


# --- API Payloads --------------------------------------------------------


class GenerationRequest(BaseModel):
    """
    Input payload for text generation endpoints.

    Kept for compatibility with callers that wrap the frame instead of posting a
    raw frame payload directly.
    """

    semantic_frame: Frame = Field(
        ...,
        validation_alias=AliasChoices("semantic_frame", "frame"),
        description="Normalized compatibility frame payload.",
    )
    target_language: str = Field(
        ...,
        min_length=2,
        max_length=3,
        validation_alias=AliasChoices(
            "target_language",
            "targetLanguage",
            "lang",
            "lang_code",
            "language",
        ),
        description="ISO 639-1 or ISO 639-3 target language code.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("target_language", mode="before")
    @classmethod
    def _normalize_target_language(cls, value: Any) -> str:
        lang = _clean_optional_str(value)
        if not lang:
            raise ValueError("Target language is required.")
        return lang.lower()

    @property
    def lang_code(self) -> str:
        return self.target_language


__all__ = [
    # Canonical frame layer re-exports
    "Entity",
    "BaseFrame",
    "BioFrame",
    "EventFrame",
    "RelationalFrame",
    "SemanticFrame",
    # Compatibility wire frame
    "FrameType",
    "Frame",
    # Result models
    "SurfaceResult",
    "Sentence",
    # Language / lexicon
    "LanguageStatus",
    "GrammarType",
    "Language",
    "LexiconEntry",
    # Requests
    "GenerationRequest",
]