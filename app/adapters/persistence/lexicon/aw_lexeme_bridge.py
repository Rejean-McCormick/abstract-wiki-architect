# app/adapters/persistence/lexicon/aw_lexeme_bridge.py
"""
Bridge from Abstract Wikipedia / Wikifunctions-style lexeme objects
(Z-objects or plain JSON) to the current internal `Lexeme` model used by
the lexicon subsystem.

Important alignment notes
-------------------------
The current repository's `Lexeme` type is a thin wrapper over
`BaseLexicalEntry`, which means:

- `key`, `lemma`, `pos`, and `language` must be non-empty strings
- `forms` is a `Dict[str, str]`, not a list of rich form objects
- there is no first-class `senses` field on `Lexeme`; richer sense/form
  metadata should be preserved in `extra`

This bridge therefore:
- stays tolerant of heterogeneous AW / Wikifunctions payloads
- keeps a simple surface-form map in `Lexeme.forms`
- preserves richer normalized senses/forms and full raw source payload in
  `Lexeme.extra` for downstream lexical-resolution/provenance work
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Dict, List, Optional, Tuple

from .types import Form, Lexeme, Sense

try:
    from utils.wikifunctions_api_mock import unwrap_recursive
except ImportError:  # pragma: no cover - defensive fallback
    def unwrap_recursive(value: Any) -> Any:
        return value


__all__ = [
    "lexeme_from_z_object",
    "lexemes_from_z_list",
]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _get_first(
    obj: Mapping[str, Any],
    keys: Iterable[str],
    default: Any = None,
) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return default


def _as_mapping(value: Any) -> Optional[Mapping[str, Any]]:
    return value if isinstance(value, Mapping) else None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        # tolerate dict-shaped containers by returning their values
        return list(value.values())
    return [value]


def _strip_or(default: str, value: Any) -> str:
    text = _safe_str(value, default).strip()
    return text if text else default


def _extract_text(value: Any, preferred_lang: str = "") -> str:
    """
    Best-effort extraction of a human-readable text value from:
    - strings
    - language maps like {"en": "physicist"}
    - label objects like {"lang": "en", "text": "physicist"}
    - nested dict/list wrappers
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, Mapping):
        lang_key = preferred_lang.split("-", 1)[0] if preferred_lang else ""

        # Exact / primary language dict mapping
        for key in (preferred_lang, lang_key):
            if key and key in value and isinstance(value[key], str):
                return value[key].strip()

        # Common scalar fields
        for key in ("text", "value", "label", "lemma", "surface", "name", "id"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()

        # Language-tagged object
        maybe_text = _get_first(value, ("text", "value", "label"), default="")
        if isinstance(maybe_text, str) and maybe_text.strip():
            return maybe_text.strip()

        # Nested values: take the first useful one
        for nested in value.values():
            text = _extract_text(nested, preferred_lang=preferred_lang)
            if text:
                return text

        return ""

    if isinstance(value, (list, tuple)):
        for item in value:
            text = _extract_text(item, preferred_lang=preferred_lang)
            if text:
                return text
        return ""

    return _safe_str(value).strip()


def _extract_language(raw: Mapping[str, Any]) -> str:
    language = _get_first(raw, ("language", "lang", "lexemeLanguage", "languageCode"))
    text = _extract_text(language).lower()
    return text or "und"


def _extract_lemma(raw: Mapping[str, Any], language: str) -> str:
    lemma_value = _get_first(
        raw,
        ("lemma", "lemmaForm", "baseForm", "canonicalForm", "lexicalForm"),
        default="",
    )
    lemma = _extract_text(lemma_value, preferred_lang=language)
    return lemma.strip()


def _normalize_pos(value: Any) -> str:
    pos = _extract_text(value).strip().upper()
    return pos or "X"


def _find_first_qid(obj: Any) -> Optional[str]:
    if isinstance(obj, str):
        text = obj.strip()
        return text if text.startswith("Q") else None

    if isinstance(obj, Mapping):
        for value in obj.values():
            found = _find_first_qid(value)
            if found:
                return found

    if isinstance(obj, (list, tuple)):
        for value in obj:
            found = _find_first_qid(value)
            if found:
                return found

    return None


def _feature_key_from_mapping(features: Mapping[str, Any]) -> str:
    """
    Turn a free-form feature mapping into a stable, readable form key.

    Preferred layout:
      gender.number.case.person.tense.mood.aspect
    plus any remaining keys as k=v segments.
    """
    if not features:
        return ""

    ordered_parts: List[str] = []
    consumed: set[str] = set()

    for key in ("gender", "number", "case", "person", "tense", "mood", "aspect"):
        if key in features and features[key] not in (None, "", False):
            ordered_parts.append(_safe_str(features[key]).strip())
            consumed.add(key)

    for key in sorted(features.keys()):
        if key in consumed:
            continue
        value = features[key]
        if value in (None, "", False):
            continue
        if value is True:
            ordered_parts.append(str(key).strip())
        else:
            ordered_parts.append(f"{key}={_safe_str(value).strip()}")

    return ".".join(part for part in ordered_parts if part)


def _normalize_features(raw_features: Any) -> Dict[str, Any]:
    if isinstance(raw_features, Mapping):
        return {str(k): v for k, v in raw_features.items()}

    if isinstance(raw_features, list):
        out: Dict[str, Any] = {}
        for item in raw_features:
            if isinstance(item, Mapping):
                key = _extract_text(_get_first(item, ("id", "key", "name", "label")))
                value = _get_first(item, ("value", "text", "label"), default=True)
                if key:
                    out[key] = value
            else:
                key = _safe_str(item).strip()
                if key:
                    out[key] = True
        return out

    return {}


# ---------------------------------------------------------------------------
# Senses
# ---------------------------------------------------------------------------


def _sense_from_raw(raw: Any) -> Sense:
    """
    Convert a raw sense-like structure to a normalized `Sense`.
    """
    if not isinstance(raw, Mapping):
        gloss = _safe_str(raw).strip()
        return Sense(
            id=None,
            glosses={"und": gloss} if gloss else {},
            domains=[],
        )

    sense_id = _extract_text(_get_first(raw, ("id", "senseId"), default="")) or None

    glosses: Dict[str, str] = {}
    raw_glosses = raw.get("glosses")

    # Variant 1: {"en": "...", "fr": "..."}
    if isinstance(raw_glosses, Mapping):
        for lang, text in raw_glosses.items():
            lang_key = _safe_str(lang).strip() or "und"
            gloss_text = _extract_text(text, preferred_lang=lang_key)
            if gloss_text:
                glosses[lang_key] = gloss_text

    # Variant 2: [{"lang": "en", "text": "..."}, ...]
    elif isinstance(raw_glosses, list):
        for item in raw_glosses:
            if not isinstance(item, Mapping):
                continue
            lang = _extract_text(_get_first(item, ("lang", "language", "code"), default="")) or "und"
            text = _extract_text(_get_first(item, ("text", "value", "label"), default=""), preferred_lang=lang)
            if text:
                glosses[lang] = text

    # Variant 3: single gloss field
    if not glosses:
        single = raw.get("gloss")
        if isinstance(single, Mapping):
            lang = _extract_text(_get_first(single, ("lang", "language", "code"), default="")) or "und"
            text = _extract_text(_get_first(single, ("text", "value", "label"), default=""), preferred_lang=lang)
            if text:
                glosses[lang] = text
        elif isinstance(single, str) and single.strip():
            glosses["und"] = single.strip()

    domains_raw = raw.get("domains")
    if domains_raw in (None, ""):
        domains_raw = raw.get("domain")

    domains: List[str] = []
    for item in _as_list(domains_raw):
        label = _extract_text(item)
        if label:
            domains.append(label)

    return Sense(id=sense_id, glosses=glosses, domains=domains)


def _serialize_sense(sense: Sense) -> Dict[str, Any]:
    return {
        "id": sense.id,
        "glosses": dict(sense.glosses),
        "domains": list(sense.domains),
    }


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


def _form_from_raw(raw: Any, index: int) -> Tuple[str, Form]:
    """
    Convert a raw form-like structure to a normalized key + `Form`.
    """
    if not isinstance(raw, Mapping):
        surface = _safe_str(raw).strip()
        key = "default" if index == 0 else f"form_{index + 1}"
        return key, Form(surface=surface, features={})

    surface = _extract_text(
        _get_first(
            raw,
            ("surface", "text", "form", "representation", "lemma", "value", "label"),
            default="",
        )
    ).strip()

    features = _normalize_features(raw.get("features") or raw.get("feature"))
    explicit_key = _extract_text(_get_first(raw, ("id", "key", "tag", "slot"), default="")).strip()
    derived_key = _feature_key_from_mapping(features)
    key = explicit_key or derived_key or ("default" if index == 0 else f"form_{index + 1}")

    return key, Form(surface=surface, features=features)


def _collect_forms(raw: Mapping[str, Any], lemma: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    raw_forms = raw.get("forms")
    if raw_forms in (None, ""):
        raw_forms = raw.get("formList")
    if raw_forms in (None, ""):
        raw_forms = raw.get("lexemeForms")

    forms_map: Dict[str, str] = {}
    rich_forms: List[Dict[str, Any]] = []

    # Dict payloads can be either {key: "surface"} or {key: {...rich form...}}
    if isinstance(raw_forms, Mapping):
        items = list(raw_forms.items())
        for index, (raw_key, raw_value) in enumerate(items):
            if isinstance(raw_value, Mapping):
                key, form = _form_from_raw(raw_value, index)
                if not key:
                    key = _safe_str(raw_key).strip() or f"form_{index + 1}"
            else:
                surface = _extract_text(raw_value).strip()
                key = _safe_str(raw_key).strip() or ("default" if index == 0 else f"form_{index + 1}")
                form = Form(surface=surface, features={})

            if not form.surface:
                continue

            key = _dedupe_form_key(forms_map, key)
            forms_map[key] = form.surface
            rich_forms.append(
                {
                    "key": key,
                    "surface": form.surface,
                    "features": dict(form.features),
                }
            )

    else:
        for index, raw_form in enumerate(_as_list(raw_forms)):
            key, form = _form_from_raw(raw_form, index)
            if not form.surface:
                continue

            key = _dedupe_form_key(forms_map, key)
            forms_map[key] = form.surface
            rich_forms.append(
                {
                    "key": key,
                    "surface": form.surface,
                    "features": dict(form.features),
                }
            )

    if lemma and "default" not in forms_map:
        forms_map["default"] = lemma

    return forms_map, rich_forms


def _dedupe_form_key(forms_map: Dict[str, str], key: str) -> str:
    if key not in forms_map:
        return key

    suffix = 2
    candidate = f"{key}_{suffix}"
    while candidate in forms_map:
        suffix += 1
        candidate = f"{key}_{suffix}"
    return candidate


# ---------------------------------------------------------------------------
# Lexeme conversion
# ---------------------------------------------------------------------------


def _derive_entry_key(
    raw: Mapping[str, Any],
    *,
    lexeme_id: Optional[str],
    lemma: str,
    pos: str,
    language: str,
) -> str:
    explicit = _extract_text(_get_first(raw, ("key", "entryKey", "slug"), default="")).strip()
    if explicit:
        return explicit
    if lexeme_id:
        return lexeme_id
    if lemma:
        return f"{language}:{pos}:{lemma}"
    return f"{language}:{pos}:unknown"


def lexeme_from_z_object(z_lexeme: Any) -> Lexeme:
    """
    Convert a Wikifunctions / Abstract Wikipedia lexeme-like Z-object
    (or plain JSON) into the current internal `Lexeme` model.

    The current Lexeme type is deliberately simple, so richer AW form/sense
    data is preserved under `extra`.
    """
    raw_unwrapped = unwrap_recursive(z_lexeme)

    # Scalar / non-dict inputs still become a valid minimal lexeme
    if not isinstance(raw_unwrapped, Mapping):
        lemma = _strip_or("unknown", raw_unwrapped)
        return Lexeme(
            key=f"aw:{lemma}",
            lemma=lemma,
            pos="X",
            language="und",
            wikidata_qid=None,
            forms={"default": lemma},
            extra={
                "source": raw_unwrapped,
                "source_kind": "aw_scalar",
                "provenance": {
                    "bridge": "aw_lexeme_bridge",
                    "source_kind": "aw_scalar",
                },
            },
        )

    raw = dict(raw_unwrapped)

    lexeme_id = _extract_text(_get_first(raw, ("id", "lexemeId", "lexeme_id", "ZID"), default="")).strip() or None
    language = _extract_language(raw)
    lemma = _extract_lemma(raw, language) or (lexeme_id or "unknown")
    pos = _normalize_pos(_get_first(raw, ("pos", "partOfSpeech", "lexemePos", "lexicalCategory"), default=""))
    qid = (
        _find_first_qid(_get_first(raw, ("qid", "wikidata_qid", "wikidataItem", "entity", "concept"), default=None))
        or _find_first_qid(raw.get("senses"))
        or None
    )

    senses_raw = raw.get("senses")
    if senses_raw in (None, ""):
        senses_raw = raw.get("senseList")
    if senses_raw in (None, ""):
        senses_raw = raw.get("lexemeSenses")

    senses = [_sense_from_raw(item) for item in _as_list(senses_raw)]
    forms_map, rich_forms = _collect_forms(raw, lemma=lemma)

    raw_extra = raw.get("extra")
    extra: Dict[str, Any] = dict(raw_extra) if isinstance(raw_extra, Mapping) else {}

    extra.update(
        {
            "source": raw,
            "source_kind": "aw_z_object",
            "provenance": {
                "bridge": "aw_lexeme_bridge",
                "source_kind": "aw_z_object",
                "lexeme_id": lexeme_id,
            },
            "aw_lexeme_id": lexeme_id,
            "aw_forms": rich_forms,
            "aw_senses": [_serialize_sense(sense) for sense in senses],
        }
    )

    sense_label = _extract_text(_get_first(raw, ("sense", "semanticClass", "semanticType"), default="")).strip() or None

    return Lexeme(
        key=_derive_entry_key(
            raw,
            lexeme_id=lexeme_id,
            lemma=lemma,
            pos=pos,
            language=language,
        ),
        lemma=lemma,
        pos=pos,
        language=language,
        sense=sense_label,
        wikidata_qid=qid,
        forms=forms_map,
        extra=extra,
    )


def lexemes_from_z_list(z_list: Iterable[Any]) -> List[Lexeme]:
    """
    Convert an iterable of Z-lexeme objects into a list of `Lexeme`.

    Any item that cannot be converted still yields a valid placeholder
    lexeme instead of failing the entire batch.
    """
    lexemes: List[Lexeme] = []

    for index, item in enumerate(z_list):
        try:
            lexeme = lexeme_from_z_object(item)
        except Exception as exc:  # pragma: no cover - defensive
            unwrapped = unwrap_recursive(item)
            lemma = _extract_text(unwrapped) or "unknown"

            lexeme = Lexeme(
                key=f"aw:error:{index}",
                lemma=lemma,
                pos="X",
                language="und",
                forms={"default": lemma} if lemma else {},
                extra={
                    "error": str(exc),
                    "source": unwrapped,
                    "source_kind": "aw_error_placeholder",
                    "provenance": {
                        "bridge": "aw_lexeme_bridge",
                        "source_kind": "aw_error_placeholder",
                    },
                },
            )

        lexemes.append(lexeme)

    return lexemes