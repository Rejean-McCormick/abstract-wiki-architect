# architect_http_api/ai/explanations.py
"""
AI-powered explanations for NLG generations and frames.

This module is intentionally **LLM-agnostic**. It does not perform HTTP
requests or talk to any particular model vendor. Instead it:

* Defines small data structures that describe what we want explained.
* Builds structured prompts (system + user messages).
* Normalizes LLM JSON replies into a stable internal shape.

The actual model call is delegated to :mod:`architect_http_api.services.ai_client`
(or an equivalent service layer). That service is expected to:

    1. Call :func:`build_generation_explanations_prompt`.
    2. Send the messages to an LLM as a chat / completion.
    3. Parse the LLM output as JSON.
    4. Pass the parsed object to :func:`normalize_explanations`.

The frontend (AIPanel, inspectors, etc.) should see a simple list of
explanations with a small, stable schema:

    {
      "kind": "coverage" | "style" | "linguistic" | "debug" | "other",
      "title": "Short title",
      "body": "Longer explanation paragraph(s)."
    }

Nothing in this file depends on FastAPI, Pydantic, or the NLG core.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import json


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

    This is deliberately close to what the frontend knows:
    * a raw JSON frame,
    * the generation result text,
    * optional debug info from the NLG stack.
    """

    lang: str
    frame_type: str

    # The semantic frame as JSON (already normalized for the NLG core)
    frame_payload: Mapping[str, Any]

    # Final text produced by the NLG pipeline (what the user sees)
    generation_text: str

    # Optional NLG debug metadata (router decisions, engine names, etc.)
    debug_info: Optional[Mapping[str, Any]] = None

    # Optional natural-language goal from the user
    user_goal: Optional[str] = None


@dataclass
class ExplanationItem:
    """
    Normalized explanation unit.

    This is what downstream layers (services, routers, frontend) should use.
    """

    kind: ExplanationKind
    title: str
    body: str

    # Optional numeric score indicating usefulness / importance.
    # Not required; mostly here to make future ranking logic easier.
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
# Prompt construction
# ---------------------------------------------------------------------------


def _compact_json(data: Any) -> str:
    """
    Compact, stable JSON representation for prompt payloads.

    We use a consistent style (sorted keys, no extra spaces) to:
    * minimize token usage,
    * make tests deterministic.
    """
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def build_generation_explanations_prompt(
    ctx: ExplanationContext,
) -> Dict[str, str]:
    """
    Build system + user messages for asking an LLM to explain a generation.

    Returns a dict with two keys:

        {
          "system": "<system prompt>",
          "user": "<user content>"
        }

    The AI client is expected to wrap this into the concrete chat/completion
    payload for a specific model provider.
    """
    system_prompt = (
        "You are an expert Natural Language Generation (NLG) architect. "
        "You help developers understand how a multilingual rule-based NLG "
        "pipeline produced its output.\n\n"
        "You will receive:\n"
        "  - the target language code,\n"
        "  - a semantic frame (JSON),\n"
        "  - the final generated text, and optionally\n"
        "  - internal debug metadata.\n\n"
        "Your job is to produce a small list of explanations that:\n"
        "  1) Describe what the sentence is doing structurally,\n"
        "  2) Highlight how the frame fields map into the text,\n"
        "  3) Comment on style / register if relevant,\n"
        "  4) Mention any obvious gaps or improvements.\n\n"
        "Respond STRICTLY as JSON, with no extra commentary, in this form:\n"
        "[\n"
        "  {\n"
        "    \"kind\": \"general\" | \"coverage\" | \"style\" | \"linguistic\" | \"debug\" | \"other\",\n"
        "    \"title\": \"Short title (max 80 chars)\",\n"
        "    \"body\": \"One or more sentences explaining this point.\",\n"
        "    \"score\": 0.0-1.0 optional numeric importance\n"
        "  },\n"
        "  ...\n"
        "]"
    )

    user_payload: Dict[str, Any] = {
        "lang": ctx.lang,
        "frame_type": ctx.frame_type,
        "frame": ctx.frame_payload,
        "generation_text": ctx.generation_text,
    }

    if ctx.debug_info is not None:
        user_payload["debug_info"] = ctx.debug_info

    if ctx.user_goal:
        user_payload["user_goal"] = ctx.user_goal

    user_prompt = (
        "Here is the context for explanation:\n\n"
        f"LANG:\n{ctx.lang}\n\n"
        f"FRAME_TYPE:\n{ctx.frame_type}\n\n"
        f"FRAME (JSON):\n{_compact_json(ctx.frame_payload)}\n\n"
        f"GENERATION_TEXT:\n{ctx.generation_text}\n"
    )

    if ctx.debug_info:
        user_prompt += "\nDEBUG_INFO (JSON):\n" + _compact_json(ctx.debug_info)

    if ctx.user_goal:
        user_prompt += "\n\nUSER_GOAL (optional, natural language):\n" + ctx.user_goal

    user_prompt += (
        "\n\nTask: produce a concise list of explanations in the strict JSON "
        "format described in the system prompt."
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

    # Fallback if the model invents a new label
    return ExplanationKind.OTHER


def normalize_explanations(raw: Any) -> List[ExplanationItem]:
    """
    Normalize a raw JSON-like object from the LLM into ExplanationItem objects.

    Expected inputs:

        * A list of dicts with keys 'kind', 'title', 'body', optional 'score'.
        * Or a single dict (will be wrapped in a list).

    Any malformed entries are ignored rather than raising, so the HTTP layer
    can safely return partial results instead of failing the whole request.
    """
    if raw is None:
        return []

    if isinstance(raw, Mapping):
        items: Iterable[Any] = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        items = raw
    else:
        # Completely unexpected shape
        return []

    explanations: List[ExplanationItem] = []

    for entry in items:
        if not isinstance(entry, Mapping):
            continue

        title = str(entry.get("title", "")).strip()
        body = str(entry.get("body", "")).strip()

        if not title and not body:
            # Skip empty explanations
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
    Convert a list of ExplanationItem objects into a JSON-serializable payload
    suitable for FastAPI responses or Pydantic models.

    This keeps the HTTP layer thin; routers can simply do:

        payload = explanations_to_response_payload(items)
        return {"explanations": payload}
    """
    return [item.to_dict() for item in explanations]


__all__ = [
    "ExplanationKind",
    "ExplanationContext",
    "ExplanationItem",
    "build_generation_explanations_prompt",
    "normalize_explanations",
    "explanations_to_response_payload",
]
