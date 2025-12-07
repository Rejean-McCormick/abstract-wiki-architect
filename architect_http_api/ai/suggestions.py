# architect_http_api/ai/suggestions.py

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

from architect_http_api.services.ai_client import AIClient
from architect_http_api.schemas.ai import AISuggestFieldsRequest, AISuggestFieldsResponse

@dataclass
class Suggestion:
    """
    Backend-agnostic suggestion object.

    This is intentionally simple so it can be:
    - returned directly as JSON, or
    - converted into Pydantic models in `schemas/ai.py`.
    """

    id: str
    title: str
    description: str

    # What the suggestion is primarily about
    category: str = "frame"  # e.g. "frame", "style", "metadata"

    # Optional target within the frame/options payload
    target_field: Optional[str] = None  # e.g. "birth_event.time", "options.max_sentences"

    # Optional patch describing a concrete change to apply if the user accepts
    # (shape is intentionally loose to keep this module decoupled)
    patch: Optional[Dict[str, Any]] = None

    # Optional numeric score in [0, 1], higher = more important
    score: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SuggestionsEngine:
    """
    Service class to handle AI-powered field suggestions.
    Initialized with an AIClient by the router dependency injection.
    """
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client

    async def suggest_fields(self, request: AISuggestFieldsRequest) -> AISuggestFieldsResponse:
        """
        Main entry point for the /suggest-fields endpoint.
        """
        # In a real implementation, you would call self.ai_client.chat() here
        # to get suggestions from an LLM.
        # For now, we delegate to the heuristic logic below.
        
        # We mock metadata lookup for now or pass None if unavailable contextually
        suggestions = _heuristic_suggest_fields(None, request.current_payload)
        
        # Convert internal Suggestion objects to the response format (dict)
        return AISuggestFieldsResponse(suggestions=[s.to_dict() for s in suggestions])


def generate_suggestions(
    frame_metadata: Any,
    payload: Dict[str, Any],
    *,
    last_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compute high-level suggestions for the current frame + generation result.
    Legacy/Direct function.
    """
    suggestions = _heuristic_suggest_fields(frame_metadata, payload, last_text)
    return [s.to_dict() for s in suggestions]


# Alias for __init__.py compatibility
def suggest_fields(request: AISuggestFieldsRequest) -> List[Dict[str, Any]]:
    """
    Compatibility wrapper for __init__.py which expects a function named `suggest_fields`.
    """
    # This matches the signature expected by run_suggestions in __init__.py
    suggestions = _heuristic_suggest_fields(None, request.current_payload)
    return [s.to_dict() for s in suggestions]


# ---------------------------------------------------------------------------
# Internal Logic (Heuristics)
# ---------------------------------------------------------------------------

def _heuristic_suggest_fields(
    frame_metadata: Any,
    payload: Dict[str, Any],
    last_text: Optional[str] = None,
) -> List[Suggestion]:
    """
    Core logic extracted from generate_suggestions to be reusable.
    """
    suggestions: List[Suggestion] = []

    if frame_metadata:
        suggestions.extend(_missing_required_field_suggestions(frame_metadata, payload))
        suggestions.extend(_missing_recommended_field_suggestions(frame_metadata, payload))
    
    # Check style
    suggestions.extend(_style_suggestions(last_text))

    suggestions = _deduplicate_suggestions(suggestions)
    return suggestions


# ---------------------------------------------------------------------------
# Field-level heuristics (Rest of your original code below)
# ---------------------------------------------------------------------------


def _missing_required_field_suggestions(
    frame_metadata: Any, payload: Dict[str, Any]
) -> List[Suggestion]:
    out: List[Suggestion] = []

    for f in _iter_fields(frame_metadata):
        name = f.get("name")
        if not name:
            continue

        if not f.get("required", False):
            continue

        value = _get_payload_value(payload, name)
        if not _is_empty(value):
            continue

        label = f.get("label") or name.replace("_", " ").capitalize()
        desc = f.get("description") or f"Fill in the required field: {label}."

        out.append(
            Suggestion(
                id=f"missing-required:{name}",
                title=f"Add {label}",
                description=desc,
                category="frame",
                target_field=name,
                patch=None,  # UI can just focus the field
                score=0.95,
            )
        )

    return out


def _missing_recommended_field_suggestions(
    frame_metadata: Any, payload: Dict[str, Any]
) -> List[Suggestion]:
    """
    Heuristics for "nice to have" fields, to keep this app-wide and not just bio.
    """
    out: List[Suggestion] = []

    for f in _iter_fields(frame_metadata):
        name = f.get("name")
        if not name:
            continue

        # Skip required fields (handled above)
        if f.get("required", False):
            continue

        # Infer "importance" from explicit flag or from naming conventions
        importance = f.get("importance")
        label = (f.get("label") or name).strip()
        desc = f.get("description")

        # Strong hint that this field materially improves text quality
        is_semantic_core = _looks_semantic_core(name, label)

        if not (is_semantic_core or (importance and str(importance) in {"high", "core"})):
            continue

        value = _get_payload_value(payload, name)
        if not _is_empty(value):
            continue

        if not desc:
            desc = f"Adding {label} will make the generated text richer and more precise."

        out.append(
            Suggestion(
                id=f"missing-recommended:{name}",
                title=f"Enrich with {label}",
                description=desc,
                category="frame",
                target_field=name,
                patch=None,
                score=0.75,
            )
        )

    return out


def _looks_semantic_core(field_name: str, label: str) -> bool:
    """
    Very light heuristic to guess that a field is semantically important.
    Works across many frame types (bio, event, meta, narrative, etc.).
    """
    name_l = field_name.lower()
    label_l = label.lower()

    semantic_keywords = [
        "summary",
        "short_description",
        "lead",
        "overview",
        "headline",
        "title",
        "subject",
        "event_type",
        "time",
        "date",
        "location",
        "participants",
        "main_entity",
        "statement",
        "claim",
        "sources",
        "impact",
        "development",
    ]

    text_keywords = [
        "intro",
        "lead_paragraph",
        "section_summary",
        "abstract",
    ]

    tokens = name_l + " " + label_l

    return any(k in tokens for k in semantic_keywords + text_keywords)


# ---------------------------------------------------------------------------
# Style / length heuristics based on the last generated text
# ---------------------------------------------------------------------------


def _style_suggestions(last_text: Optional[str]) -> List[Suggestion]:
    if not last_text:
        return []

    text = last_text.strip()
    if not text:
        return []

    length = len(text)

    out: List[Suggestion] = []

    # Absolute character length thresholds; we intentionally avoid any NLP here.
    if length > 900:
        out.append(
            Suggestion(
                id="style:shorter",
                title="Make it shorter",
                description=(
                    "Use fewer sentences or a more compact summary. "
                    "This typically maps to a lower `max_sentences` option."
                ),
                category="style",
                target_field="options.max_sentences",
                patch={
                    "options": {
                        # The router/schemas can clamp/interpret this; it's a hint.
                        "max_sentences": 2
                    }
                },
                score=0.9,
            )
        )
    elif length < 250:
        out.append(
            Suggestion(
                id="style:more-detail",
                title="Add more detail",
                description=(
                    "Expand the text with more context and supporting facts. "
                    "This typically maps to a higher `max_sentences` option."
                ),
                category="style",
                target_field="options.max_sentences",
                patch={"options": {"max_sentences": 4}},
                score=0.7,
            )
        )

    # Tone suggestions; these don't inspect the text, they just expose options.
    out.append(
        Suggestion(
            id="style:more-formal",
            title="More formal tone",
            description="Switch to a more formal register (e.g. for encyclopedia-style text).",
            category="style",
            target_field="options.register",
            patch={"options": {"register": "formal"}},
            score=0.6,
        )
    )
    out.append(
        Suggestion(
            id="style:more-neutral",
            title="More neutral tone",
            description="Use a neutral, factual tone; useful for contentious or sensitive topics.",
            category="style",
            target_field="options.register",
            patch={"options": {"register": "neutral"}},
            score=0.6,
        )
    )

    return out


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _iter_fields(frame_metadata: Any) -> Iterable[Dict[str, Any]]:
    """
    Normalize `frame_metadata.fields` into simple dicts.

    Supports both:
    - list[dict] with the right keys, or
    - list[objects] with attributes (`name`, `label`, `description`, `required`, `importance`, ...).
    """
    fields = getattr(frame_metadata, "fields", None)
    if not fields:
        return []

    normalized: List[Dict[str, Any]] = []

    for raw in fields:
        if isinstance(raw, dict):
            normalized.append(raw)
            continue

        # Generic object -> dict adapter
        normalized.append(
            {
                "name": getattr(raw, "name", None)
                or getattr(raw, "id", None),
                "label": getattr(raw, "label", None)
                or getattr(raw, "title", None),
                "description": getattr(raw, "description", None),
                "required": getattr(raw, "required", False),
                "importance": getattr(raw, "importance", None),
            }
        )

    return normalized


def _get_payload_value(payload: Dict[str, Any], field_path: str) -> Any:
    """
    Resolve a dotted field path against the payload dict.

    Example:
        payload = {"birth_event": {"time": {"year": 1870}}}
        _get_payload_value(payload, "birth_event.time.year") -> 1870
    """
    parts = field_path.split(".")
    current: Any = payload

    for part in parts:
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]

    return current


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _deduplicate_suggestions(suggestions: List[Suggestion]) -> List[Suggestion]:
    """
    Deduplicate by (id, target_field). If duplicates exist, keep the one with higher score.
    """
    seen: Dict[tuple, Suggestion] = {}

    for s in suggestions:
        key = (s.id, s.target_field)
        existing = seen.get(key)
        if existing is None or s.score > existing.score:
            seen[key] = s

    # Sort by descending score for a nicer default ordering
    return sorted(seen.values(), key=lambda s: s.score, reverse=True)