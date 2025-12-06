# architect_http_api/schemas/common.py

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from pydantic import BaseModel, Field, conint, constr


# ---------------------------------------------------------------------------
# Base / shared types
# ---------------------------------------------------------------------------


class APIModel(BaseModel):
    """
    Base Pydantic model for all HTTP API schemas.

    Common config:
    - forbid extra fields so the frontend gets early feedback on mistakes
    - allow_population_by_field_name to make future renames easier
    """

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True
        orm_mode = True


# BCP-47-ish language code ("en", "fr", "de", "pt-BR", etc.)
LangCode = constr(
    min_length=2,
    max_length=32,
    regex=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]+)*$",
)


PositiveInt = conint(ge=1)


JsonObject = Dict[str, Any]


# ---------------------------------------------------------------------------
# Generation options / result (HTTP-facing mirror of nlg.api)
# ---------------------------------------------------------------------------


class GenerationOptionsModel(APIModel):
    """
    HTTP representation of `nlg.api.GenerationOptions`.

    All fields are optional; omitted values fall back to engine defaults.
    """

    register: Optional[str] = Field(
        default=None,
        description='Stylistic register, e.g. "neutral", "formal", "informal".',
    )
    max_sentences: Optional[PositiveInt] = Field(
        default=None,
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


class GenerationResultModel(APIModel):
    """
    HTTP representation of `nlg.api.GenerationResult`.

    `frame` is serialized as plain JSON; individual endpoints may provide
    more specific typing for their particular frame shapes.
    """

    text: str = Field(
        ...,
        description="Final realized text.",
    )
    sentences: list[str] = Field(
        default_factory=list,
        description="Optional sentence-level split of `text`.",
    )
    lang: LangCode = Field(
        ...,
        description="Language code actually used for generation.",
    )
    frame: JsonObject = Field(
        ...,
        description="Original input frame as JSON.",
    )
    debug_info: Optional[JsonObject] = Field(
        default=None,
        description="Optional implementation-specific debug payload.",
    )


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class ErrorDetail(APIModel):
    """
    Machine- and human-readable error description.
    """

    code: str = Field(
        ...,
        description="Stable, machine-readable error code (e.g. 'invalid_frame').",
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error.",
    )
    details: Optional[Mapping[str, Any]] = Field(
        default=None,
        description="Optional structured details (field errors, etc.).",
    )


class ErrorResponse(APIModel):
    """
    Standard error envelope for all endpoints.
    """

    error: ErrorDetail


__all__ = [
    "APIModel",
    "LangCode",
    "PositiveInt",
    "JsonObject",
    "GenerationOptionsModel",
    "GenerationResultModel",
    "ErrorDetail",
    "ErrorResponse",
]
