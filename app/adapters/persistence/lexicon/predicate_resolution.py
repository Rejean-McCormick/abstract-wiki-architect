# app/adapters/persistence/lexicon/predicate_resolution.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.core.domain.constructions.slot_models import LexemeRef
from app.core.ports.lexical_resolver_port import ResolutionResult

from .index import get_index

_QID_OR_LEXEME_ID_RE = re.compile(r"^[QL]\d+(?:[-_][A-Za-z0-9]+)?$", re.IGNORECASE)

# Canonical Batch-5 predicate-like slots, plus a few pragmatic aliases that
# already appear in frame/slot naming across the repo.
DEFAULT_PREDICATE_SLOT_NAMES = frozenset(
    {
        "profession",
        "profession_lemma",
        "predicate_nominal",
        "predicate_adjective",
        "relation_label",
        "office_title",
        "event_label",
        "class_lemma",
        "occupation",
        "occupation_lemma",
        "nationality",
        "nationality_lemma",
        "role_label",
        "title_lemma",
        "honour_lemma",
        "species_lemma",
        "kind_lemma",
    }
)

DEFAULT_POS_BY_SLOT: dict[str, str] = {
    "predicate_adjective": "ADJ",
    "nationality": "ADJ",
    "nationality_lemma": "ADJ",
    "profession": "NOUN",
    "profession_lemma": "NOUN",
    "predicate_nominal": "NOUN",
    "relation_label": "NOUN",
    "office_title": "NOUN",
    "event_label": "NOUN",
    "class_lemma": "NOUN",
    "occupation": "NOUN",
    "occupation_lemma": "NOUN",
    "role_label": "NOUN",
    "title_lemma": "NOUN",
    "honour_lemma": "NOUN",
    "species_lemma": "NOUN",
    "kind_lemma": "NOUN",
}


@dataclass(slots=True)
class PredicateResolutionOptions:
    """
    Local options for predicate-slot resolution.

    Notes:
    - This module is intentionally deterministic and storage-light.
    - Cross-language orchestration belongs in the higher-level lexical
      resolution layer; this helper resolves one predicate-like slot for
      one language at a time.
    """

    allow_raw_fallback: bool = True
    allow_shared_lexicon_fallback: bool = True
    try_qid_lookup: bool = True
    try_posless_lookup: bool = True
    raw_fallback_confidence: float = 0.25
    index_hit_confidence: float = 0.98
    qid_hit_confidence: float = 1.0
    shared_runtime_confidence: float = 0.72
    preferred_pos_by_slot: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_POS_BY_SLOT)
    )


def is_predicate_like_slot(slot_name: str | None) -> bool:
    cleaned = _clean_text(slot_name)
    return bool(cleaned and cleaned in DEFAULT_PREDICATE_SLOT_NAMES)


def resolve_predicate(
    value: object,
    *,
    lang_code: str,
    slot_name: str,
    construction_id: str | None = None,
    generation_options: Mapping[str, Any] | None = None,
    options: PredicateResolutionOptions | None = None,
) -> ResolutionResult:
    """
    Resolve a predicate-like slot into a canonical `LexemeRef` where possible.

    Resolution order:
    1. Preserve an incoming LexemeRef
    2. Resolve by explicit QID / lexeme ID
    3. Resolve by lemma with preferred POS
    4. Resolve by lemma without POS (optional)
    5. Shared legacy lexicon fallback (optional)
    6. Raw-string fallback as a low-confidence LexemeRef (optional)
    """

    opts = options or PredicateResolutionOptions()
    requested_pos = _preferred_pos(slot_name, value, opts)
    allow_raw = _allow_raw_fallback(opts, generation_options)

    if isinstance(value, LexemeRef):
        return _result_from_existing_lexeme_ref(
            value=value,
            lang_code=lang_code,
            slot_name=slot_name,
            construction_id=construction_id,
            requested_pos=requested_pos,
        )

    if value is None:
        return _unresolved_result(
            slot_name=slot_name,
            input_value=value,
            source="predicate_resolution",
            reason="empty_input",
            lang_code=lang_code,
            construction_id=construction_id,
            requested_pos=requested_pos,
        )

    if isinstance(value, Mapping):
        return _resolve_from_mapping(
            payload=value,
            lang_code=lang_code,
            slot_name=slot_name,
            construction_id=construction_id,
            requested_pos=requested_pos,
            generation_options=generation_options,
            options=opts,
            allow_raw=allow_raw,
        )

    return _resolve_from_text(
        text=str(value),
        original_value=value,
        lang_code=lang_code,
        slot_name=slot_name,
        construction_id=construction_id,
        requested_pos=requested_pos,
        generation_options=generation_options,
        options=opts,
        allow_raw=allow_raw,
    )


class PredicateResolver:
    """
    Small stateful wrapper for callers that want an object-oriented adapter.
    """

    def __init__(self, options: PredicateResolutionOptions | None = None) -> None:
        self.options = options or PredicateResolutionOptions()

    def resolve(
        self,
        value: object,
        *,
        lang_code: str,
        slot_name: str,
        construction_id: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        return resolve_predicate(
            value,
            lang_code=lang_code,
            slot_name=slot_name,
            construction_id=construction_id,
            generation_options=generation_options,
            options=self.options,
        )


# ---------------------------------------------------------------------------
# Internal resolution steps
# ---------------------------------------------------------------------------


def _resolve_from_mapping(
    *,
    payload: Mapping[str, Any],
    lang_code: str,
    slot_name: str,
    construction_id: str | None,
    requested_pos: str | None,
    generation_options: Mapping[str, Any] | None,
    options: PredicateResolutionOptions,
    allow_raw: bool,
) -> ResolutionResult:
    existing = _coerce_mapping_to_lexeme_ref(payload, requested_pos=requested_pos)
    if existing is not None:
        # Prefer canonical index hit if we have enough information, but do not
        # throw away an already-normalized LexemeRef if lookup misses.
        qid = _first_text(payload, "qid", "wikidata_qid")
        lemma = _first_text(payload, "lemma", "label", "text", "surface", "name")
        pos = _clean_text(payload.get("pos")) or requested_pos

        if qid and options.try_qid_lookup:
            hit = _lookup_by_qid(lang_code=lang_code, qid=qid)
            if hit is not None:
                return _result_from_lexicon_hit(
                    lexeme=hit,
                    slot_name=slot_name,
                    input_value=dict(payload),
                    source="lexicon_qid",
                    confidence=options.qid_hit_confidence,
                    lang_code=lang_code,
                    construction_id=construction_id,
                    requested_pos=pos,
                )

        if lemma:
            hit = _lookup_by_lemma(lang_code=lang_code, lemma=lemma, pos=pos)
            if hit is None and options.try_posless_lookup:
                hit = _lookup_by_lemma(lang_code=lang_code, lemma=lemma, pos=None)
            if hit is not None:
                return _result_from_lexicon_hit(
                    lexeme=hit,
                    slot_name=slot_name,
                    input_value=dict(payload),
                    source="lexicon_lemma",
                    confidence=options.index_hit_confidence,
                    lang_code=lang_code,
                    construction_id=construction_id,
                    requested_pos=pos,
                )

        return ResolutionResult(
            slot_name=slot_name,
            input_value=dict(payload),
            resolved_value=existing,
            kind="lexeme_ref",
            source=existing.source or "existing_lexeme_ref",
            confidence=float(existing.confidence or 0.85),
            fallback_used=False,
            unresolved=False,
            surface_hint=existing.surface_hint,
            notes=("preserved_existing_lexeme_ref",),
            metadata={
                "lang_code": lang_code,
                "construction_id": construction_id,
                "requested_pos": pos,
                "resolved_pos": existing.pos,
                "matched_qid": existing.qid,
                "matched_lexeme_id": existing.lexeme_id,
            },
        )

    text = _first_text(payload, "lemma", "label", "text", "surface", "name")
    qid = _first_text(payload, "qid", "wikidata_qid", "entity_id", "lexeme_id")

    if qid and options.try_qid_lookup and _looks_like_qid_or_lexeme_id(qid):
        hit = _lookup_by_qid(lang_code=lang_code, qid=qid)
        if hit is not None:
            return _result_from_lexicon_hit(
                lexeme=hit,
                slot_name=slot_name,
                input_value=dict(payload),
                source="lexicon_qid",
                confidence=options.qid_hit_confidence,
                lang_code=lang_code,
                construction_id=construction_id,
                requested_pos=requested_pos,
            )

    if text:
        return _resolve_from_text(
            text=text,
            original_value=dict(payload),
            lang_code=lang_code,
            slot_name=slot_name,
            construction_id=construction_id,
            requested_pos=requested_pos,
            generation_options=generation_options,
            options=options,
            allow_raw=allow_raw,
        )

    return _unresolved_result(
        slot_name=slot_name,
        input_value=dict(payload),
        source="predicate_resolution",
        reason="mapping_without_predicate_text",
        lang_code=lang_code,
        construction_id=construction_id,
        requested_pos=requested_pos,
    )


def _resolve_from_text(
    *,
    text: str,
    original_value: object,
    lang_code: str,
    slot_name: str,
    construction_id: str | None,
    requested_pos: str | None,
    generation_options: Mapping[str, Any] | None,
    options: PredicateResolutionOptions,
    allow_raw: bool,
) -> ResolutionResult:
    cleaned = _clean_text(text)
    if not cleaned:
        return _unresolved_result(
            slot_name=slot_name,
            input_value=original_value,
            source="predicate_resolution",
            reason="blank_text",
            lang_code=lang_code,
            construction_id=construction_id,
            requested_pos=requested_pos,
        )

    if options.try_qid_lookup and _looks_like_qid_or_lexeme_id(cleaned):
        hit = _lookup_by_qid(lang_code=lang_code, qid=cleaned)
        if hit is not None:
            return _result_from_lexicon_hit(
                lexeme=hit,
                slot_name=slot_name,
                input_value=original_value,
                source="lexicon_qid",
                confidence=options.qid_hit_confidence,
                lang_code=lang_code,
                construction_id=construction_id,
                requested_pos=requested_pos,
            )

    hit = _lookup_by_lemma(lang_code=lang_code, lemma=cleaned, pos=requested_pos)
    if hit is not None:
        return _result_from_lexicon_hit(
            lexeme=hit,
            slot_name=slot_name,
            input_value=original_value,
            source="lexicon_lemma",
            confidence=options.index_hit_confidence,
            lang_code=lang_code,
            construction_id=construction_id,
            requested_pos=requested_pos,
        )

    if options.try_posless_lookup:
        hit = _lookup_by_lemma(lang_code=lang_code, lemma=cleaned, pos=None)
        if hit is not None:
            return _result_from_lexicon_hit(
                lexeme=hit,
                slot_name=slot_name,
                input_value=original_value,
                source="lexicon_lemma_posless",
                confidence=max(options.index_hit_confidence - 0.12, 0.0),
                lang_code=lang_code,
                construction_id=construction_id,
                requested_pos=requested_pos,
            )

    if options.allow_shared_lexicon_fallback:
        fallback = _lookup_in_shared_lexicon(
            text=cleaned,
            lang_code=lang_code,
            requested_pos=requested_pos,
            confidence=options.shared_runtime_confidence,
        )
        if fallback is not None:
            return ResolutionResult(
                slot_name=slot_name,
                input_value=original_value,
                resolved_value=fallback,
                kind="lexeme_ref",
                source=fallback.source,
                confidence=fallback.confidence,
                fallback_used=False,
                unresolved=False,
                surface_hint=fallback.surface_hint,
                notes=("resolved_via_shared_lexicon",),
                metadata={
                    "lang_code": lang_code,
                    "construction_id": construction_id,
                    "requested_pos": requested_pos,
                    "resolved_pos": fallback.pos,
                    "matched_qid": fallback.qid,
                    "matched_lexeme_id": fallback.lexeme_id,
                },
            )

    if allow_raw:
        raw = _build_raw_fallback(
            text=cleaned,
            requested_pos=requested_pos,
            confidence=options.raw_fallback_confidence,
        )
        return ResolutionResult(
            slot_name=slot_name,
            input_value=original_value,
            resolved_value=raw,
            kind="lexeme_ref",
            source=raw.source,
            confidence=raw.confidence,
            fallback_used=True,
            unresolved=False,
            surface_hint=raw.surface_hint,
            notes=("raw_string_fallback",),
            metadata={
                "lang_code": lang_code,
                "construction_id": construction_id,
                "requested_pos": requested_pos,
                "resolved_pos": raw.pos,
                "matched_qid": None,
                "matched_lexeme_id": None,
            },
        )

    return _unresolved_result(
        slot_name=slot_name,
        input_value=original_value,
        source="predicate_resolution",
        reason="no_match",
        lang_code=lang_code,
        construction_id=construction_id,
        requested_pos=requested_pos,
    )


# ---------------------------------------------------------------------------
# Lexicon lookups
# ---------------------------------------------------------------------------


def _lookup_by_lemma(*, lang_code: str, lemma: str, pos: str | None) -> Any | None:
    idx = get_index(lang_code)
    try:
        return idx.lookup_by_lemma(lemma, pos=pos)
    except TypeError:
        try:
            return idx.lookup_by_lemma(lemma, pos)
        except Exception:
            return None
    except Exception:
        return None


def _lookup_by_qid(*, lang_code: str, qid: str) -> Any | None:
    idx = get_index(lang_code)
    try:
        return idx.lookup_by_qid(qid)
    except Exception:
        return None


def _lookup_in_shared_lexicon(
    *,
    text: str,
    lang_code: str,
    requested_pos: str | None,
    confidence: float,
) -> LexemeRef | None:
    try:
        from app.shared.lexicon import LexiconRuntime
    except Exception:
        return None

    try:
        runtime = LexiconRuntime.get_instance()
        entry = runtime.lookup(text, lang_code)
    except Exception:
        return None

    if entry is None:
        return None

    entry_pos = _clean_text(getattr(entry, "pos", None))
    if requested_pos and entry_pos and entry_pos != requested_pos:
        return None

    features = _copy_mapping(getattr(entry, "features", None))
    gf_fun = _clean_text(getattr(entry, "gf_fun", None))
    if gf_fun:
        features.setdefault("gf_fun", gf_fun)

    return LexemeRef(
        lemma=_clean_text(getattr(entry, "lemma", None)) or text,
        lexeme_id=None,
        qid=_clean_text(getattr(entry, "qid", None)),
        pos=entry_pos or requested_pos,
        surface_hint=None,
        source=_clean_text(getattr(entry, "source", None)) or "shared_lexicon",
        confidence=confidence,
        features=features,
    )


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------


def _result_from_existing_lexeme_ref(
    *,
    value: LexemeRef,
    lang_code: str,
    slot_name: str,
    construction_id: str | None,
    requested_pos: str | None,
) -> ResolutionResult:
    return ResolutionResult(
        slot_name=slot_name,
        input_value=value,
        resolved_value=value,
        kind="lexeme_ref",
        source=value.source or "existing_lexeme_ref",
        confidence=float(value.confidence or 0.85),
        fallback_used=False,
        unresolved=False,
        surface_hint=value.surface_hint,
        notes=("preserved_existing_lexeme_ref",),
        metadata={
            "lang_code": lang_code,
            "construction_id": construction_id,
            "requested_pos": requested_pos,
            "resolved_pos": value.pos,
            "matched_qid": value.qid,
            "matched_lexeme_id": value.lexeme_id,
        },
    )


def _result_from_lexicon_hit(
    *,
    lexeme: Any,
    slot_name: str,
    input_value: object,
    source: str,
    confidence: float,
    lang_code: str,
    construction_id: str | None,
    requested_pos: str | None,
) -> ResolutionResult:
    ref = _lexeme_ref_from_lexicon_hit(
        lexeme,
        source=source,
        confidence=confidence,
        requested_pos=requested_pos,
    )
    return ResolutionResult(
        slot_name=slot_name,
        input_value=input_value,
        resolved_value=ref,
        kind="lexeme_ref",
        source=source,
        confidence=confidence,
        fallback_used=False,
        unresolved=False,
        surface_hint=ref.surface_hint,
        notes=("resolved_via_lexicon_index",),
        metadata={
            "lang_code": lang_code,
            "construction_id": construction_id,
            "requested_pos": requested_pos,
            "resolved_pos": ref.pos,
            "matched_qid": ref.qid,
            "matched_lexeme_id": ref.lexeme_id,
        },
    )


def _unresolved_result(
    *,
    slot_name: str,
    input_value: object,
    source: str,
    reason: str,
    lang_code: str,
    construction_id: str | None,
    requested_pos: str | None,
) -> ResolutionResult:
    return ResolutionResult(
        slot_name=slot_name,
        input_value=input_value,
        resolved_value=None,
        kind="unresolved",
        source=source,
        confidence=0.0,
        fallback_used=False,
        unresolved=True,
        surface_hint=None,
        notes=(reason,),
        metadata={
            "lang_code": lang_code,
            "construction_id": construction_id,
            "requested_pos": requested_pos,
        },
    )


def _lexeme_ref_from_lexicon_hit(
    lexeme: Any,
    *,
    source: str,
    confidence: float,
    requested_pos: str | None,
) -> LexemeRef:
    extra = _copy_mapping(getattr(lexeme, "extra", None))
    features = _copy_mapping(getattr(lexeme, "forms", None))
    if extra:
        features.setdefault("extra", extra)

    return LexemeRef(
        lemma=_clean_text(getattr(lexeme, "lemma", None)) or "",
        lexeme_id=(
            _clean_text(extra.get("lexeme_id"))
            or _clean_text(getattr(lexeme, "key", None))
            or _clean_text(getattr(lexeme, "id", None))
        ),
        qid=(
            _clean_text(getattr(lexeme, "wikidata_qid", None))
            or _clean_text(extra.get("qid"))
            or _clean_text(extra.get("wikidata_qid"))
        ),
        pos=_clean_text(getattr(lexeme, "pos", None)) or requested_pos,
        surface_hint=_extract_surface_hint(lexeme),
        source=source,
        confidence=confidence,
        features=features,
    )


def _build_raw_fallback(
    *,
    text: str,
    requested_pos: str | None,
    confidence: float,
) -> LexemeRef:
    return LexemeRef(
        lemma=text,
        lexeme_id=None,
        qid=None,
        pos=requested_pos,
        surface_hint=text,
        source="raw_string",
        confidence=confidence,
        features={"raw_fallback": True},
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _allow_raw_fallback(
    options: PredicateResolutionOptions,
    generation_options: Mapping[str, Any] | None,
) -> bool:
    if generation_options is None:
        return options.allow_raw_fallback

    direct = generation_options.get("allow_raw_fallback")
    if isinstance(direct, bool):
        return direct

    lexical = generation_options.get("lexical_resolution")
    if isinstance(lexical, Mapping):
        nested = lexical.get("allow_raw_fallback")
        if isinstance(nested, bool):
            return nested

    return options.allow_raw_fallback


def _preferred_pos(
    slot_name: str,
    value: object,
    options: PredicateResolutionOptions,
) -> str | None:
    slot_key = _clean_text(slot_name)
    if slot_key:
        hinted = options.preferred_pos_by_slot.get(slot_key)
        if hinted:
            return hinted

    if isinstance(value, LexemeRef) and value.pos:
        return _clean_text(value.pos)

    if isinstance(value, Mapping):
        pos = _clean_text(value.get("pos"))
        if pos:
            return pos

    return None


def _coerce_mapping_to_lexeme_ref(
    payload: Mapping[str, Any],
    *,
    requested_pos: str | None,
) -> LexemeRef | None:
    lemma = _first_text(payload, "lemma", "label", "text", "surface", "name")
    qid = _first_text(payload, "qid", "wikidata_qid")
    lexeme_id = _first_text(payload, "lexeme_id", "id", "source_id")
    pos = _clean_text(payload.get("pos")) or requested_pos
    source = _clean_text(payload.get("source")) or "existing_mapping"
    surface_hint = _first_text(payload, "surface_hint", "surface", "text")
    confidence = _float_or_default(payload.get("confidence"), 0.85)

    if not lemma and not qid and not lexeme_id:
        return None

    raw_features = payload.get("features")
    features = _copy_mapping(raw_features)

    return LexemeRef(
        lemma=lemma or "",
        lexeme_id=lexeme_id,
        qid=qid,
        pos=pos,
        surface_hint=surface_hint,
        source=source,
        confidence=confidence,
        features=features,
    )


def _extract_surface_hint(lexeme: Any) -> str | None:
    forms = getattr(lexeme, "forms", None)

    if isinstance(forms, Mapping):
        default = forms.get("default")
        if isinstance(default, str) and default.strip():
            return default.strip()
        for value in forms.values():
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _looks_like_qid_or_lexeme_id(text: str | None) -> bool:
    cleaned = _clean_text(text)
    return bool(cleaned and _QID_OR_LEXEME_ID_RE.match(cleaned))


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    cleaned = str(value).strip()
    return cleaned or None


def _copy_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


__all__ = [
    "DEFAULT_PREDICATE_SLOT_NAMES",
    "DEFAULT_POS_BY_SLOT",
    "PredicateResolutionOptions",
    "PredicateResolver",
    "is_predicate_like_slot",
    "resolve_predicate",
]