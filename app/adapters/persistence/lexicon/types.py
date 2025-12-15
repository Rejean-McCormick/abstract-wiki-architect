# lexicon\types.py
"""
lexicon/types.py

Core type definitions for the lexicon layer.

This module deliberately contains *no I/O* and *no Wikidata calls*.
It defines Python-side structures that other modules (e.g. loaders,
morphology engines, or renderers) can rely on when working with
lexical information coming from JSON files such as:

    - data/lexicon/en_lexicon.json
    - data/lexicon/fr_lexicon.json
    - data/lexicon/ja_lexicon.json
    - data/lexicon/sw_lexicon.json

The goal is to provide a thin, well-documented abstraction over
those JSON schemas without over-constraining them. Different
languages can keep their own layout; a loader is responsible for
mapping them into these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


# ---------------------------------------------------------------------------
# Metadata for a language-specific lexicon
# ---------------------------------------------------------------------------


@dataclass
class LexiconMeta:
    """
    Metadata about a single language lexicon file.

    This is typically read from a `meta` or `_meta` object in JSON, e.g.:

        {
          "meta": {
            "language": "en",
            "family": "germanic",
            "version": "1.0",
            "description": "Minimal English lexicon ..."
          },
          ...
        }

    or

        {
          "_meta": {
            "language": "fr",
            "version": "0.1.0",
            "description": "Minimal French lexicon ..."
          },
          ...
        }
    """

    language: str
    """BCP-47-ish language code, e.g. 'en', 'fr', 'ja', 'sw'."""

    family: Optional[str] = None
    """Language family label, e.g. 'germanic', 'romance', 'bantu' (optional)."""

    version: Optional[str] = None
    """Free-form version tag, e.g. '1.0' or '0.1.0'."""

    description: Optional[str] = None
    """Human-readable description of the lexicon contents."""

    extra: Dict[str, Any] = field(default_factory=dict)
    """
    Any additional metadata fields that do not have a dedicated slot
    (e.g. authorship, license info, timestamps).
    """


# ---------------------------------------------------------------------------
# Base lexical entry type
# ---------------------------------------------------------------------------


@dataclass
class BaseLexicalEntry:
    """
    Minimal cross-linguistic lexical entry.

    This is intentionally permissive. Family- or language-specific
    loaders may populate additional structured fields as needed.

    Examples of how different JSON schemas can map here:

      * data/lexicon/en_lexicon.json (professions):

            {
              "lemma": "physicist",
              "display": "physicist",
              "gender": "common",
              "wikidata_qid": "Q169470"
            }

      * data/lexicon/fr_lexicon.json (entries):

            {
              "pos": "NOUN",
              "gender": "m",
              "default_number": "sg",
              "semantic_class": "profession",
              "forms": {
                "m.sg": "physicien",
                "f.sg": "physicienne",
                "m.pl": "physiciens",
                "f.pl": "physiciennes"
              }
            }

      * data/lexicon/sw_lexicon.json (lemmas):

            {
              "pos": "NOUN",
              "gloss": "physicist",
              "human": true,
              "noun_class_sg": 1,
              "noun_class_pl": 2,
              "plural_lemma": "wanasayansi"
            }
    """

    key: str
    """
    Stable dictionary key for this entry *within* its lexicon.

    Examples:
        - "physicist" (profession key in English lexicon)
        - "Marie Curie" (proper name key in French lexicon)
        - "mwanasayansi" (lemma key in Swahili lexicon)
    """

    lemma: str
    """
    Canonical lemma/surface for this entry in the target language.

    For many entries this is identical to `key`, but it does not have
    to be (e.g. key "computer_scientist" with lemma "computer scientist").
    """

    pos: str
    """
    Part-of-speech label, e.g. 'NOUN', 'PROPN', 'ADJ', 'TITLE'.

    The exact tagset is project-defined, but POS is useful for:
      - choosing morphology pathways
      - filtering in loaders
    """

    language: str
    """Language code, copied from LexiconMeta.language."""

    # --- Core lexical properties ------------------------------------------------

    sense: Optional[str] = None
    """
    Optional fine-grained semantic sense label.

    Examples:
      - "profession"
      - "country"
      - "title"
      - "common_noun"
    """

    human: Optional[bool] = None
    """
    Whether this entry denotes a human (True), non-human (False),
    or if unknown/irrelevant (None).

    Useful for agreement and discourse constraints.
    """

    gender: Optional[str] = None
    """
    Grammatical gender of the lemma's *default* form, if any.

    Examples:
      - 'm'
      - 'f'
      - 'n'
      - 'common'
      - None (no gender category)
    """

    default_number: Optional[str] = None
    """
    Default grammatical number of the lemma, e.g. 'sg' or 'pl'.
    """

    default_formality: Optional[str] = None
    """
    Default register/formality (e.g. 'neutral', 'polite', 'formal').

    Especially useful for languages like Japanese or Korean.
    """

    wikidata_qid: Optional[str] = None
    """
    Optional Wikidata Q-ID linking this lexeme to a concept.
    """

    # --- Inflectional data ------------------------------------------------------

    forms: Dict[str, str] = field(default_factory=dict)
    """
    Optional mapping from inflectional keys to surface forms.

    This is deliberately unopinionated. Typical patterns include:
      - "m.sg" / "f.sg" / "m.pl" / "f.pl"
      - "sg" / "pl"
      - "plain" / "formal"
    """

    # --- Free-form additional info ---------------------------------------------

    extra: Dict[str, Any] = field(default_factory=dict)
    """
    Any additional fields present in the JSON that do not have a
    dedicated attribute (e.g. 'gloss', 'noun_class_sg').
    """

    # ------------------------------------------------------------------
    # Helper API
    # ------------------------------------------------------------------

    def get_form(
        self,
        gender: Optional[str] = None,
        number: Optional[str] = None,
        fallback_to_lemma: bool = True,
    ) -> str:
        """
        Lookup an inflected form based on simple gender/number keys.

        This is a best-effort, language-agnostic helper. It assumes
        that `forms` keys may look like `"m.sg"`, `"f.pl"`, `"sg"`, `"pl"`,
        etc. Use more specialized logic in family-specific morphology
        engines when necessary.

        Resolution strategy:

          1. If both `gender` and `number` are provided:
                - try `"{gender}.{number}"` (e.g. "f.sg")
          2. If only `number` is provided:
                - try `number` (e.g. "sg")
          3. If only `gender` is provided:
                - try `gender` (e.g. "f")
          4. If none of the above match:
                - if `fallback_to_lemma` → return `lemma`
                - else → return empty string
        """
        # Normalize keys
        g = (gender or "").strip()
        n = (number or "").strip()

        # 1. gender + number (e.g. "f.sg")
        if g and n:
            key = f"{g}.{n}"
            form = self.forms.get(key)
            if form:
                return form

        # 2. number-only (e.g. "sg")
        if n:
            form = self.forms.get(n)
            if form:
                return form

        # 3. gender-only (e.g. "f")
        if g:
            form = self.forms.get(g)
            if form:
                return form

        # 4. Fallback
        return self.lemma if fallback_to_lemma else ""


# ---------------------------------------------------------------------------
# Backwards-compatible alias for older code
# ---------------------------------------------------------------------------


@dataclass
class Lexeme(BaseLexicalEntry):
    """
    Backwards-compatible alias for the older `Lexeme` concept.

    Historically, some modules (e.g. older versions of lexicon.index)
    worked directly with `Lexeme` instances created from JSON. The
    new architecture prefers:

        - BaseLexicalEntry for generic entries
        - ProfessionEntry / NationalityEntry / TitleEntry / HonourEntry
          for specialized roles
        - Lexicon as the container

    This subclass allows older code that imports `Lexeme` to keep
    working while internally sharing the same shape as
    BaseLexicalEntry.
    """

    # No extra fields; we inherit everything from BaseLexicalEntry.
    pass


# ---------------------------------------------------------------------------
# Specialized entry types (thin wrappers over BaseLexicalEntry)
# ---------------------------------------------------------------------------


@dataclass
class ProfessionEntry(BaseLexicalEntry):
    """
    Profession / occupation lexeme.

    This is typically used for renderings like "Marie Curie was a
    Polish physicist". It adds no new required fields beyond
    BaseLexicalEntry but gives a semantic handle to the type checker.
    """

    sense: Optional[str] = "profession"


@dataclass
class NationalityEntry(BaseLexicalEntry):
    """
    Nationality or country-related entry.

    Typical JSON (English):

        "polish": {
          "key": "polish",
          "adjective": "Polish",
          "demonym": "Pole",
          "country_name": "Poland",
          "wikidata_qid": "Q36"
        }
    """

    adjective: Optional[str] = None
    """Adjectival form, e.g. 'Polish', 'French', 'Japanese'."""

    demonym: Optional[str] = None
    """Noun for person of this nationality, e.g. 'Pole', 'French person'."""

    country_name: Optional[str] = None
    """Localized country name, e.g. 'Poland', 'France'."""

    # The `lemma` field is typically the adjective or demonym, depending
    # on language preference. For some renderings, engines may prefer
    # `adjective` while for others they may prefer `demonym`.


@dataclass
class TitleEntry(BaseLexicalEntry):
    """
    Honorific / title entry such as 'Sir', 'Dr', 'Prof.'.

    Example JSON (English):

        "sir": {
          "lemma": "Sir",
          "position": "pre_name",
          "gender": "male"
        }
    """

    position: Optional[str] = None
    """
    Typical values:
      - "pre_name"  → before given name (e.g. "Dr Marie Curie")
      - "post_name" → after name (e.g. "Marie Curie, PhD")
    """


@dataclass
class HonourEntry:
    """
    Non-inflecting honour / award label.

    Example JSON (English):

        "nobel_prize_physics": {
          "label": "Nobel Prize in Physics",
          "short_label": "the Nobel Prize in Physics",
          "wikidata_qid": "Q38104"
        }
    """

    key: str
    label: str
    short_label: Optional[str] = None
    wikidata_qid: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def display(self, short: bool = False) -> str:
        """
        Return either the long or short label, falling back gracefully.
        """
        if short and self.short_label:
            return self.short_label
        return self.label


@dataclass
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

    def format(self, **parts: Any) -> str:
        """
        Apply the template with the given parts.

        Missing keys are turned into empty strings and extra whitespace
        is collapsed by the caller (if desired).
        """
        safe_parts: Dict[str, Any] = {
            k: ("" if v is None else v) for k, v in parts.items()
        }
        try:
            text = self.template.format(**safe_parts)
        except KeyError:
            # If the template references keys that are not provided,
            # treat them as empty.
            all_keys = {
                field_name
                for field_name in self.template.split("{")
                if "}" in field_name
            }
            for k in all_keys:
                k = k.split("}")[0]
                if k not in safe_parts:
                    safe_parts[k] = ""
            text = self.template.format(**safe_parts)

        # Lightweight normalization: collapse multiple spaces.
        return " ".join(text.split())


# ---------------------------------------------------------------------------
# Lexicon container
# ---------------------------------------------------------------------------


@dataclass
class Lexicon:
    """
    In-memory representation of a single language lexicon.

    This is a convenient, structured view on top of the raw JSON.
    A loader is expected to:

      1. Read a JSON file into a dict.
      2. Extract `meta` / `_meta` to build LexiconMeta.
      3. Convert the remainder into ProfessionEntry / NationalityEntry /
         BaseLexicalEntry / TitleEntry / HonourEntry / NameTemplate.
      4. Populate this Lexicon instance.
    """

    meta: LexiconMeta

    professions: Dict[str, ProfessionEntry] = field(default_factory=dict)
    """Profession entries indexed by key (e.g. 'physicist')."""

    nationalities: Dict[str, NationalityEntry] = field(default_factory=dict)
    """Nationality entries indexed by key (e.g. 'polish')."""

    titles: Dict[str, TitleEntry] = field(default_factory=dict)
    """Honorific titles (e.g. 'sir', 'dr', 'prof')."""

    honours: Dict[str, HonourEntry] = field(default_factory=dict)
    """Named honours/awards (e.g. 'nobel_prize_physics')."""

    general_entries: Dict[str, BaseLexicalEntry] = field(default_factory=dict)
    """
    Catch-all mapping for lexemes that don't fit the above specializations
    (e.g. French `entries`, Swahili `lemmas`, Japanese `lemmas`).
    """

    name_templates: Dict[str, NameTemplate] = field(default_factory=dict)
    """Name templates by key, e.g. 'default_person', 'with_title'."""

    raw: Dict[str, Any] = field(default_factory=dict)
    """
    Optional original JSON (or a subset of it) for debugging and
    round-tripping. This is not required for normal operation.
    """

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _lookup_case_insensitive(
        self,
        table: Mapping[str, Any],
        key: str,
    ) -> Optional[Any]:
        """
        Case-insensitive lookup into a dictionary, preserving original keys.

        This is appropriate for keys like 'physicist', 'polish', etc.
        For keys where case is semantically meaningful (e.g. 'Marie Curie'),
        callers may prefer direct indexing using the exact key instead.
        """
        if key in table:
            return table[key]

        lower = key.lower()
        for k, v in table.items():
            if k.lower() == lower:
                return v
        return None

    # --- Profession API ----------------------------------------------------

    def get_profession(self, key: str) -> Optional[ProfessionEntry]:
        """
        Retrieve a profession by its key, using case-insensitive matching.
        """
        return self._lookup_case_insensitive(self.professions, key)

    # --- Nationality API ---------------------------------------------------

    def get_nationality(self, key: str) -> Optional[NationalityEntry]:
        """
        Retrieve a nationality by its key, using case-insensitive matching.
        """
        return self._lookup_case_insensitive(self.nationalities, key)

    # --- Title API ---------------------------------------------------------

    def get_title(self, key: str) -> Optional[TitleEntry]:
        """
        Retrieve a title/honorific by its key, using case-insensitive matching.
        """
        return self._lookup_case_insensitive(self.titles, key)

    # --- Honour API --------------------------------------------------------

    def get_honour(self, key: str) -> Optional[HonourEntry]:
        """
        Retrieve an honour/award entry by its key, using case-insensitive matching.
        """
        return self._lookup_case_insensitive(self.honours, key)

    # --- General entries ---------------------------------------------------

    def get_entry(self, key: str) -> Optional[BaseLexicalEntry]:
        """
        Retrieve a generic lexical entry by key, using case-insensitive matching.

        This is mainly intended for lexica like French / Swahili / Japanese
        whose JSON schema uses a single `entries` or `lemmas` map.
        """
        return self._lookup_case_insensitive(self.general_entries, key)

    # --- Name templating ---------------------------------------------------

    def get_name_template(self, key: str) -> Optional[NameTemplate]:
        """
        Retrieve a name template by key, using case-insensitive matching.
        """
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

        Typically used with templates like:

            "default_person": "{given} {family}"
            "with_title": "{title} {given} {family}"

        If `title` is provided and the chosen template references it,
        the user should ensure the template_key (e.g. "with_title")
        is appropriate.
        """
        tmpl = self.get_name_template(template_key)
        if not tmpl:
            # Fallback: naive 'Given Family'
            parts = [p for p in (title, given, family) if p]
            return " ".join(parts)

        return tmpl.format(given=given, family=family, title=title)

    # ------------------------------------------------------------------
    # Mutation helpers (for programmatic enrichment of a lexicon)
    # ------------------------------------------------------------------

    def add_profession(self, entry: ProfessionEntry) -> None:
        """
        Add or overwrite a profession entry.
        """
        self.professions[entry.key] = entry

    def add_nationality(self, entry: NationalityEntry) -> None:
        """
        Add or overwrite a nationality entry.
        """
        self.nationalities[entry.key] = entry

    def add_title(self, entry: TitleEntry) -> None:
        """
        Add or overwrite a title entry.
        """
        self.titles[entry.key] = entry

    def add_honour(self, entry: HonourEntry) -> None:
        """
        Add or overwrite an honour/award entry.
        """
        self.honours[entry.key] = entry

    def add_entry(self, entry: BaseLexicalEntry) -> None:
        """
        Add or overwrite a general lexical entry.
        """
        self.general_entries[entry.key] = entry

    def add_name_template(self, template: NameTemplate) -> None:
        """
        Add or overwrite a name template.
        """
        self.name_templates[template.key] = template


__all__ = [
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
