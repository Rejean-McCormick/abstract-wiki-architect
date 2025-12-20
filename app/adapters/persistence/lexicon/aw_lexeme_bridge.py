# app\adapters\persistence\lexicon\aw_lexeme_bridge.py
# lexicon\aw_lexeme_bridge.py
"""
lexicon.aw_lexeme_bridge
========================

Bridge from Abstract Wikipedia / Wikifunctions-style *lexeme objects*
(Z-objects or plain JSON) to the internal `Lexeme` model used by the
lexicon subsystem.

This module is deliberately tolerant and schema-agnostic:

- It accepts *any* dict-ish structure that roughly looks like a lexeme.
- It first runs everything through `unwrap_recursive` so that Z6/Z9
  wrappers are converted to plain Python values.
- It then tries several common field names for lemma, language, POS,
  senses, and forms.

Expected internal model
-----------------------

We assume `lexicon.types` defines dataclasses roughly like:

    @dataclass
    class Form:
        form: str
        features: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Sense:
        id: Optional[str] = None
        glosses: Dict[str, str] = field(default_factory=dict)
        domains: List[str] = field(default_factory=list)

    @dataclass
    class Lexeme:
        id: Optional[str] = None      # e.g. Wikidata lexeme ID "L1"
        language: str = ""           # e.g. "en"
        lemma: str = ""              # canonical lemma
        pos: str = ""                # e.g. "NOUN"
        forms: List[Form] = field(default_factory=list)
        senses: List[Sense] = field(default_factory=list)
        extra: Dict[str, Any] = field(default_factory=dict)

If your actual `Lexeme`/`Sense`/`Form` classes differ slightly, adjust
the mapping in this module accordingly.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from lexicon.types import Lexeme, Sense, Form  # type: ignore
from utils.wikifunctions_api_mock import unwrap_recursive  # type: ignore

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


def _get_first(obj: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return default


# ---------------------------------------------------------------------------
# Senses
# ---------------------------------------------------------------------------


def _sense_from_raw(raw: Any) -> Sense:
    """
    Convert a raw sense-like structure to a Sense.

    We accept multiple shapes for glosses:
        - {"glosses": {"en": "physicist", "fr": "physicien"}}
        - {"glosses": [{"lang": "en", "text": "physicist"}, ...]}
        - {"gloss": "physicist"}  # single gloss, no language
    """
    if not isinstance(raw, dict):
        return Sense(id=None, glosses={})

    sense_id = _safe_str(_get_first(raw, ["id", "senseId"]), default="") or None
    glosses: Dict[str, str] = {}

    # Variant 1: dict mapping language -> text
    raw_glosses = raw.get("glosses")
    if isinstance(raw_glosses, dict):
        for lang, txt in raw_glosses.items():
            glosses[_safe_str(lang)] = _safe_str(txt)
    # Variant 2: list of {"lang": "...", "text": "..."}
    elif isinstance(raw_glosses, list):
        for g in raw_glosses:
            if not isinstance(g, dict):
                continue
            lang = _safe_str(_get_first(g, ["lang", "language", "code"]), default="")
            txt = _safe_str(_get_first(g, ["text", "value", "label"]), default="")
            if lang and txt:
                glosses[lang] = txt
    # Variant 3: single gloss field
    else:
        single = raw.get("gloss")
        if isinstance(single, dict):
            # e.g. {"lang": "en", "text": "physicist"}
            lang = _safe_str(
                _get_first(single, ["lang", "language", "code"]),
                default="",
            )
            txt = _safe_str(
                _get_first(single, ["text", "value", "label"]),
                default="",
            )
            if lang and txt:
                glosses[lang] = txt
        elif isinstance(single, str):
            glosses["und"] = single  # undetermined language

    domains_raw = raw.get("domains", []) or raw.get("domain", [])
    domains: List[str] = []
    if isinstance(domains_raw, list):
        domains = [_safe_str(d) for d in domains_raw if d is not None]
    elif isinstance(domains_raw, str):
        domains = [_safe_str(domains_raw)]

    return Sense(id=sense_id, glosses=glosses, domains=domains)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


def _form_from_raw(raw: Any) -> Form:
    """
    Convert a raw form-like structure to a Form.

    Attempts several common patterns for the surface representation:
        - {"text": "..."}                     # generic
        - {"form": "..."}                     # generic
        - {"representation": "..."}           # Wikidata-ish
        - {"lemma": "..."}                    # fallback
    """
    if not isinstance(raw, dict):
        return Form(form=_safe_str(raw))

    form_text = _safe_str(
        _get_first(
            raw,
            ["text", "form", "representation", "lemma", "value"],
        ),
        default="",
    )

    features: Dict[str, Any] = {}
    raw_features = raw.get("features") or raw.get("feature") or {}

    # If we get a dict directly, use it as-is.
    if isinstance(raw_features, dict):
        features = dict(raw_features)
    # If we get a list of feature labels, convert to boolean flags.
    elif isinstance(raw_features, list):
        for f in raw_features:
            key = _safe_str(f)
            if key:
                features[key] = True

    return Form(form=form_text, features=features)


# ---------------------------------------------------------------------------
# Lexeme
# ---------------------------------------------------------------------------


def lexeme_from_z_object(z_lexeme: Any) -> Lexeme:
    """
    Convert a Wikifunctions / Abstract Wikipedia lexeme-style Z-object
    (or plain JSON) into an internal Lexeme.

    Steps:
        1. Recursively unwrap Z6/Z9 wrappers.
        2. Treat the result as a dict.
        3. Extract:
            - lexeme id (e.g. "L1")
            - language (e.g. "en")
            - lemma
            - part-of-speech
            - senses
            - forms
        4. Store the full unwrapped raw object in `lexeme.extra["source"]`.

    This function is intentionally forgiving: missing fields are allowed
    and will fall back to empty strings or lists where appropriate.
    """
    raw = unwrap_recursive(z_lexeme)

    if not isinstance(raw, dict):
        # Wrap non-dict input in a minimal Lexeme
        return Lexeme(
            id=None,
            language="",
            lemma=_safe_str(raw),
            pos="",
            forms=[],
            senses=[],
            extra={"source": raw},
        )

    lex_id = (
        _safe_str(
            _get_first(raw, ["id", "lexemeId", "lexeme_id", "ZID"]),
            default="",
        )
        or None
    )
    language = _safe_str(
        _get_first(raw, ["language", "lang", "lexemeLanguage"]),
        default="",
    )
    lemma = _safe_str(
        _get_first(raw, ["lemma", "lemmaForm", "baseForm"]),
        default="",
    )
    pos = _safe_str(
        _get_first(raw, ["pos", "partOfSpeech", "lexemePos"]),
        default="",
    )

    # Senses
    raw_senses = (
        raw.get("senses") or raw.get("senseList") or raw.get("lexemeSenses") or []
    )
    senses: List[Sense] = []
    if isinstance(raw_senses, list):
        for s in raw_senses:
            senses.append(_sense_from_raw(s))

    # Forms
    raw_forms = raw.get("forms") or raw.get("formList") or raw.get("lexemeForms") or []
    forms: List[Form] = []
    if isinstance(raw_forms, list):
        for f in raw_forms:
            forms.append(_form_from_raw(f))

    # Keep full unwrapped raw object as source metadata
    extra: Dict[str, Any] = {"source": raw}

    return Lexeme(
        id=lex_id,
        language=language,
        lemma=lemma,
        pos=pos,
        forms=forms,
        senses=senses,
        extra=extra,
    )


def lexemes_from_z_list(z_list: Iterable[Any]) -> List[Lexeme]:
    """
    Convert an iterable of Z-lexeme objects into a list of Lexeme.

    Any item that cannot be converted will still yield a Lexeme
    (with minimal fields) rather than raising an error.
    """
    lexemes: List[Lexeme] = []
    for item in z_list:
        try:
            lex = lexeme_from_z_object(item)
        except Exception as e:  # pragma: no cover - defensive
            # Produce a placeholder lexeme capturing the failure.
            lex = Lexeme(
                id=None,
                language="",
                lemma="",
                pos="",
                forms=[],
                senses=[],
                extra={
                    "error": str(e),
                    "source": unwrap_recursive(item),
                },
            )
        lexemes.append(lex)
    return lexemes
