# architect_http_api/schemas/generations.py

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .common import BaseApiModel


class GenerationStatus(str, Enum):
    """
    Lifecycle status of a generation request.

    The current HTTP API is synchronous and will mostly return
    COMPLETED or FAILED, but the enum is future-proofed for async flows.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationOptions(BaseApiModel):
    """
    HTTP representation of the GenerationOptions documented in docs/FRONTEND_API.md.

    This is a thin JSON-friendly wrapper; the NLG layer can map this
    back to its internal dataclass if needed.
    """

    register: Optional[str] = Field(
        default=None,
        description='Stylistic register, e.g. "neutral", "formal", "informal".',
    )
    max_sentences: Optional[int] = Field(
        default=None,
        ge=1,
        description="Upper bound on the number of sentences to generate.",
    )
    discourse_mode: Optional[str] = Field(
        default=None,
        description='High-level discourse mode, e.g. "intro", "summary".',
    )
    seed: Optional[int] = Field(
        default=None,
        description="Reserved for future stochastic behavior / reproducibility.",
    )


class GenerationRequest(BaseApiModel):
    """
    Request body for the /generate endpoint.

    The frontend chooses a frame_slug, collects a frame_payload that
    conforms to that frame’s schema, and passes optional GenerationOptions.
    """

    frame_slug: str = Field(
        ...,
        description="Frame configuration slug, e.g. 'bio.person' or 'event.generic'.",
    )
    lang: str = Field(
        ...,
        min_length=1,
        description="Target language code, e.g. 'en', 'fr', 'sw'.",
    )
    frame_payload: Dict[str, Any] = Field(
        ...,
        description=(
            "Arbitrary JSON payload for the frame. Must match the schema "
            "associated with frame_slug (see frames_registry)."
        ),
    )
    options: Optional[GenerationOptions] = Field(
        default=None,
        description="Optional high-level generation controls.",
    )
    debug: bool = Field(
        default=False,
        description="If true, include engine-specific debug_info in the result when available.",
    )


class GenerationResult(BaseApiModel):
    """
    JSON-serializable mirror of docs/FRONTEND_API.md::GenerationResult.

    - text: final realized text
    - sentences: sentence-level split
    - lang: language actually used
    - frame: original frame as a JSON object
    - debug_info: optional engine-specific metadata
    """

    text: str = Field(
        ...,
        description="Final realized text.",
    )
    sentences: List[str] = Field(
        default_factory=list,
        description="Sentence-level split of the text.",
    )
    lang: str = Field(
        ...,
        description="Language code used by the NLG engine.",
    )
    frame: Dict[str, Any] = Field(
        ...,
        description="Original frame as a JSON object (after any normalization).",
    )
    debug_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Engine-specific debug information, present only when debug=True.",
    )


class GenerationResponse(BaseApiModel):
    """
    Envelope returned by the /generate endpoint.

    For now the API is synchronous, so typical responses are:
      - status=COMPLETED with result populated
      - status=FAILED with error populated
    """

    frame_slug: str = Field(
        ...,
        description="Echo of the frame_slug used for this generation.",
    )
    lang: str = Field(
        ...,
        description="Echo of the requested / effective language.",
    )
    status: GenerationStatus = Field(
        default=GenerationStatus.COMPLETED,
        description="Lifecycle status of the generation.",
    )
    result: Optional[GenerationResult] = Field(
        default=None,
        description="Generation result when status=COMPLETED.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Human-readable error message when status=FAILED.",
    )
