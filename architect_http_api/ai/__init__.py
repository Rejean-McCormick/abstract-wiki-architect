"""
architect_http_api.ai

High-level AI orchestration entry points for the HTTP API.

This package hides the details of LLM / AI integration behind a small
set of pure-Python functions so that:

- Routers only depend on typed request/response models from
  `architect_http_api.schemas.ai`.
- Core NLG / frame logic stays independent of any particular AI backend.

The public surface here is intentionally small:

- `run_ai_command`      → interpret a free-text user command and return
                          frame patches + assistant messages.
- `run_suggestions`     → suggest missing / improved field values.
- `run_explanation`     → explain how a frame and a generated text relate.
"""

from __future__ import annotations

from typing import Sequence

from ..schemas.ai import (
    AICommandRequest,
    AICommandResponse,
    AISuggestionRequest,
    AISuggestionResponse,
    AIExplainRequest,
    AIExplainResponse,
    AIFramePatch,
    AIMessage,
)

from .intent_handler import interpret_command
from .suggestions import suggest_fields
from .explanations import explain_text


def run_ai_command(command: AICommandRequest) -> AICommandResponse:
    """
    Entry point used by the `/ai/command` router.

    Args:
        command: Parsed request model containing the user utterance and
                 optional context frames / entity-id.

    Returns:
        AICommandResponse with proposed frame patches and assistant messages.
    """
    patches, messages = interpret_command(command)
    # Normalise to sequences to keep the interface predictable.
    if not isinstance(patches, Sequence):
        raise TypeError("interpret_command() must return a sequence of AIFramePatch")
    if messages is None:
        messages = []

    # Let Pydantic handle validation / conversion on construction.
    return AICommandResponse(frame_patches=list(patches), messages=list(messages))


def run_suggestions(request: AISuggestionRequest) -> AISuggestionResponse:
    """
    Entry point used by the `/ai/suggest` router.

    Delegates to `suggest_fields` which encapsulates the actual AI logic.
    """
    suggestions = suggest_fields(request)
    return AISuggestionResponse(suggestions=suggestions)


def run_explanation(request: AIExplainRequest) -> AIExplainResponse:
    """
    Entry point used by the `/ai/explain` router.

    Delegates to `explain_text` which encapsulates the explanation logic.
    """
    explanation = explain_text(request)
    return AIExplainResponse(explanation=explanation)


__all__ = [
    "AICommandRequest",
    "AICommandResponse",
    "AISuggestionRequest",
    "AISuggestionResponse",
    "AIExplainRequest",
    "AIExplainResponse",
    "AIFramePatch",
    "AIMessage",
    "run_ai_command",
    "run_suggestions",
    "run_explanation",
]
