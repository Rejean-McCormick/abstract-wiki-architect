# architect_http_api/schemas/generic.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import GenerationOptions


class GenericGenerateRequest(BaseModel):
    """
    Generic “frame → text” generation request.

    This mirrors the core `nlg.api.generate` entry point, but with a JSON
    `frame` payload suitable for HTTP. The concrete shape of `frame` depends
    on `frame_type` and should follow the corresponding JSON schema.
    """

    lang: str = Field(
        ...,
        description="Target language (ISO 639-1 code), e.g. 'en', 'fr', 'sw'.",
        examples=["en", "fr"],
    )
    frame_type: str = Field(
        ...,
        description=(
            "Canonical frame_type string, e.g. 'bio', 'entity.organization', "
            "'event.battle'. Used for routing to the appropriate family engine."
        ),
        examples=["bio", "entity.organization"],
    )
    frame: Dict[str, Any] = Field(
        ...,
        description=(
            "Normalized frame payload for the given frame_type. "
            "Must match the corresponding JSON schema under schemas/frames/."
        ),
        example={
            "frame_type": "bio",
            "name": "Douglas Adams",
            "gender": "male",
            "profession_lemma": "writer",
            "nationality_lemma": "British",
        },
    )
    options: Optional[GenerationOptions] = Field(
        None,
        description="Optional high-level generation controls (style, length, etc.).",
    )
    debug: bool = Field(
        False,
        description="If true, include implementation-specific debug_info in the response.",
    )


class GenericGeneration(BaseModel):
    """
    Standardized generic generation result for a single frame.

    This is the HTTP/JSON counterpart of `nlg.api.GenerationResult`.
    """

    text: str = Field(
        ...,
        description="Final rendered text for the frame.",
        example="Douglas Adams was a British writer.",
    )
    sentences: List[str] = Field(
        default_factory=list,
        description=(
            "Sentence-level segmentation of `text`. "
            "May be empty if sentence splitting is not available."
        ),
        example=["Douglas Adams was a British writer."],
    )
    lang: str = Field(
        ...,
        description="Language actually used for generation (usually echoes the request lang).",
        example="en",
    )
    frame_type: str = Field(
        ...,
        description="Canonical frame_type of the input frame.",
        example="bio",
    )
    frame: Dict[str, Any] = Field(
        ...,
        description="Echo of the resolved frame used for generation (post-normalization).",
    )
    debug_info: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional implementation-specific debug information. "
            "Not guaranteed to be stable; consumers must treat as opaque."
        ),
    )


class GenericGenerateResponse(GenericGeneration):
    """
    Response model for the /generate endpoint.

    Currently identical to GenericGeneration, but kept as a separate type in
    case we want to attach top-level metadata (e.g. request_id) later.
    """

    pass


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------


class BatchGenericGenerateItemRequest(BaseModel):
    """
    Single item in a batch generation request.

    All items share the same target `lang`, but may have different frame types.
    """

    frame_type: str = Field(
        ...,
        description="Canonical frame_type string for this item.",
        example="bio",
    )
    frame: Dict[str, Any] = Field(
        ...,
        description=(
            "Frame payload for this item, normalized for the given frame_type."
        ),
    )
    options: Optional[GenerationOptions] = Field(
        None,
        description="Optional per-item generation options. Overrides batch-level defaults.",
    )


class BatchGenericGenerateRequest(BaseModel):
    """
    Batch variant of the generic generate API.

    Useful for rendering multiple frames to the same target language in one call.
    """

    lang: str = Field(
        ...,
        description="Target language for all items in the batch.",
        example="en",
    )
    items: List[BatchGenericGenerateItemRequest] = Field(
        ...,
        description="List of frames to generate.",
        min_items=1,
    )
    debug: bool = Field(
        False,
        description="If true, include debug_info for each item where available.",
    )


class BatchGenericGenerateItemResponse(BaseModel):
    """
    Generation result for a single item inside a batch response.
    """

    frame_type: str = Field(
        ...,
        description="Canonical frame_type string for this item.",
        example="bio",
    )
    frame: Dict[str, Any] = Field(
        ...,
        description="Echo of the frame payload used for generation.",
    )
    result: GenericGeneration = Field(
        ...,
        description="Structured generation result for this item.",
    )


class BatchGenericGenerateResponse(BaseModel):
    """
    Response for the batch generic generation endpoint.
    """

    lang: str = Field(
        ...,
        description="Target language used for batch generation.",
        example="en",
    )
    items: List[BatchGenericGenerateItemResponse] = Field(
        ...,
        description="Per-item generation results.",
    )
