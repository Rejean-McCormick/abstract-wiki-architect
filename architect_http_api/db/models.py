# architect_http_api/db/models.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import enum
from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    Mapped,
    mapped_column,
)

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

Base = declarative_base()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(str, enum.Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PLACE = "place"
    WORK = "work"  # books, films, albums, etc.
    CONCEPT = "concept"  # abstract topics
    OTHER = "other"


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


class GenerationLogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Entity(Base):
    """
    High-level entity managed by the Architect UI.

    Examples:
      - A person whose bio and related frames you generate
      - An organization, place, or abstract topic

    The `data` column can store arbitrary, frame-friendly metadata
    (e.g. Wikidata IDs, occupations, dates) as JSON.
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, name="entity_type_enum"),
        nullable=False,
        default=EntityType.OTHER,
    )

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Free-form JSON: canonical IDs, aliases, dates, structured attributes, etc.
    data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="Optional tag payload; may be a list or dict depending on use.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    generations: Mapped[List["Generation"]] = relationship(
        "Generation",
        back_populates="entity",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Entity id={self.id!r} slug={self.slug!r} type={self.entity_type.value!r}>"


# ---------------------------------------------------------------------------
# Generations
# ---------------------------------------------------------------------------


class Generation(Base):
    """
    A single generation job/request made through the Architect HTTP API.

    Stores:
      - Which frame was used (`frame_slug`)
      - Structured request payload (`input_payload`)
      - Final text + any structured output (`output_text`, `output_payload`)
      - Status, errors, and basic tracing info
    """

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Optional link back to an Entity managed in the UI
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id"),
        nullable=True,
        index=True,
    )

    # Which frame template / workspace was used (e.g. "bio", "timeline")
    frame_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Language of the generation ("en", "fr", etc.)
    language_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # The original request as JSON (form data, frame payload, options, etc.)
    input_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Primary text output for display
    output_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional structured result (sentences, debug info, etc.)
    output_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[GenerationStatus] = mapped_column(
        SQLEnum(GenerationStatus, name="generation_status_enum"),
        nullable=False,
        default=GenerationStatus.PENDING,
        index=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trace / observability
    request_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Optional external correlation ID.",
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Model or engine identifier used for this generation.",
    )
    nlg_engine: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Internal NLG engine family, if relevant.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    entity: Mapped[Optional[Entity]] = relationship(
        "Entity",
        back_populates="generations",
    )

    logs: Mapped[List["GenerationLog"]] = relationship(
        "GenerationLog",
        back_populates="generation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Generation id={self.id!r} frame_slug={self.frame_slug!r} "
            f"status={self.status.value!r}>"
        )


# ---------------------------------------------------------------------------
# Generation logs
# ---------------------------------------------------------------------------


class GenerationLog(Base):
    """
    Structured log entries for a generation.

    Useful for debugging, audit trails, or exposing a "debug timeline" in the UI.
    """

    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    generation_id: Mapped[int] = mapped_column(
        ForeignKey("generations.id"),
        nullable=False,
        index=True,
    )

    level: Mapped[GenerationLogLevel] = mapped_column(
        SQLEnum(GenerationLogLevel, name="generation_log_level_enum"),
        nullable=False,
        default=GenerationLogLevel.INFO,
        index=True,
    )

    # Optional short context label (e.g. "router", "nlg_client", "ai_suggestion")
    context: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Additional structured data (e.g. partial frames, raw NLG output, timings)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # Relationships
    generation: Mapped["Generation"] = relationship(
        "Generation",
        back_populates="logs",
    )

    def __repr__(self) -> str:
        return (
            f"<GenerationLog id={self.id!r} generation_id={self.generation_id!r} "
            f"level={self.level.value!r}>"
        )
