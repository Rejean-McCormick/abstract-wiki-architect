# app/adapters/persistence/lexicon/entity_resolution.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional

from . import lookup_lemma, lookup_qid
from .types import Lexeme

__all__ = [
    "EntityRef",
    "EntityResolutionResult",
    "resolve_entity",
    "resolve_entity_slots",
]


# ---------------------------------------------------------------------------
# Public result models
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EntityRef:
    """
    Normalized runtime entity reference.

    This is the entity-side counterpart to lexeme-oriented references used by
    the lexical resolution layer. It is intentionally lightweight and keeps
    fallback metadata visible.

    Notes:
    - `qid` is the preferred stable external identity when available.
    - `entity_id` may carry an internal ID or a non-QID stable identifier.
    - `lemma` is the lexicon/native label when resolved through the lexicon.
    - `label` is always safe to surface as a human-readable fallback.
    """

    label: str
    lang_code: str

    qid: Optional[str] = None
    entity_id: Optional[str] = None

    lemma: Optional[str] = None
    pos: Optional[str] = None

    provenance: str = "unresolved"
    confidence: float = 0.0
    fallback_used: bool = False

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "lang_code": self.lang_code,
            "qid": self.qid,
            "entity_id": self.entity_id,
            "lemma": self.lemma,
            "pos": self.pos,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class EntityResolutionResult:
    """
    Per-slot entity resolution outcome.

    This object is suitable for a later lexical_resolution.py layer to convert
    into `lexical_bindings` while preserving slot-level provenance and fallback.
    """

    slot_name: Optional[str]
    input_value: Any

    ref: Optional[EntityRef]
    matched: bool

    provenance: str
    confidence: float

    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_name": self.slot_name,
            "input_value": self.input_value,
            "matched": self.matched,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "ref": self.ref.to_dict() if self.ref is not None else None,
            "debug": dict(self.debug),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_entity(
    value: Any,
    *,
    lang_code: str,
    slot_name: Optional[str] = None,
    allow_raw_fallback: bool = True,
) -> EntityResolutionResult:
    """
    Resolve one entity-like slot value against the lexicon layer.

    Resolution order:
    1. Stable/canonical ID lookup (QID / entity ID that looks like a QID)
    2. Lemma / label lookup in the target language
    3. Explicit raw-string fallback, if allowed

    Accepted input shapes:
    - "Q90"
    - "Paris"
    - {"qid": "Q90", "label": "Paris"}
    - {"name": "Paris"}
    - {"entity_id": "Q90"}
    """

    raw = _coerce_mapping(value)

    qid = _extract_qid(value, raw)
    entity_id = _extract_entity_id(raw, qid=qid)
    label = _extract_label(value, raw)
    aliases = _extract_aliases(raw)

    # 1) Canonical / stable ID path
    if qid:
        lexeme = _safe_lookup_qid(lang_code=lang_code, qid=qid)
        if lexeme is not None:
            ref = _entity_ref_from_lexeme(
                lexeme,
                lang_code=lang_code,
                label_hint=label or qid,
                qid_hint=qid,
                entity_id_hint=entity_id,
                provenance="canonical_id_match",
                confidence=1.0,
                fallback_used=False,
            )
            return EntityResolutionResult(
                slot_name=slot_name,
                input_value=value,
                ref=ref,
                matched=True,
                provenance=ref.provenance,
                confidence=ref.confidence,
                fallback_used=False,
                debug={
                    "resolution_path": "qid",
                    "requested_qid": qid,
                },
            )

    # 2) Lemma / label path
    candidate_labels = [c for c in [label, *aliases] if c]
    for candidate in _dedupe_preserve_order(candidate_labels):
        lexeme = _safe_lookup_entity_lemma(lang_code=lang_code, label=candidate)
        if lexeme is not None:
            ref = _entity_ref_from_lexeme(
                lexeme,
                lang_code=lang_code,
                label_hint=candidate,
                qid_hint=qid,
                entity_id_hint=entity_id,
                provenance="lemma_match",
                confidence=0.92,
                fallback_used=False,
            )
            return EntityResolutionResult(
                slot_name=slot_name,
                input_value=value,
                ref=ref,
                matched=True,
                provenance=ref.provenance,
                confidence=ref.confidence,
                fallback_used=False,
                debug={
                    "resolution_path": "lemma",
                    "candidate": candidate,
                },
            )

    # 3) Visible raw fallback
    if allow_raw_fallback and (label or qid or entity_id):
        fallback_label = label or qid or entity_id or _safe_str(value)
        ref = EntityRef(
            label=fallback_label,
            lang_code=lang_code,
            qid=qid,
            entity_id=entity_id,
            lemma=None,
            pos=None,
            provenance="raw_string_fallback",
            confidence=0.2,
            fallback_used=True,
            metadata={
                "requested_qid": qid,
                "aliases": aliases,
            },
        )
        return EntityResolutionResult(
            slot_name=slot_name,
            input_value=value,
            ref=ref,
            matched=False,
            provenance=ref.provenance,
            confidence=ref.confidence,
            fallback_used=True,
            fallback_reason="no_entity_match",
            debug={
                "resolution_path": "raw_fallback",
                "label": fallback_label,
            },
        )

    # Fully unresolved / empty
    return EntityResolutionResult(
        slot_name=slot_name,
        input_value=value,
        ref=None,
        matched=False,
        provenance="unresolved",
        confidence=0.0,
        fallback_used=False,
        fallback_reason="empty_or_unsupported_input",
        debug={
            "resolution_path": "unresolved",
        },
    )


def resolve_entity_slots(
    slots: Mapping[str, Any],
    *,
    lang_code: str,
    entity_slot_names: Iterable[str],
    allow_raw_fallback: bool = True,
) -> Dict[str, EntityResolutionResult]:
    """
    Resolve multiple entity-designated slots while preserving the caller's
    requested slot ordering.
    """

    results: Dict[str, EntityResolutionResult] = {}
    for slot_name in entity_slot_names:
        results[slot_name] = resolve_entity(
            slots.get(slot_name),
            lang_code=lang_code,
            slot_name=slot_name,
            allow_raw_fallback=allow_raw_fallback,
        )
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _entity_ref_from_lexeme(
    lexeme: Lexeme,
    *,
    lang_code: str,
    label_hint: Optional[str],
    qid_hint: Optional[str],
    entity_id_hint: Optional[str],
    provenance: str,
    confidence: float,
    fallback_used: bool,
) -> EntityRef:
    qid = _safe_str(getattr(lexeme, "wikidata_qid", None)) or qid_hint
    lemma = _safe_str(getattr(lexeme, "lemma", None)) or label_hint or qid or ""
    pos = _safe_str(getattr(lexeme, "pos", None)) or None
    entity_id = entity_id_hint or _safe_str(getattr(lexeme, "key", None)) or None

    return EntityRef(
        label=lemma or label_hint or qid or "",
        lang_code=lang_code,
        qid=qid or None,
        entity_id=entity_id,
        lemma=lemma or None,
        pos=pos,
        provenance=provenance,
        confidence=confidence,
        fallback_used=fallback_used,
        metadata={
            "lexeme_key": _safe_str(getattr(lexeme, "key", None)) or None,
            "sense": _safe_str(getattr(lexeme, "sense", None)) or None,
            "human": bool(getattr(lexeme, "human", False)),
        },
    )


def _safe_lookup_qid(*, lang_code: str, qid: str) -> Optional[Lexeme]:
    try:
        return lookup_qid(lang_code, qid)
    except Exception:
        return None


def _safe_lookup_entity_lemma(*, lang_code: str, label: str) -> Optional[Lexeme]:
    cleaned = _normalize_label(label)
    if not cleaned:
        return None

    # Entity labels in the current runtime may live under different POS/storage
    # conventions, so avoid over-constraining the first pass.
    for pos in (None, "PROPN", "NOUN"):
        try:
            found = lookup_lemma(lang_code, cleaned, pos=pos)
        except Exception:
            found = None
        if found is not None:
            return found
    return None


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _extract_qid(value: Any, raw: Mapping[str, Any]) -> Optional[str]:
    candidates = [
        raw.get("qid"),
        raw.get("wikidata_qid"),
        raw.get("wikidataId"),
        raw.get("entity_qid"),
        raw.get("canonical_id"),
        raw.get("canonicalId"),
        raw.get("id"),
        value if isinstance(value, str) and _looks_like_qid(value) else None,
    ]

    for candidate in candidates:
        s = _safe_str(candidate).strip()
        if _looks_like_qid(s):
            return s
    return None


def _extract_entity_id(raw: Mapping[str, Any], *, qid: Optional[str]) -> Optional[str]:
    if qid:
        return qid

    for key in ("entity_id", "entityId", "id", "canonical_id", "canonicalId", "key"):
        value = _safe_str(raw.get(key)).strip()
        if value:
            return value
    return None


def _extract_label(value: Any, raw: Mapping[str, Any]) -> Optional[str]:
    for key in ("label", "name", "title", "text", "lemma", "surface", "display"):
        candidate = _safe_str(raw.get(key)).strip()
        if candidate:
            return candidate

    if isinstance(value, str) and not _looks_like_qid(value):
        stripped = value.strip()
        return stripped or None

    return None


def _extract_aliases(raw: Mapping[str, Any]) -> list[str]:
    aliases_value = raw.get("aliases")
    if isinstance(aliases_value, str):
        return [_normalize_label(aliases_value)] if aliases_value.strip() else []

    aliases: list[str] = []
    if isinstance(aliases_value, Iterable):
        for item in aliases_value:
            alias = _safe_str(item).strip()
            if alias:
                aliases.append(_normalize_label(alias))
    return [a for a in aliases if a]


def _normalize_label(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _looks_like_qid(value: str) -> bool:
    if not value or len(value) < 2:
        return False
    if value[0] != "Q":
        return False
    return value[1:].isdigit()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered