# app/adapters/persistence/lexicon/types.py
# lexicon/types.py
"""
lexicon/types.py

Core type definitions for the lexicon layer.

This module contains *no I/O* and *no Wikidata calls*. It defines
Python-side structures that other modules (loaders, morphology engines,
renderers) can rely on when working with lexical information coming
from JSON files such as:

    - data/lexicon/en_lexicon.json
    - data/lexicon/fr_lexicon.json
    - data/lexicon/ja_lexicon.json
    - data/lexicon/sw_lexicon.json

Design goals
------------
- Thin, permissive abstractions over heterogeneous per-language schemas.
- Enterprise-grade hygiene:
    - explicit typing and safe defaults
    - lightweight invariant checks
    - predictable behavior for formatting and form selection
- Backwards compatibility: keep Lexeme alias and existing field names.

Loaders are responsible for mapping raw JSON dictionaries into these
types (including populating `extra` for unknown fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from string import Formatter
from typing import Any, Dict, Iterable, Mapping, Optional


# ---------------------------------------------------------------------------
# Common type aliases (kept intentionally permissive)
# ---------------------------------------------------------------------------

PosTag = str
GenderTag = str
NumberTag = str
FormKey = str
LanguageCode = str
WikidataId = str


# ---------------------------------------------------------------------------
# Metadata for a language-specific lexicon
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LexiconMeta:
    """
    Metadata about a single language lexicon.

    Typically read from a `meta` or `_meta` object in JSON, e.g.:

        {
          "meta": {
            "language": "en",
            "family": "germanic",
            "version": "1.0",
            "description": "Minimal English lexicon ..."
          }
        }
    """

    language: LanguageCode
    """BCP-47-ish language code, e.g. 'en', 'fr', 'ja', 'sw'."""

    family: Optional[str] = None
    """Language family label, e.g. 'germanic', 'romance', 'bantu' (optional)."""

    version: Optional[str] = None
    """Free-form version tag, e.g. '1.0' or '0.1.0'."""

    description: Optional[str] = None
    """Human-readable description of the lexicon contents."""

    extra: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata fields not captured above."""

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or not self.language.strip():
            raise ValueError("LexiconMeta.language must be a non-empty string.")


# ---------------------------------------------------------------------------
# Base lexical entry type
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BaseLexicalEntry:
    """
    Minimal cross-linguistic lexical entry.

    This is intentionally permissive. Family- or language-specific loaders
    may populate additional structured fields as needed.

    Core invariants:
      - key, lemma, pos, language are non-empty strings
      - forms is a mapping from string keys to string surface forms
    """

    key: str
    """Stable dictionary key for this entry within its lexicon."""

    lemma: str
    """Canonical lemma/surface for this entry in the target language."""

    pos: PosTag
    """Part-of-speech label, e.g. 'NOUN', 'PROPN', 'ADJ', 'TITLE'."""

    language: LanguageCode
    """Language code, copied from LexiconMeta.language."""

    # --- Core lexical properties ---------------------------------------------

    sense: Optional[str] = None
    """Optional fine-grained semantic sense label (e.g. 'profession')."""

    human: Optional[bool] = None
    """Whether this entry denotes a human (True), non-human (False), or unknown (None)."""

    gender: Optional[GenderTag] = None
    """Default grammatical gender of the lemma, if applicable."""

    default_number: Optional[NumberTag] = None
    """Default grammatical number (e.g. 'sg', 'pl') if applicable."""

    default_formality: Optional[str] = None
    """Default register/formality (e.g. 'neutral', 'polite', 'formal')."""

    wikidata_qid: Optional[WikidataId] = None
    """Optional Wikidata Q-ID linking this entry to a concept."""

    # --- Inflectional data ---------------------------------------------------

    forms: Dict[FormKey, str] = field(default_factory=dict)
    """
    Optional mapping from inflectional keys to surface forms.

    Common patterns:
      - "m.sg" / "f.sg" / "m.pl" / "f.pl"
      - "sg" / "pl"
      - "plain" / "formal"
    """

    # --- Free-form additional info -------------------------------------------

    extra: Dict[str, Any] = field(default_factory=dict)
    """Any additional fields not captured by dedicated attributes."""

    def __post_init__(self) -> None:
        for attr_name in ("key", "lemma", "pos", "language"):
            val = getattr(self, attr_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{self.__class__.__name__}.{attr_name} must be a non-empty string.")

        # Sanitize forms: keep only str->str items
        if not isinstance(self.forms, dict):
            self.forms = {}
        else:
            cleaned: Dict[str, str] = {}
            for k, v in self.forms.items():
                if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                    cleaned[k] = v
            self.forms = cleaned

        if not isinstance(self.extra, dict):
            self.extra = {}

    # ------------------------------------------------------------------
    # Helper API
    # ------------------------------------------------------------------

    def get_form(
        self,
        gender: Optional[GenderTag] = None,
        number: Optional[NumberTag] = None,
        fallback_to_lemma: bool = True,
    ) -> str:
        """
        Lookup an inflected form based on simple gender/number keys.

        Best-effort, language-agnostic resolution strategy:

          1. If gender and number are provided: try "{gender}.{number}" (e.g. "f.sg")
          2. If only number is provided: try "number" (e.g. "sg")
          3. If only gender is provided: try "gender" (e.g. "f")
          4. If no match:
                - if fallback_to_lemma -> return lemma
                - else -> return empty string
        """
        g = (gender or "").strip()
        n = (number or "").strip()

        if g and n:
            key = f"{g}.{n}"
            form = self.forms.get(key)
            if form:
                return form

        if n:
            form = self.forms.get(n)
            if form:
                return form

        if g:
            form = self.forms.get(g)
            if form:
                return form

        return self.lemma if fallback_to_lemma else ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the entry into a JSON-friendly dict.

        Note: This is a convenience helper; loaders may use their own schema.
        """
        return {
            "key": self.key,
            "lemma": self.lemma,
            "pos": self.pos,
            "language": self.language,
            "sense": self.sense,
            "human": self.human,
            "gender": self.gender,
            "default_number": self.default_number,
            "default_formality": self.default_formality,
            "wikidata_qid": self.wikidata_qid,
            "forms": dict(self.forms),
            "extra": dict(self.extra),
        }


# ---------------------------------------------------------------------------
# Backwards-compatible alias for older code
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Lexeme(BaseLexicalEntry):
    """
    Backwards-compatible alias for the older `Lexeme` concept.
    """
    pass


# ---------------------------------------------------------------------------
# Specialized entry types (thin wrappers over BaseLexicalEntry)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ProfessionEntry(BaseLexicalEntry):
    """
    Profession / occupation lexeme (semantic handle for type checking).
    """
    sense: Optional[str] = "profession"


@dataclass(slots=True)
class NationalityEntry(BaseLexicalEntry):
    """
    Nationality or country-related entry.
    """

    adjective: Optional[str] = None
    """Adjectival form, e.g. 'Polish', 'French', 'Japanese'."""

    demonym: Optional[str] = None
    """Noun for person of this nationality, e.g. 'Pole'."""

    country_name: Optional[str] = None
    """Localized country name, e.g. 'Poland', 'France'."""


@dataclass(slots=True)
class TitleEntry(BaseLexicalEntry):
    """
    Honorific / title entry such as 'Sir', 'Dr', 'Prof.'.
    """

    position: Optional[str] = None
    """
    Typical values:
      - "pre_name"  -> before given name (e.g. "Dr Marie Curie")
      - "post_name" -> after name (e.g. "Marie Curie, PhD")
    """


@dataclass(slots=True)
class HonourEntry:
    """
    Non-inflecting honour / award label.
    """

    key: str
    label: str
    short_label: Optional[str] = None
    wikidata_qid: Optional[WikidataId] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("HonourEntry.key must be a non-empty string.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("HonourEntry.label must be a non-empty string.")
        if not isinstance(self.extra, dict):
            self.extra = {}

    def display(self, short: bool = False) -> str:
        """Return either the long or short label, falling back gracefully."""
        if short and self.short_label:
            return self.short_label
        return self.label


@dataclass(slots=True)
class NameTemplate:
    """
    Template for assembling personal names, titles, etc.

    Example JSON:

        "name_templates": {
          "default_person": "{given} {family}",
          "with_title": "{title} {given} {family}"
        }
    """

    key: str
    template: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("NameTemplate.key must be a non-empty string.")
        if not isinstance(self.template, str) or not self.template.strip():
            raise ValueError("NameTemplate.template must be a non-empty string.")
        if not isinstance(self.extra, dict):
            self.extra = {}

    def required_fields(self) -> Iterable[str]:
        """
        Yield format field names referenced by the template.
        """
        fmt = Formatter()
        for _, field_name, _, _ in fmt.parse(self.template):
            if field_name:
                # field_name may include indexing like "person.given"
                yield field_name.split("[", 1)[0].split(".", 1)[0]

    def format(self, **parts: Any) -> str:
        """
        Apply the template with the given parts.

        Missing keys become empty strings and extra whitespace is collapsed.
        """
        safe_parts: Dict[str, Any] = {k: ("" if v is None else v) for k, v in parts.items()}

        # Ensure all referenced fields exist to avoid KeyError
        for k in self.required_fields():
            safe_parts.setdefault(k, "")

        text = self.template.format(**safe_parts)
        return " ".join(text.split())


# ---------------------------------------------------------------------------
# Lexicon container
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Lexicon:
    """
    In-memory representation of a single language lexicon.

    Loaders are expected to populate this container from raw JSON.
    """

    meta: LexiconMeta

    professions: Dict[str, ProfessionEntry] = field(default_factory=dict)
    nationalities: Dict[str, NationalityEntry] = field(default_factory=dict)
    titles: Dict[str, TitleEntry] = field(default_factory=dict)
    honours: Dict[str, HonourEntry] = field(default_factory=dict)
    general_entries: Dict[str, BaseLexicalEntry] = field(default_factory=dict)
    name_templates: Dict[str, NameTemplate] = field(default_factory=dict)

    raw: Dict[str, Any] = field(default_factory=dict)
    """Optional original JSON (or subset) for debugging/round-tripping."""

    def __post_init__(self) -> None:
        if not isinstance(self.raw, dict):
            self.raw = {}

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup_case_insensitive(table: Mapping[str, Any], key: str) -> Optional[Any]:
        """
        Case-insensitive lookup into a mapping, preserving original keys.

        Prefer this for semantically case-insensitive keys (e.g. 'physicist').
        For case-sensitive keys (e.g. proper names), callers may want direct access.
        """
        if key in table:
            return table[key]

        lower = key.casefold()
        for k, v in table.items():
            if isinstance(k, str) and k.casefold() == lower:
                return v
        return None

    def get_profession(self, key: str) -> Optional[ProfessionEntry]:
        return self._lookup_case_insensitive(self.professions, key)

    def get_nationality(self, key: str) -> Optional[NationalityEntry]:
        return self._lookup_case_insensitive(self.nationalities, key)

    def get_title(self, key: str) -> Optional[TitleEntry]:
        return self._lookup_case_insensitive(self.titles, key)

    def get_honour(self, key: str) -> Optional[HonourEntry]:
        return self._lookup_case_insensitive(self.honours, key)

    def get_entry(self, key: str) -> Optional[BaseLexicalEntry]:
        return self._lookup_case_insensitive(self.general_entries, key)

    def get_name_template(self, key: str) -> Optional[NameTemplate]:
        return self._lookup_case_insensitive(self.name_templates, key)

    def format_person_name(
        self,
        given: str,
        family: str,
        title: Optional[str] = None,
        template_key: str = "default_person",
    ) -> str:
        """
        Convenience helper for constructing basic person name strings.
        """
        tmpl = self.get_name_template(template_key)
        if not tmpl:
            parts = [p for p in (title, given, family) if p]
            return " ".join(parts)
        return tmpl.format(given=given, family=family, title=title)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_profession(self, entry: ProfessionEntry) -> None:
        self.professions[entry.key] = entry

    def add_nationality(self, entry: NationalityEntry) -> None:
        self.nationalities[entry.key] = entry

    def add_title(self, entry: TitleEntry) -> None:
        self.titles[entry.key] = entry

    def add_honour(self, entry: HonourEntry) -> None:
        self.honours[entry.key] = entry

    def add_entry(self, entry: BaseLexicalEntry) -> None:
        self.general_entries[entry.key] = entry

    def add_name_template(self, template: NameTemplate) -> None:
        self.name_templates[template.key] = template


__all__ = [
    "PosTag",
    "GenderTag",
    "NumberTag",
    "FormKey",
    "LanguageCode",
    "WikidataId",
    "LexiconMeta",
    "BaseLexicalEntry",
    "Lexeme",
    "ProfessionEntry",
    "NationalityEntry",
    "TitleEntry",
    "HonourEntry",
    "NameTemplate",
    "Lexicon",
]
