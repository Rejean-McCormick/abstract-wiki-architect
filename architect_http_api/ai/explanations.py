# architect_http_api/ai/explanations.py
"""
AI-powered explanations for NLG generations and frames.

This module is intentionally **LLM-agnostic**. It does not perform HTTP
requests or talk to any particular model vendor. Instead it:

* Defines small data structures that describe what we want explained.
* Builds structured prompts (system + user messages).
* Normalizes LLM JSON replies into a stable internal shape.

The actual model call is delegated to :mod:`architect_http_api.services.ai_client`
(or an equivalent service layer).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import json

from architect_http_api.services.ai_client import AIClient
from architect_http_api.schemas.ai import AIExplainRequest, AIExplainResponse


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


class ExplanationKind(str, Enum):
    """
    High-level categories for explanations.

    These are kept intentionally broad so that the frontend can group or
    color-code them without depending on model-specific wording.
    """

    GENERAL = "general"       # High-level summary / main takeaways
    COVERAGE = "coverage"     # What is covered, what is missing vs. frame
    STYLE = "style"           # Register, tone, length, fluency
    LINGUISTIC = "linguistic" # Morphology, agreement, word order, etc.
    DEBUG = "debug"           # Internal hints about engines, configs, fallbacks
    OTHER = "other"           # Catch-all / miscellaneous


@dataclass
class ExplanationContext:
    """
    Context for asking an LLM to explain a generation.
    """

    lang: str
    frame_type: str
    # The semantic frame as JSON (already normalized for the NLG core)
    frame_payload: Mapping[str, Any]
    # Final text produced by the NLG pipeline (what the user sees)
    generation_text: str
    # Optional NLG debug metadata
    debug_info: Optional[Mapping[str, Any]] = None
    # Optional natural-language goal from the user
    user_goal: Optional[str] = None


@dataclass
class ExplanationItem:
    """
    Normalized explanation unit.
    """

    kind: ExplanationKind
    title: str
    body: str
    score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a JSON-serializable dict.
        """
        data = asdict(self)
        # Enum to plain string
        data["kind"] = self.kind.value
        return data


# ---------------------------------------------------------------------------
# Engine & Entry Points (Added to fix ImportErrors)
# ---------------------------------------------------------------------------

class ExplanationEngine:
    """
    Service class to handle AI-powered explanations.
    Initialized with an AIClient by the router dependency injection.
    """
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client

    async def explain_field(self, request: AIExplainRequest) -> AIExplainResponse:
        """
        Main entry point for the /explain-field endpoint.
        """
        # In a real implementation, you would call self.ai_client.chat() here.
        # For now, we delegate to heuristic/mock logic.
        explanation_items = _heuristic_explain_text(request.frame, request.generation_text)
        
        # Convert internal ExplanationItem objects to the response format (dict)
        return AIExplainResponse(explanation=[item.to_dict() for item in explanation_items])


def explain_text(request: AIExplainRequest) -> List[Dict[str, Any]]:
    """
    Legacy/Standalone entry point matching the signature expected by __init__.py.
    """
    items = _heuristic_explain_text(request.frame, request.generation_text)
    return [item.to_dict() for item in items]


def _heuristic_explain_text(
    frame_payload: Dict[str, Any],
    generation_text: Optional[str] = None,
) -> List[ExplanationItem]:
    """
    Mock explanation logic until LLM integration is fully wired up.
    """
    items: List[ExplanationItem] = []

    # 1. General Overview
    items.append(
        ExplanationItem(
            kind=ExplanationKind.GENERAL,
            title="Overview",
            body="This text was generated based on the provided frame data using a standard template.",
            score=1.0
        )
    )

    # 2. Coverage Check
    if frame_payload:
        key_count = len(frame_payload.keys())
        items.append(
            ExplanationItem(
                kind=ExplanationKind.COVERAGE,
                title="Data Usage",
                body=f"The generator used {key_count} fields from your input frame configuration.",
                score=0.8
            )
        )

    # 3. Linguistic Note (Stub)
    if generation_text and len(generation_text) > 100:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.STYLE,
                title="Sentence Length",
                body="The output is quite long. Consider checking if it can be split into multiple sentences.",
                score=0.6
            )
        )

    return items


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _compact_json(data: Any) -> str:
    """Compact, stable JSON representation for prompt payloads."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def build_generation_explanations_prompt(
    ctx: ExplanationContext,
) -> Dict[str, str]:
    """
    Build system + user messages for asking an LLM to explain a generation.
    """
    system_prompt = (
        "You are an expert Natural Language Generation (NLG) architect. "
        "You help developers understand how a multilingual rule-based NLG "
        "pipeline produced its output.\n\n"
        "Respond STRICTLY as JSON."
    )

    user_payload: Dict[str, Any] = {
        "lang": ctx.lang,
        "frame_type": ctx.frame_type,
        "frame": ctx.frame_payload,
        "generation_text": ctx.generation_text,
    }

    if ctx.debug_info is not None:
        user_payload["debug_info"] = ctx.debug_info

    user_prompt = (
        f"Analyze this generation:\n{_compact_json(user_payload)}"
    )

    return {"system": system_prompt, "user": user_prompt}


# ---------------------------------------------------------------------------
# Normalization of LLM output
# ---------------------------------------------------------------------------


def _coerce_kind(value: Any) -> ExplanationKind:
    """
    Convert an arbitrary 'kind' field into a valid ExplanationKind.
    """
    if isinstance(value, ExplanationKind):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        for k in ExplanationKind:
            if k.value == normalized:
                return k

    return ExplanationKind.OTHER


def normalize_explanations(raw: Any) -> List[ExplanationItem]:
    """
    Normalize a raw JSON-like object from the LLM into ExplanationItem objects.
    """
    if raw is None:
        return []

    if isinstance(raw, Mapping):
        items: Iterable[Any] = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        items = raw
    else:
        return []

    explanations: List[ExplanationItem] = []

    for entry in items:
        if not isinstance(entry, Mapping):
            continue

        title = str(entry.get("title", "")).strip()
        body = str(entry.get("body", "")).strip()

        if not title and not body:
            continue

        kind_value = entry.get("kind", ExplanationKind.GENERAL.value)
        kind = _coerce_kind(kind_value)

        score_raw = entry.get("score")
        score: Optional[float]
        try:
            score = float(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            score = None

        explanations.append(
            ExplanationItem(
                kind=kind,
                title=title or "Explanation",
                body=body,
                score=score,
            )
        )

    return explanations


# ---------------------------------------------------------------------------
# Convenience helpers for service / router layers
# ---------------------------------------------------------------------------


def explanations_to_response_payload(
    explanations: Sequence[ExplanationItem],
) -> List[Dict[str, Any]]:
    """
    Convert a list of ExplanationItem objects into a JSON-serializable payload.
    """
    return [item.to_dict() for item in explanations]


__all__ = [
    "ExplanationKind",
    "ExplanationContext",
    "ExplanationItem",
    "ExplanationEngine",
    "explain_text",
    "build_generation_explanations_prompt",
    "normalize_explanations",
    "explanations_to_response_payload",
]