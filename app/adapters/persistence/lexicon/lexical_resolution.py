# app/adapters/persistence/lexicon/lexical_resolution.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
import re
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence

from app.core.domain.constructions.slot_models import (
    EntityRef,
    LexemeRef,
    is_entity_ref_like,
    is_lexeme_ref_like,
    slot_value_to_dict,
)
from app.core.ports.lexical_resolver_port import ResolutionResult

from .index import get_index
from .normalization import normalize_for_lookup

if TYPE_CHECKING:
    from app.core.domain.planning.construction_plan import ConstructionPlan
    from app.core.domain.planning.slot_map import SlotMap


_QID_RE = re.compile(r"^Q\d+$", re.IGNORECASE)

# Conservative heuristics. These are intentionally migration-friendly and can
# later be delegated to entity_resolution.py / predicate_resolution.py.
_ENTITY_SLOT_NAMES = frozenset(
    {
        "subject",
        "topic",
        "object",
        "indirect_object",
        "recipient",
        "agent",
        "patient",
        "theme",
        "owner",
        "possessor",
        "location",
        "place",
        "venue",
        "host_location",
        "destination",
        "origin",
        "source_entity",
        "target_entity",
        "main_event",
        "event_subject",
        "speaker",
        "addressee",
        "organization",
        "organisation",
        "person",
        "team",
        "country",
        "city",
        "region",
    }
)

_LEXEME_SLOT_NAMES = frozenset(
    {
        "predicate",
        "predicate_nominal",
        "profession",
        "nationality",
        "title",
        "honour",
        "descriptor",
        "adjective",
        "attribute",
        "quality",
        "role",
        "occupation",
        "demonym",
        "verb",
        "verb_lemma",
        "predicate_lemma",
    }
)

_LITERAL_SLOT_NAMES = frozenset(
    {
        "tense",
        "aspect",
        "polarity",
        "mood",
        "voice",
        "count",
        "number",
        "quantity",
        "year",
        "date",
        "time",
        "ordinal",
        "percent",
        "text",
        "surface",
        "surface_hint",
        "raw_text",
    }
)


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(mapping: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        if key in mapping:
            text = _clean_str(mapping.get(key))
            if text:
                return text
    return None


def _extract_features(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        raw = value.get("features")
        if isinstance(raw, Mapping):
            return dict(raw)
    return {}


def _is_qid_like(value: Any) -> bool:
    text = _clean_str(value)
    return bool(text and _QID_RE.fullmatch(text))


def _serialize_jsonish(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if is_entity_ref_like(value) or is_lexeme_ref_like(value):
        try:
            return slot_value_to_dict(value)
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {str(k): _serialize_jsonish(v) for k, v in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_serialize_jsonish(v) for v in value]

    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)

    return str(value)


def _clone_with_updates(obj: Any, **changes: Any) -> Any:
    if isinstance(obj, Mapping):
        merged = dict(obj)
        merged.update(changes)
        return merged

    if hasattr(obj, "with_updates") and callable(obj.with_updates):
        return obj.with_updates(**changes)

    model_copy = getattr(obj, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=changes)

    if is_dataclass(obj) and not isinstance(obj, type):
        return replace(obj, **changes)

    replacer = getattr(obj, "_replace", None)
    if callable(replacer):
        return replacer(**changes)

    if hasattr(obj, "__dict__"):
        payload = dict(vars(obj))
        payload.update(changes)
        return obj.__class__(**payload)

    raise TypeError(f"Unsupported ConstructionPlan object type: {type(obj).__name__}")


def _entry_attr(entry: Any, name: str, default: Any = None) -> Any:
    if entry is None:
        return default
    if hasattr(entry, name):
        return getattr(entry, name)
    if isinstance(entry, Mapping):
        return entry.get(name, default)
    return default


def _entry_extra(entry: Any) -> Mapping[str, Any]:
    extra = _entry_attr(entry, "extra", {})
    return extra if isinstance(extra, Mapping) else {}


def _entry_qid(entry: Any) -> Optional[str]:
    extra = _entry_extra(entry)
    return (
        _clean_str(_entry_attr(entry, "qid"))
        or _clean_str(extra.get("qid"))
        or _clean_str(extra.get("wikidata_id"))
        or _clean_str(extra.get("entity_id"))
    )


def _entry_lexeme_id(entry: Any) -> Optional[str]:
    return _clean_str(_entry_attr(entry, "id"))


def _entry_label(entry: Any) -> Optional[str]:
    return _clean_str(_entry_attr(entry, "lemma")) or _clean_str(_entry_attr(entry, "label"))


def _slot_kind_hint(slot_name: str, value: Any) -> str:
    slot = (slot_name or "").strip().lower()

    if is_entity_ref_like(value):
        return "entity"
    if is_lexeme_ref_like(value):
        return "lexeme"

    if slot in _LITERAL_SLOT_NAMES:
        return "literal"
    if slot in _ENTITY_SLOT_NAMES:
        return "entity"
    if slot in _LEXEME_SLOT_NAMES or slot.endswith("_lemma"):
        return "lexeme"

    if isinstance(value, Mapping):
        if any(k in value for k in ("entity_id", "qid", "surface_key", "entity_type")):
            return "entity"
        if any(k in value for k in ("lexeme_id", "lemma", "pos", "part_of_speech")):
            return "lexeme"

    return "literal"


def _pos_hints_for_slot(slot_name: str) -> tuple[Optional[str], ...]:
    slot = (slot_name or "").strip().lower()
    if slot in {"profession", "title", "honour", "occupation", "predicate_nominal"}:
        return ("NOUN", None)
    if slot in {"nationality", "adjective", "descriptor", "quality", "attribute"}:
        return ("ADJ", "NOUN", None)
    if slot in {"verb", "verb_lemma", "predicate_lemma"}:
        return ("VERB", None)
    return (None,)


class LexicalResolver:
    """
    Shared lexical-resolution adapter for the planning -> realization boundary.

    Responsibilities:
    - resolve a whole ConstructionPlan or slot_map deterministically,
    - preserve slot names and ordering,
    - populate `lexical_bindings`,
    - make fallback explicit and machine-readable.

    Notes:
    - This implementation is intentionally conservative and migration-friendly.
    - Entity- and predicate-specific heuristics can later move into the
      dedicated Batch 5 helper modules without changing this public adapter.
    """

    def __init__(
        self,
        *,
        default_generation_options: Optional[Mapping[str, Any]] = None,
        materialize_resolved_slot_values: bool = True,
    ) -> None:
        self._default_generation_options = dict(default_generation_options or {})
        self._materialize_resolved_slot_values = bool(materialize_resolved_slot_values)

    async def resolve_plan(self, *, construction_plan: "ConstructionPlan") -> Any:
        if construction_plan is None:
            raise TypeError("construction_plan must not be None")

        lang_code = _clean_str(getattr(construction_plan, "lang_code", None) or construction_plan.get("lang_code"))  # type: ignore[arg-type]
        construction_id = _clean_str(
            getattr(construction_plan, "construction_id", None) or construction_plan.get("construction_id")  # type: ignore[arg-type]
        )
        slot_map = getattr(construction_plan, "slot_map", None)
        if slot_map is None and isinstance(construction_plan, Mapping):
            slot_map = construction_plan.get("slot_map")

        if not isinstance(slot_map, Mapping):
            raise TypeError("construction_plan.slot_map must be a mapping")

        resolved_slot_map = await self.resolve_slot_map(
            slot_map,
            lang_code=lang_code or "und",
            construction_id=construction_id,
            generation_options=getattr(construction_plan, "generation_options", None)
            if not isinstance(construction_plan, Mapping)
            else construction_plan.get("generation_options"),
        )

        lexical_bindings = resolved_slot_map.get("lexical_bindings", {})
        return _clone_with_updates(
            construction_plan,
            slot_map=resolved_slot_map,
            lexical_bindings=lexical_bindings,
        )

    async def resolve_slot_map(
        self,
        slot_map: "SlotMap",
        *,
        lang_code: str,
        construction_id: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if slot_map is None:
            raise TypeError("slot_map must not be None")
        if not isinstance(slot_map, Mapping):
            raise TypeError("slot_map must be a mapping")

        normalized_lang = _clean_str(lang_code) or "und"
        options = dict(self._default_generation_options)
        if isinstance(generation_options, Mapping):
            options.update(generation_options)

        resolved_slot_map: dict[str, Any] = {}
        lexical_bindings: dict[str, Any] = {}

        for slot_name, slot_value in slot_map.items():
            if str(slot_name) == "lexical_bindings":
                continue

            result = await self.resolve_slot(
                lang_code=normalized_lang,
                construction_id=construction_id or "",
                slot_name=str(slot_name),
                slot_value=slot_value,
                generation_options=options,
            )

            lexical_bindings[str(slot_name)] = self._result_to_binding(result)

            if self._materialize_resolved_slot_values and not result.unresolved:
                resolved_slot_map[str(slot_name)] = result.resolved_value
            else:
                resolved_slot_map[str(slot_name)] = slot_value

        resolved_slot_map["lexical_bindings"] = lexical_bindings
        return resolved_slot_map

    async def resolve_slot(
        self,
        *,
        lang_code: str,
        construction_id: str,
        slot_name: str,
        slot_value: object,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        options = dict(self._default_generation_options)
        if isinstance(generation_options, Mapping):
            options.update(generation_options)

        if slot_value is None:
            return ResolutionResult(
                slot_name=slot_name,
                input_value=None,
                resolved_value=None,
                kind="unresolved",
                source="missing",
                confidence=0.0,
                fallback_used=False,
                unresolved=True,
                metadata={"construction_id": construction_id, "lang_code": lang_code},
            )

        if isinstance(slot_value, Sequence) and not isinstance(
            slot_value, (str, bytes, bytearray, Mapping)
        ):
            return await self._resolve_sequence(
                slot_name=slot_name,
                slot_value=slot_value,
                lang_code=lang_code,
                construction_id=construction_id,
                generation_options=options,
            )

        if is_entity_ref_like(slot_value):
            return self._pass_through_entity_ref(slot_name=slot_name, value=slot_value)

        if is_lexeme_ref_like(slot_value):
            return self._pass_through_lexeme_ref(slot_name=slot_name, value=slot_value)

        hint = _slot_kind_hint(slot_name, slot_value)

        if hint == "entity":
            return self._resolve_entity(
                slot_name=slot_name,
                slot_value=slot_value,
                lang_code=lang_code,
            )

        if hint == "lexeme":
            return self._resolve_lexeme(
                slot_name=slot_name,
                slot_value=slot_value,
                lang_code=lang_code,
            )

        return ResolutionResult(
            slot_name=slot_name,
            input_value=slot_value,
            resolved_value=slot_value,
            kind="literal",
            source="literal_passthrough",
            confidence=1.0,
            fallback_used=False,
            unresolved=False,
            metadata={"construction_id": construction_id, "lang_code": lang_code},
        )

    async def resolve_entity(
        self,
        value: object,
        *,
        lang_code: str,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        return self._resolve_entity(slot_name="entity", slot_value=value, lang_code=lang_code)

    async def resolve_lexeme(
        self,
        value: object,
        *,
        lang_code: str,
        pos: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        return self._resolve_lexeme(
            slot_name="lexeme",
            slot_value=value,
            lang_code=lang_code,
            forced_pos=pos,
        )

    def _pass_through_entity_ref(self, *, slot_name: str, value: Any) -> ResolutionResult:
        payload = slot_value_to_dict(value)
        metadata = {
            "entity_id": payload.get("entity_id"),
            "qid": payload.get("qid"),
            "surface_key": payload.get("surface_key"),
            "entity_type": payload.get("entity_type"),
            "alias_used": payload.get("alias_used"),
        }
        return ResolutionResult(
            slot_name=slot_name,
            input_value=value,
            resolved_value=value,
            kind="entity_ref",
            source=payload.get("source") or "pre_resolved",
            confidence=float(payload.get("confidence") or 1.0),
            fallback_used=False,
            unresolved=False,
            surface_hint=payload.get("label"),
            metadata=metadata,
        )

    def _pass_through_lexeme_ref(self, *, slot_name: str, value: Any) -> ResolutionResult:
        payload = slot_value_to_dict(value)
        metadata = {
            "lexeme_id": payload.get("lexeme_id"),
            "qid": payload.get("qid"),
            "pos": payload.get("pos"),
            "surface_hint": payload.get("surface_hint"),
        }
        return ResolutionResult(
            slot_name=slot_name,
            input_value=value,
            resolved_value=value,
            kind="lexeme_ref",
            source=payload.get("source") or "pre_resolved",
            confidence=float(payload.get("confidence") or 1.0),
            fallback_used=False,
            unresolved=False,
            surface_hint=payload.get("surface_hint") or payload.get("lemma"),
            metadata=metadata,
        )

    async def _resolve_sequence(
        self,
        *,
        slot_name: str,
        slot_value: Sequence[Any],
        lang_code: str,
        construction_id: str,
        generation_options: Mapping[str, Any],
    ) -> ResolutionResult:
        items: list[ResolutionResult] = []
        resolved_values: list[Any] = []

        for item in slot_value:
            child = await self.resolve_slot(
                lang_code=lang_code,
                construction_id=construction_id,
                slot_name=slot_name,
                slot_value=item,
                generation_options=generation_options,
            )
            items.append(child)
            resolved_values.append(child.resolved_value if not child.unresolved else item)

        item_kinds = {item.kind for item in items if not item.unresolved}
        if len(item_kinds) == 1:
            kind = f"{next(iter(item_kinds))}_list"
        else:
            kind = "sequence"

        confidence = min((item.confidence for item in items), default=0.0)
        fallback_used = any(item.fallback_used for item in items)
        unresolved = all(item.unresolved for item in items) if items else False

        return ResolutionResult(
            slot_name=slot_name,
            input_value=list(slot_value),
            resolved_value=resolved_values,
            kind=kind,
            source="sequence",
            confidence=confidence,
            fallback_used=fallback_used,
            unresolved=unresolved,
            metadata={
                "items": [self._result_to_binding(item) for item in items],
            },
        )

    def _resolve_entity(
        self,
        *,
        slot_name: str,
        slot_value: Any,
        lang_code: str,
    ) -> ResolutionResult:
        if isinstance(slot_value, Mapping):
            entity_id = _first_text(slot_value, "entity_id", "id")
            qid = _first_text(slot_value, "qid")
            label = _first_text(slot_value, "label", "name", "surface", "text", "lemma")
            entity_type = _first_text(slot_value, "entity_type", "type", "kind")
            surface_key = _first_text(slot_value, "surface_key")
            features = _extract_features(slot_value)

            if entity_id or qid:
                label = label or qid or entity_id or "unknown"
                ref = EntityRef(
                    entity_id=entity_id,
                    label=label,
                    lang_code=lang_code,
                    source="stable_id",
                    confidence=1.0,
                    qid=qid,
                    surface_key=surface_key,
                    entity_type=entity_type,
                    alias_used=None,
                    features=features,
                )
                return ResolutionResult(
                    slot_name=slot_name,
                    input_value=slot_value,
                    resolved_value=ref,
                    kind="entity_ref",
                    source="stable_id",
                    confidence=1.0,
                    fallback_used=False,
                    unresolved=False,
                    surface_hint=label,
                    metadata={
                        "entity_id": entity_id,
                        "qid": qid,
                        "surface_key": surface_key,
                        "entity_type": entity_type,
                    },
                )

            if label:
                entry = self._lookup_any_entry(lang_code=lang_code, key=label)
                if entry is not None:
                    alias_used = label if normalize_for_lookup(label) != normalize_for_lookup(_entry_label(entry) or label) else None
                    ref = EntityRef(
                        entity_id=_entry_lexeme_id(entry),
                        label=_entry_label(entry) or label,
                        lang_code=lang_code,
                        source="entity_index" if alias_used is None else "entity_alias",
                        confidence=0.9 if alias_used is None else 0.75,
                        qid=_entry_qid(entry),
                        surface_key=surface_key,
                        entity_type=entity_type,
                        alias_used=alias_used,
                        features=features,
                    )
                    return ResolutionResult(
                        slot_name=slot_name,
                        input_value=slot_value,
                        resolved_value=ref,
                        kind="entity_ref",
                        source=ref.source,
                        confidence=ref.confidence,
                        fallback_used=False,
                        unresolved=False,
                        surface_hint=ref.label,
                        metadata={
                            "entity_id": ref.entity_id,
                            "qid": ref.qid,
                            "surface_key": ref.surface_key,
                            "entity_type": ref.entity_type,
                            "alias_used": ref.alias_used,
                        },
                    )

                ref = EntityRef(
                    entity_id=None,
                    label=label,
                    lang_code=lang_code,
                    source="label_only",
                    confidence=0.25,
                    qid=None,
                    surface_key=surface_key,
                    entity_type=entity_type,
                    alias_used=None,
                    features=features,
                )
                return ResolutionResult(
                    slot_name=slot_name,
                    input_value=slot_value,
                    resolved_value=ref,
                    kind="entity_ref",
                    source="label_only",
                    confidence=0.25,
                    fallback_used=True,
                    unresolved=False,
                    surface_hint=label,
                    metadata={
                        "entity_id": None,
                        "qid": None,
                        "surface_key": surface_key,
                        "entity_type": entity_type,
                    },
                )

        raw = _clean_str(slot_value)
        if raw is None:
            return ResolutionResult(
                slot_name=slot_name,
                input_value=slot_value,
                resolved_value=slot_value,
                kind="unresolved",
                source="invalid_entity_input",
                confidence=0.0,
                fallback_used=False,
                unresolved=True,
            )

        if _is_qid_like(raw):
            entry = self._lookup_qid_entry(lang_code=lang_code, qid=raw)
            label = _entry_label(entry) or raw
            ref = EntityRef(
                entity_id=_entry_lexeme_id(entry),
                label=label,
                lang_code=lang_code,
                source="stable_id" if entry is not None else "label_only",
                confidence=1.0 if entry is not None else 0.25,
                qid=raw,
                surface_key=None,
                entity_type=None,
                alias_used=None,
                features={},
            )
            return ResolutionResult(
                slot_name=slot_name,
                input_value=slot_value,
                resolved_value=ref,
                kind="entity_ref",
                source=ref.source,
                confidence=ref.confidence,
                fallback_used=entry is None,
                unresolved=False,
                surface_hint=label,
                metadata={
                    "entity_id": ref.entity_id,
                    "qid": ref.qid,
                },
            )

        entry = self._lookup_any_entry(lang_code=lang_code, key=raw)
        if entry is not None:
            alias_used = raw if normalize_for_lookup(raw) != normalize_for_lookup(_entry_label(entry) or raw) else None
            ref = EntityRef(
                entity_id=_entry_lexeme_id(entry),
                label=_entry_label(entry) or raw,
                lang_code=lang_code,
                source="entity_index" if alias_used is None else "entity_alias",
                confidence=0.9 if alias_used is None else 0.75,
                qid=_entry_qid(entry),
                surface_key=None,
                entity_type=None,
                alias_used=alias_used,
                features={},
            )
            return ResolutionResult(
                slot_name=slot_name,
                input_value=slot_value,
                resolved_value=ref,
                kind="entity_ref",
                source=ref.source,
                confidence=ref.confidence,
                fallback_used=False,
                unresolved=False,
                surface_hint=ref.label,
                metadata={
                    "entity_id": ref.entity_id,
                    "qid": ref.qid,
                    "alias_used": ref.alias_used,
                },
            )

        ref = EntityRef(
            entity_id=None,
            label=raw,
            lang_code=lang_code,
            source="raw_string",
            confidence=0.25,
            qid=None,
            surface_key=None,
            entity_type=None,
            alias_used=None,
            features={},
        )
        return ResolutionResult(
            slot_name=slot_name,
            input_value=slot_value,
            resolved_value=ref,
            kind="entity_ref",
            source="raw_string",
            confidence=0.25,
            fallback_used=True,
            unresolved=False,
            surface_hint=raw,
            metadata={
                "entity_id": None,
                "qid": None,
            },
        )

    def _resolve_lexeme(
        self,
        *,
        slot_name: str,
        slot_value: Any,
        lang_code: str,
        forced_pos: str | None = None,
    ) -> ResolutionResult:
        if isinstance(slot_value, Mapping):
            lexeme_id = _first_text(slot_value, "lexeme_id", "id")
            qid = _first_text(slot_value, "qid")
            lemma = _first_text(slot_value, "lemma", "surface", "label", "name", "text")
            pos = forced_pos or _first_text(slot_value, "pos", "part_of_speech", "category")
            surface_hint = _first_text(slot_value, "surface_hint", "surface")
            features = _extract_features(slot_value)

            if lexeme_id or qid:
                if lemma is None and qid is not None:
                    entry = self._lookup_qid_entry(lang_code=lang_code, qid=qid)
                    lemma = _entry_label(entry) or qid
                    if pos is None:
                        pos = _clean_str(_entry_attr(entry, "pos"))
                    if lexeme_id is None:
                        lexeme_id = _entry_lexeme_id(entry)
                ref = LexemeRef(
                    lemma=lemma or "unknown",
                    lang_code=lang_code,
                    pos=pos,
                    source="stable_id",
                    confidence=1.0,
                    lexeme_id=lexeme_id,
                    qid=qid,
                    surface_hint=surface_hint or lemma,
                    features=features,
                )
                return ResolutionResult(
                    slot_name=slot_name,
                    input_value=slot_value,
                    resolved_value=ref,
                    kind="lexeme_ref",
                    source="stable_id",
                    confidence=1.0,
                    fallback_used=False,
                    unresolved=False,
                    surface_hint=ref.surface_hint,
                    metadata={
                        "lexeme_id": ref.lexeme_id,
                        "qid": ref.qid,
                        "pos": ref.pos,
                    },
                )

            if lemma:
                entry = self._lookup_lemma_entry(lang_code=lang_code, lemma=lemma, slot_name=slot_name, forced_pos=pos)
                if entry is not None:
                    entry_lemma = _entry_label(entry) or lemma
                    alias_used = lemma if normalize_for_lookup(lemma) != normalize_for_lookup(entry_lemma) else None
                    ref = LexemeRef(
                        lemma=entry_lemma,
                        lang_code=lang_code,
                        pos=_clean_str(_entry_attr(entry, "pos")) or pos,
                        source="language_lexicon" if alias_used is None else "lexicon_alias",
                        confidence=0.9 if alias_used is None else 0.75,
                        lexeme_id=_entry_lexeme_id(entry),
                        qid=_entry_qid(entry),
                        surface_hint=surface_hint or entry_lemma,
                        features=features,
                    )
                    return ResolutionResult(
                        slot_name=slot_name,
                        input_value=slot_value,
                        resolved_value=ref,
                        kind="lexeme_ref",
                        source=ref.source,
                        confidence=ref.confidence,
                        fallback_used=False,
                        unresolved=False,
                        surface_hint=ref.surface_hint,
                        metadata={
                            "lexeme_id": ref.lexeme_id,
                            "qid": ref.qid,
                            "pos": ref.pos,
                            "alias_used": alias_used,
                        },
                    )

                ref = LexemeRef(
                    lemma=lemma,
                    lang_code=lang_code,
                    pos=pos,
                    source="raw_string",
                    confidence=0.25,
                    lexeme_id=None,
                    qid=qid,
                    surface_hint=surface_hint or lemma,
                    features=features,
                )
                return ResolutionResult(
                    slot_name=slot_name,
                    input_value=slot_value,
                    resolved_value=ref,
                    kind="lexeme_ref",
                    source="raw_string",
                    confidence=0.25,
                    fallback_used=True,
                    unresolved=False,
                    surface_hint=ref.surface_hint,
                    metadata={
                        "lexeme_id": None,
                        "qid": qid,
                        "pos": pos,
                    },
                )

        raw = _clean_str(slot_value)
        if raw is None:
            return ResolutionResult(
                slot_name=slot_name,
                input_value=slot_value,
                resolved_value=slot_value,
                kind="unresolved",
                source="invalid_lexeme_input",
                confidence=0.0,
                fallback_used=False,
                unresolved=True,
            )

        if _is_qid_like(raw):
            entry = self._lookup_qid_entry(lang_code=lang_code, qid=raw)
            if entry is not None:
                ref = LexemeRef(
                    lemma=_entry_label(entry) or raw,
                    lang_code=lang_code,
                    pos=_clean_str(_entry_attr(entry, "pos")),
                    source="stable_id",
                    confidence=1.0,
                    lexeme_id=_entry_lexeme_id(entry),
                    qid=raw,
                    surface_hint=_entry_label(entry) or raw,
                    features={},
                )
                return ResolutionResult(
                    slot_name=slot_name,
                    input_value=slot_value,
                    resolved_value=ref,
                    kind="lexeme_ref",
                    source="stable_id",
                    confidence=1.0,
                    fallback_used=False,
                    unresolved=False,
                    surface_hint=ref.surface_hint,
                    metadata={
                        "lexeme_id": ref.lexeme_id,
                        "qid": ref.qid,
                        "pos": ref.pos,
                    },
                )

        entry = self._lookup_lemma_entry(
            lang_code=lang_code,
            lemma=raw,
            slot_name=slot_name,
            forced_pos=forced_pos,
        )
        if entry is not None:
            entry_lemma = _entry_label(entry) or raw
            alias_used = raw if normalize_for_lookup(raw) != normalize_for_lookup(entry_lemma) else None
            ref = LexemeRef(
                lemma=entry_lemma,
                lang_code=lang_code,
                pos=_clean_str(_entry_attr(entry, "pos")),
                source="language_lexicon" if alias_used is None else "lexicon_alias",
                confidence=0.9 if alias_used is None else 0.75,
                lexeme_id=_entry_lexeme_id(entry),
                qid=_entry_qid(entry),
                surface_hint=entry_lemma,
                features={},
            )
            return ResolutionResult(
                slot_name=slot_name,
                input_value=slot_value,
                resolved_value=ref,
                kind="lexeme_ref",
                source=ref.source,
                confidence=ref.confidence,
                fallback_used=False,
                unresolved=False,
                surface_hint=ref.surface_hint,
                metadata={
                    "lexeme_id": ref.lexeme_id,
                    "qid": ref.qid,
                    "pos": ref.pos,
                    "alias_used": alias_used,
                },
            )

        pos_hint = forced_pos
        if pos_hint is None:
            for candidate in _pos_hints_for_slot(slot_name):
                if candidate is not None:
                    pos_hint = candidate
                    break

        ref = LexemeRef(
            lemma=raw,
            lang_code=lang_code,
            pos=pos_hint,
            source="raw_string",
            confidence=0.25,
            lexeme_id=None,
            qid=None,
            surface_hint=raw,
            features={},
        )
        return ResolutionResult(
            slot_name=slot_name,
            input_value=slot_value,
            resolved_value=ref,
            kind="lexeme_ref",
            source="raw_string",
            confidence=0.25,
            fallback_used=True,
            unresolved=False,
            surface_hint=raw,
            metadata={
                "lexeme_id": None,
                "qid": None,
                "pos": pos_hint,
            },
        )

    def _lookup_qid_entry(self, *, lang_code: str, qid: str) -> Any:
        index = get_index(lang_code)
        lookup = getattr(index, "lookup_by_qid", None)
        if callable(lookup):
            try:
                return lookup(qid)
            except Exception:
                return None
        return None

    def _lookup_any_entry(self, *, lang_code: str, key: str) -> Any:
        index = get_index(lang_code)

        lookup_any = getattr(index, "lookup_any", None)
        if callable(lookup_any):
            try:
                hit = lookup_any(key)
            except Exception:
                hit = None
            if hit is not None:
                return hit

        lookup_lemma = getattr(index, "lookup_by_lemma", None)
        if callable(lookup_lemma):
            try:
                hit = lookup_lemma(key, pos=None)
            except Exception:
                hit = None
            if hit is not None:
                return hit

        return None

    def _lookup_lemma_entry(
        self,
        *,
        lang_code: str,
        lemma: str,
        slot_name: str,
        forced_pos: str | None = None,
    ) -> Any:
        index = get_index(lang_code)
        lookup = getattr(index, "lookup_by_lemma", None)
        if not callable(lookup):
            return None

        for pos in ((forced_pos,) if forced_pos is not None else _pos_hints_for_slot(slot_name)):
            try:
                hit = lookup(lemma, pos=pos)
            except Exception:
                hit = None
            if hit is not None:
                return hit
        return None

    def _result_to_binding(self, result: ResolutionResult) -> dict[str, Any]:
        payload = {
            "slot_name": result.slot_name,
            "input_value": _serialize_jsonish(result.input_value),
            "resolved_value": _serialize_jsonish(result.resolved_value),
            "kind": result.kind,
            "source": result.source,
            "confidence": result.confidence,
            "fallback_used": result.fallback_used,
            "unresolved": result.unresolved,
            "surface_hint": result.surface_hint,
            "notes": list(result.notes),
            "metadata": _serialize_jsonish(result.metadata),
        }

        resolved_value = _serialize_jsonish(result.resolved_value)
        if isinstance(resolved_value, Mapping):
            for key in (
                "entity_id",
                "lexeme_id",
                "qid",
                "alias_used",
                "surface_key",
                "entity_type",
                "pos",
                "lemma",
                "label",
            ):
                if key in resolved_value and resolved_value.get(key) is not None:
                    payload[key] = resolved_value.get(key)

        return payload


async def resolve_slot_map(
    slot_map: "SlotMap",
    *,
    lang_code: str,
    construction_id: str | None = None,
    generation_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience coroutine for migration-time callers that do not yet own a
    resolver instance.
    """
    resolver = LexicalResolver()
    return await resolver.resolve_slot_map(
        slot_map,
        lang_code=lang_code,
        construction_id=construction_id,
        generation_options=generation_options,
    )


async def resolve_plan(*, construction_plan: "ConstructionPlan") -> Any:
    """
    Convenience coroutine mirroring the canonical plan-level port.
    """
    resolver = LexicalResolver()
    return await resolver.resolve_plan(construction_plan=construction_plan)


__all__ = [
    "LexicalResolver",
    "resolve_slot_map",
    "resolve_plan",
]