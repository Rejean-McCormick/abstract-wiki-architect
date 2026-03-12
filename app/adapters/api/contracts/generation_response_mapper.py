from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    """
    Read a field from either a dict-like object or an attribute-bearing object.
    """
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _coerce_debug_info(value: Any) -> dict[str, Any]:
    """
    Normalize debug_info into a plain JSON-friendly dict.
    """
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return dict(value)

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, Mapping):
                return dict(dumped)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            raw = vars(value)
            if isinstance(raw, Mapping):
                return dict(raw)
        except Exception:
            pass

    return {"raw_debug_info": str(value)}


def map_generation_response(result: Any, *, requested_lang_code: str | None = None) -> dict[str, Any]:
    """
    Map a domain/use-case generation result into the public API response shape.

    Public contract:
        {
            "text": "...",
            "lang_code": "en",
            "debug_info": {...}
        }

    Accepts:
    - Sentence-like objects exposing attributes such as `.text`, `.lang_code`,
      `.debug_info`, `.generation_time_ms`
    - dict-like results with equivalent keys
    - raw string results (best-effort compatibility)

    Raises:
        ValueError: when required response fields cannot be derived.
    """
    if result is None:
        raise ValueError("Generation result cannot be None.")

    text = _get_value(result, "text")
    if text is None and isinstance(result, str):
        text = result

    text = "" if text is None else str(text).strip()
    if not text:
        raise ValueError("Generation result is missing required field 'text'.")

    lang_code = _get_value(result, "lang_code", requested_lang_code)
    if not lang_code:
        lang_code = _get_value(result, "language", requested_lang_code)

    lang_code = "" if lang_code is None else str(lang_code).strip()
    if not lang_code:
        raise ValueError("Generation result is missing required field 'lang_code'.")

    debug_info = _coerce_debug_info(_get_value(result, "debug_info"))

    # Preserve important runtime metadata when it exists outside debug_info.
    promoted_keys = (
        "construction_id",
        "renderer_backend",
        "fallback_used",
        "selected_backend",
        "attempted_backends",
        "tokens",
    )
    for key in promoted_keys:
        value = _get_value(result, key, None)
        if value is not None and key not in debug_info:
            debug_info[key] = value

    generation_time_ms = _get_value(result, "generation_time_ms", None)
    if generation_time_ms is not None and "generation_time_ms" not in debug_info:
        debug_info["generation_time_ms"] = generation_time_ms

    # Keep shared contract metadata stable and explicit.
    debug_info.setdefault("lang_code", lang_code)

    resolved_language = _get_value(result, "language", None)
    if resolved_language and "resolved_language" not in debug_info:
        debug_info["resolved_language"] = str(resolved_language)

    return {
        "text": text,
        "lang_code": lang_code,
        "debug_info": debug_info,
    }


# Small aliases so router code can read naturally during Batch 3 refactor.
to_generation_response = map_generation_response
generation_response_to_dict = map_generation_response


__all__ = [
    "map_generation_response",
    "to_generation_response",
    "generation_response_to_dict",
]