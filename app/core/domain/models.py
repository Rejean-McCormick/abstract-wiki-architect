# app/core/domain/models.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Unify Frame definition by importing from the authoritative source
from app.core.domain.frame import BaseFrame, BioFrame, EventFrame

# -----------------------------
# Frames (compat + canonical)
# -----------------------------

# Canonical semantic frames from the domain package
SemanticFrame = Union[BioFrame, EventFrame, BaseFrame]

# Backward-compat: older tests/imports expect FrameType + a Pydantic Frame model.
# Keep it permissive (string) to avoid tight coupling to frame registries.
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


class Frame(BaseModel):
    """
    Backward-compatible Frame model used in tests and older API payloads.

    Supports both:
      1) Canonical nested payloads:
         Frame(frame_type="bio", subject={...}, properties={...}, meta={...})

      2) Legacy / GUI flat payloads:
         {
           "frame_type": "entity.person",
           "name": "Alan Turing",
           "profession": "Mathematician",
           "nationality": "British",
           "gender": "m",
           ...
         }

    For bio-like frame types, flat top-level person fields are normalized into
    `subject` so downstream code can rely on a stable shape.
    """

    frame_type: FrameType
    subject: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

    # Optional compatibility fields sometimes sent by the GUI / legacy callers.
    # These are normalized into `subject` for bio-like frames but still accepted
    # here so they are not silently dropped before normalization.
    context_id: Optional[str] = None
    style: str = "simple"

    name: Optional[str] = None
    profession: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    qid: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_person_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        raw = dict(data)
        frame_type = str(raw.get("frame_type") or "").strip().lower()

        # Start from existing nested subject if present.
        subject_in = raw.get("subject")
        subject: Dict[str, Any] = dict(subject_in) if isinstance(subject_in, dict) else {}

        # Merge common flat legacy fields into subject.
        for key in ("name", "profession", "nationality", "gender", "qid"):
            value = raw.get(key)
            if isinstance(value, str):
                value = value.strip()
                if value:
                    subject.setdefault(key, value)

        # Preserve the normalized subject if anything meaningful was found.
        if subject:
            raw["subject"] = subject

        # For bio/person-like frames, require at least some subject data.
        if frame_type in _BIOISH_FRAME_TYPES and not raw.get("subject"):
            raise ValueError(
                "Bio/person frames require `subject`, or flat fields such as "
                "`name`, `profession`, `nationality`, `gender`, `qid`."
            )

        return raw

    @property
    def subject_name(self) -> Optional[str]:
        value = self.subject.get("name")
        return value if isinstance(value, str) and value.strip() else None

    @property
    def subject_qid(self) -> Optional[str]:
        value = self.subject.get("qid")
        return value if isinstance(value, str) and value.strip() else None


# --- Enums ---

class LanguageStatus(str, Enum):
    """Lifecycle status of a language in the system."""
    PLANNED = "planned"       # Defined in config but no files exist
    SCAFFOLDED = "scaffolded" # Directories created, seed files exist
    BUILDING = "building"     # Compilation in progress
    READY = "ready"           # Successfully compiled and loaded
    ERROR = "error"           # Build failed


class GrammarType(str, Enum):
    """The type of grammar engine backing a language."""
    RGL = "rgl"               # Official Resource Grammar Library
    CONTRIB = "contrib"       # Manual contribution (Silver tier)
    FACTORY = "factory"       # Auto-generated Pidgin (Bronze tier)


# --- Entities ---

class Language(BaseModel):
    """
    Represents a supported language in the system.
    Matches the data found in the 'Everything Matrix'.
    """
    # Accept ISO 639-1 or ISO 639-3 (some parts of the system use iso2 keys)
    code: str = Field(
        ...,
        min_length=2,
        max_length=3,
        pattern=r"^[a-z]{2,3}$",
        description="ISO 639-1 or 639-3 code (e.g., 'en', 'fra')",
    )
    name: str = Field(..., min_length=1, description="English name of the language")
    family: Optional[str] = Field(None, description="Language family (e.g., 'Romance')")
    status: LanguageStatus = LanguageStatus.PLANNED
    grammar_type: GrammarType = GrammarType.FACTORY

    # Metadata for tracking build health
    build_strategy: str = Field("fast", pattern=r"^(fast|full)$", description="Build strategy")
    last_build_time: Optional[datetime] = None
    error_log: Optional[str] = None


class Sentence(BaseModel):
    """The output generated text."""
    text: str
    lang_code: str

    # Debug info provided by the engine (e.g., linearization tree)
    debug_info: Optional[Dict[str, Any]] = None

    # Metrics for observability
    generation_time_ms: float = 0.0


class LexiconEntry(BaseModel):
    """Represents a single word in the lexicon."""
    lemma: str
    pos: str  # Part of Speech: N, V, A, etc.
    features: Dict[str, Any] = Field(default_factory=dict)  # Gender, Number, etc.
    source: str = "manual"  # 'wikidata', 'ai', 'manual'
    confidence: float = 1.0


# --- API Payloads ---

class GenerationRequest(BaseModel):
    """
    Input payload for the text generation endpoint.
    (Kept for compatibility; router may accept raw Frame JSON directly.)
    """
    semantic_frame: Frame
    target_language: str = Field(..., min_length=2, max_length=3, description="ISO 639-1 or 639-3")