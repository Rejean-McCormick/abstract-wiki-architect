"""
architect_http_api/ai/frame_builder.py

Helpers for turning AI-suggested field values into concrete frame payloads
that the HTTP API can persist and send to the NLG backend.

The goal of this module is deliberately narrow:

* Start from:
    - a `FrameMetadata` description (fields, types, required flags),
    - an optional existing frame dict (from the DB),
    - a flat mapping of AI-proposed updates (`{field_name: value, ...}`),
* Return a normalized frame dict plus bookkeeping about:
    - which required fields are still missing,
    - which updates were ignored or coerced.

This keeps all frame-shape knowledge in the registry / metadata layer and
keeps the AI integration focused on *semantics*, not JSON minutiae.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

try:  # Soft import so this file is importable even before schemas are wired.
    from architect_http_api.schemas.frames_metadata import FrameMetadata, FrameFieldMetadata
except Exception:  # pragma: no cover
    FrameMetadata = Any  # type: ignore[assignment]
    FrameFieldMetadata = Any  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------


@dataclass
class FrameBuildResult:
    """
    Result of building a frame from metadata + updates.

    Attributes
    ----------
    frame_type:
        Canonical frame_type for routing (`"bio"`, `"entity.person"`, etc.).
    frame:
        JSON-serializable dict ready to store or send to the NLG API.
    missing_required:
        Names of fields that are marked as required in metadata but still
        effectively empty after applying updates.
    warnings:
        Human-readable notes about discarded keys, type coercion issues, etc.
    """

    frame_type: str
    frame: Dict[str, Any]
    missing_required: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_fields(meta: FrameMetadata) -> Iterable[FrameFieldMetadata]:
    """Yield field metadata items from a FrameMetadata-like object."""
    fields = getattr(meta, "fields", None)
    if fields is None and isinstance(meta, Mapping):
        fields = meta.get("fields", [])

    return fields or []


def _field_name(field_meta: FrameFieldMetadata) -> str:
    if hasattr(field_meta, "name"):
        return field_meta.name  # type: ignore[no-any-return]
    if isinstance(field_meta, Mapping):
        return str(field_meta.get("name", ""))
    return ""


def _field_kind(field_meta: FrameFieldMetadata) -> str:
    if hasattr(field_meta, "kind"):
        return str(field_meta.kind)  # type: ignore[no-any-return]
    if isinstance(field_meta, Mapping):
        return str(field_meta.get("kind", "string"))
    return "string"


def _field_required(field_meta: FrameFieldMetadata) -> bool:
    if hasattr(field_meta, "required"):
        return bool(field_meta.required)  # type: ignore[no-any-return]
    if isinstance(field_meta, Mapping):
        return bool(field_meta.get("required", False))
    return False


def _field_is_list(field_meta: FrameFieldMetadata) -> bool:
    # Two common encodings:
    # - explicit `is_list: bool`
    # - list-y kinds like "string_list", "entity_list"
    if hasattr(field_meta, "is_list"):
        return bool(field_meta.is_list)  # type: ignore[no-any-return]

    if isinstance(field_meta, Mapping):
        if field_meta.get("is_list") is True:
            return True
        kind = str(field_meta.get("kind", ""))
        return kind.endswith("_list")

    return False


def _field_default(field_meta: FrameFieldMetadata) -> Any:
    if hasattr(field_meta, "default"):
        return getattr(field_meta, "default")  # type: ignore[no-any-return]
    if isinstance(field_meta, Mapping) and "default" in field_meta:
        return field_meta["default"]
    return None


def _coerce_scalar(value: Any, kind: str) -> Any:
    """
    Best-effort scalar coercion based on a simple `kind` string.

    This is intentionally conservative and never raises on bad data; instead,
    it returns the original value so that upstream layers can decide what to do.
    """
    if value is None:
        return None

    # Normalized kind
    k = kind.lower()

    if k in {"string", "multiline", "text"}:
        if isinstance(value, str):
            return value
        return str(value)

    if k in {"number", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    if k in {"int", "integer"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            # Fall back to float if possible, else leave as-is
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return value

    if k in {"bool", "boolean"}:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "yes", "y", "1", "on"}:
                return True
            if v in {"false", "no", "n", "0", "off"}:
                return False
        return value

    # Entity / JSON-ish kinds – we do not coerce aggressively.
    # The caller may pass dicts or strings; we preserve structure.
    return value


def _coerce_value_for_field(value: Any, field_meta: FrameFieldMetadata) -> Any:
    """Apply list + scalar coercions according to metadata."""
    kind = _field_kind(field_meta)
    is_list = _field_is_list(field_meta)

    if is_list:
        # If already a list/tuple, coerce each element.
        if isinstance(value, (list, tuple)):
            return [_coerce_scalar(v, kind) for v in value]
        # Treat comma-separated strings as multiple entries for simple string kinds.
        if isinstance(value, str) and kind.startswith("string"):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [_coerce_scalar(p, kind) for p in parts]
        # Otherwise, wrap single value.
        return [_coerce_scalar(value, kind)]

    # Not a list field
    return _coerce_scalar(value, kind)


def _set_dotted(target: MutableMapping[str, Any], dotted_key: str, value: Any) -> None:
    """
    Set `target["a"]["b"]["c"] = value` given "a.b.c", creating intermediate
    dicts as needed.
    """
    parts = dotted_key.split(".")
    if not parts:
        return

    cur: MutableMapping[str, Any] = target
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _is_effectively_empty(value: Any) -> bool:
    """Heuristic emptiness check for detecting missing required fields."""
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def initialise_frame(
    metadata: FrameMetadata,
    *,
    base: Optional[Dict[str, Any]] = None,
    initialise_collections: bool = True,
) -> Dict[str, Any]:
    """
    Create a new frame dict initialized from metadata and an optional base.

    Parameters
    ----------
    metadata:
        FrameMetadata object describing fields for this frame_type.
    base:
        Optional existing frame dict to start from (e.g. loaded from DB).
    initialise_collections:
        If True, list-like fields are initialised to `[]` when no base/default
        is present; otherwise they are left unset.

    Returns
    -------
    dict
        A shallow dict with at least a `frame_type` key and any defaults
        defined in metadata applied.
    """
    # Start from a shallow copy of the base dict, if provided.
    frame: Dict[str, Any] = dict(base or {})

    # Ensure frame_type is set from metadata if possible.
    frame_type = getattr(metadata, "frame_type", None)
    if frame_type is None and isinstance(metadata, Mapping):
        frame_type = metadata.get("frame_type")
    if frame_type:
        frame["frame_type"] = frame_type

    # Apply per-field defaults / collection initialisation.
    for field_meta in _iter_fields(metadata):
        name = _field_name(field_meta)
        if not name:
            continue

        if name in frame:
            # Existing value (from base) wins over defaults.
            continue

        default = _field_default(field_meta)
        if default is not None:
            frame[name] = default
            continue

        if initialise_collections and _field_is_list(field_meta):
            frame[name] = []

    return frame


def apply_updates(
    frame: Dict[str, Any],
    metadata: FrameMetadata,
    updates: Mapping[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Apply AI-suggested updates to a frame dict, respecting metadata.

    Unknown fields are ignored and reported in the warnings list.

    Parameters
    ----------
    frame:
        The frame dict to mutate (usually from `initialise_frame`).
    metadata:
        FrameMetadata describing allowed fields.
    updates:
        Mapping from field-name (optionally dotted, e.g. "time.start_year")
        to raw values.

    Returns
    -------
    (frame, warnings)
        The same dict instance (for convenience) plus a list of warnings.
    """
    warnings: List[str] = []

    # Index metadata by field name for quick lookup.
    field_by_name: Dict[str, FrameFieldMetadata] = {}
    for fmeta in _iter_fields(metadata):
        name = _field_name(fmeta)
        if name:
            field_by_name[name] = fmeta

    for raw_key, raw_value in updates.items():
        if not isinstance(raw_key, str) or not raw_key:
            warnings.append(f"Ignored update with non-string key: {raw_key!r}")
            continue

        root_name = raw_key.split(".", 1)[0]
        field_meta = field_by_name.get(root_name)
        if field_meta is None:
            warnings.append(f"Ignored unknown field '{raw_key}' (root '{root_name}')")
            continue

        coerced = _coerce_value_for_field(raw_value, field_meta)

        # If the key is dotted, we treat it as a nested path; otherwise top-level.
        if "." in raw_key:
            _set_dotted(frame, raw_key, coerced)
        else:
            frame[raw_key] = coerced

    return frame, warnings


def build_frame(
    metadata: FrameMetadata,
    updates: Mapping[str, Any],
    *,
    base: Optional[Dict[str, Any]] = None,
    enforce_required: bool = False,
) -> FrameBuildResult:
    """
    High-level helper: initialise a frame, apply updates, and report status.

    This is the main entry point used by the AI intent handler:

        1. Look up FrameMetadata for a given frame_type.
        2. Call `build_frame(metadata, updates, base=existing_frame)`.
        3. Persist the returned `frame` and/or send it to `generate`.

    Parameters
    ----------
    metadata:
        FrameMetadata instance from the registry.
    updates:
        Mapping produced by the AI layer (or frontend) with proposed
        field values.
    base:
        Optional starting frame dict (e.g. from DB).
    enforce_required:
        If True, `missing_required` will be populated using the metadata’s
        `required` flags and the current frame content.

    Returns
    -------
    FrameBuildResult
        Structured result including the final frame and diagnostics.
    """
    frame = initialise_frame(metadata, base=base)
    frame, warnings = apply_updates(frame, metadata, updates)

    # Detect missing required fields.
    missing_required: List[str] = []
    if enforce_required:
        for fmeta in _iter_fields(metadata):
            name = _field_name(fmeta)
            if not name:
                continue
            if not _field_required(fmeta):
                continue

            value = frame.get(name)
            if _is_effectively_empty(value):
                missing_required.append(name)

    # Derive frame_type from metadata or the frame itself.
    frame_type = getattr(metadata, "frame_type", None)
    if frame_type is None and isinstance(metadata, Mapping):
        frame_type = metadata.get("frame_type")
    if frame_type is None:
        frame_type = str(frame.get("frame_type", ""))

    return FrameBuildResult(
        frame_type=frame_type,
        frame=frame,
        missing_required=missing_required,
        warnings=warnings,
    )
