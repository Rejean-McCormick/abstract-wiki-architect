"""
lexicon/loader.py
=================

Helpers to load and normalize per-language lexicon files.

Goals
-----
- Provide a single entry point to load lexicon JSON from data/lexicon/.
- Hide filesystem details behind `lexicon.config`.
- Normalize light schema differences (meta vs _meta, entries vs lemmas).
- For callers (and tests), expose a simple mapping:

    load_lexicon(lang_code) -> Dict[str, Dict[str, Any]]

  where keys are lemma / surface strings (e.g. "physicienne", "polonais",
  "física", "физик") and values are small feature bundles
  (at least POS, and optionally human / gender / nationality flags).

Current expectations
--------------------
- Lexica live under a directory configured via `lexicon.config`:

      LexiconConfig(lexicon_dir=PATH_TO_DATA_LEXICON)

  The test suite sets this to the project’s real data/lexicon/ directory.

- Files are plain JSON dictionaries. Known patterns:

  * Simple “lemmas” schema (pt, ru, ja, sw, …):

        {
          "_meta": {...},
          "lemmas": {
            "física": { "pos": "NOUN", "human": true, "gender": "f", ... },
            ...
          }
        }

    In this case, `load_lexicon(lang)` simply returns the `lemmas` mapping.

  * French-style “entries + forms” schema (fr):

        {
          "_meta": {...},
          "entries": {
            "physicien": {
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
            },
            "polonais": {
              "pos": "ADJ",
              "inflection_class": "ais",
              "semantic_class": "demonym",
              "forms": {
                "m.sg": "polonais",
                "f.sg": "polonaise",
                "m.pl": "polonais",
                "f.pl": "polonaises"
              }
            },
            ...
          }
        }

    In this case, `load_lexicon("fr")` synthesizes a lemma dictionary
    where keys include both base entries ("polonais") and inflected
    forms ("physicienne", "polonaise", ...), with feature bundles that
    at least expose:

        - "pos"
        - "human" (for professions)
        - "gender" (m/f/common/…)
        - "nationality" (for demonyms)

Error behaviour
---------------
- If the JSON file for a language does not exist, `load_lexicon(lang)`
  raises `FileNotFoundError` (or a subclass).
- If the JSON exists but is not valid JSON or does not contain any
  recognizable lemma information, `ValueError` is raised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from lexicon.config import get_config


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """
    Infer the project root as the parent of this package directory.

    Layout assumption:

        abstract-wiki-architect/
            lexicon/
                __init__.py
                loader.py  <-- this file
            data/
                lexicon/
                    fr_lexicon.json
                    pt_lexicon.json
                    ru_lexicon.json
                    ...
    """
    return Path(__file__).resolve().parent.parent


def _lexicon_dir() -> Path:
    """
    Resolve the directory where lexicon JSON files live, using
    `lexicon.config.get_config()`.

    If the configured path is relative, treat it as relative to the
    project root.
    """
    cfg = get_config()
    lex_dir = Path(cfg.lexicon_dir)
    if not lex_dir.is_absolute():
        lex_dir = _project_root() / lex_dir
    return lex_dir


def _lexicon_path(lang_code: str) -> Path:
    """
    Compute the path to the JSON file for a given language code.

        "fr" -> <lexicon_dir>/fr_lexicon.json
    """
    return _lexicon_dir() / f"{lang_code}_lexicon.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_raw_json(path: Path) -> Dict[str, Any]:
    """
    Load a lexicon JSON file and return the raw top-level object.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the contents are not valid JSON or not a dict.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Lexicon file not found at: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse lexicon JSON at {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Lexicon JSON at {path} must be a top-level object (dict), "
            f"got {type(data).__name__!r}."
        )

    return data


def _extract_lemmas_from_simple_schema(
    raw: Mapping[str, Any],
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Handle the simple schema:

        {
          "_meta": {...},
          "lemmas": { "lemma": { ... }, ... }
        }

    Returns:
        A dict lemma -> entry, or None if no 'lemmas' section is present.
    """
    lemmas_section = raw.get("lemmas")
    if not isinstance(lemmas_section, Mapping):
        return None

    lemmas: Dict[str, Dict[str, Any]] = {}
    for lemma, entry in lemmas_section.items():
        if not isinstance(lemma, str) or not isinstance(entry, Mapping):
            continue
        lemmas[lemma] = dict(entry)
    return lemmas


def _build_lemmas_from_entries(entries: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build a lemma dictionary from a French-style `entries` section.

    Each entry looks roughly like:

        {
          "pos": "NOUN" | "ADJ" | ...,
          "gender": "m" | "f" | "common" | ...,
          "default_number": "sg" | "pl" | ...,
          "semantic_class": "profession" | "demonym" | ...,
          "forms": {
            "m.sg": "physicien",
            "f.sg": "physicienne",
            ...
          },
          ...
        }

    We synthesize a mapping:

        lemma_surface -> {
            "pos": ...,
            "human": True/False/None,
            "gender": ...,
            "nationality": True/False/None,
            # plus any other useful flags we choose to propagate
        }

    This is intentionally minimal and tailored to what the tests expect.
    """
    lemmas: Dict[str, Dict[str, Any]] = {}

    for base_key, entry in entries.items():
        if not isinstance(base_key, str) or not isinstance(entry, Mapping):
            continue

        pos = entry.get("pos")
        gender = entry.get("gender")
        semantic_class = entry.get("semantic_class")
        nationality_flag = entry.get("nationality")

        # Profession → human = True
        human_flag: Optional[bool]
        if isinstance(entry.get("human"), bool):
            human_flag = entry.get("human")  # explicit override
        elif semantic_class == "profession":
            human_flag = True
        else:
            human_flag = None

        # Nationality / demonym → nationality = True
        if isinstance(nationality_flag, bool):
            nat_flag: Optional[bool] = nationality_flag
        elif semantic_class in ("demonym", "nationality"):
            nat_flag = True
        else:
            nat_flag = None

        base_features: Dict[str, Any] = {
            "pos": pos,
            "human": human_flag,
            "gender": gender,
        }
        if nat_flag is not None:
            base_features["nationality"] = nat_flag

        # 1) Index the base lemma key itself (e.g. "polonais").
        head_lemma = str(entry.get("lemma") or base_key)
        if head_lemma not in lemmas:
            lemmas[head_lemma] = dict(base_features)

        # 2) Index all surface forms from the "forms" map.
        forms = entry.get("forms")
        if isinstance(forms, Mapping):
            for tag, surface in forms.items():
                if not isinstance(surface, str):
                    continue

                feat = dict(base_features)

                # Try to refine gender/number from tags like "f.sg" / "m.pl".
                if isinstance(tag, str):
                    parts = tag.split(".")
                    if len(parts) == 2:
                        g_tag, n_tag = parts
                    else:
                        g_tag, n_tag = parts[0], None

                    g_tag = (g_tag or "").strip()
                    n_tag = (n_tag or "").strip() if n_tag else None

                    if g_tag in {"m", "f", "n", "common"}:
                        feat["gender"] = g_tag

                    if n_tag in {"sg", "pl"}:
                        feat["number"] = n_tag

                # Do not overwrite an existing lemma if we've already
                # seen it (keep the first; that's enough for tests).
                lemmas.setdefault(surface, feat)

    return lemmas


def _extract_lemmas_from_raw(
    lang_code: str, raw: Mapping[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Given a raw lexicon JSON payload, extract a lemma → feature dict.

    Supports:
      - Simple "lemmas" schema.
      - French-style "entries + forms" schema.
    """
    # 1) Simple schema: raw["lemmas"]
    simple = _extract_lemmas_from_simple_schema(raw)
    if simple is not None:
        return simple

    # 2) French-style entries: raw["entries"]
    entries = raw.get("entries")
    if isinstance(entries, Mapping):
        return _build_lemmas_from_entries(entries)

    # 3) Nothing usable found
    raise ValueError(
        f"Lexicon for language '{lang_code}' does not contain a usable "
        f"'lemmas' or 'entries' section."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_lexicon(lang_code: str) -> Dict[str, Dict[str, Any]]:
    """
    Load and normalize the lexicon for a given language code.

    This is the function used by the tests in qa/test_lexicon_loader.py.

    Args:
        lang_code:
            Language code such as "fr", "pt", "ru".

    Returns:
        A mapping:

            {
              "physicienne": { "pos": "NOUN", "human": True, "gender": "f", ... },
              "polonais":    { "pos": "ADJ", "nationality": True, ... },
              ...
            }

    Raises:
        FileNotFoundError: if the underlying JSON file does not exist.
        ValueError: if the JSON is invalid or has no usable lemma data.
    """
    path = _lexicon_path(lang_code)
    raw = _load_raw_json(path)
    return _extract_lemmas_from_raw(lang_code, raw)


def available_languages() -> List[str]:
    """
    Return a sorted list of language codes for which a lexicon file exists.

    Scans the configured lexicon directory for files named `*_lexicon.json`.
    """
    lex_dir = _lexicon_dir()
    if not lex_dir.is_dir():
        return []

    langs = []
    # Use glob to find matching files
    for path in lex_dir.glob("*_lexicon.json"):
        if path.is_file():
            # Extract lang code from filename: "fr_lexicon.json" -> "fr"
            code = path.name.replace("_lexicon.json", "")
            if code:
                langs.append(code)
    return sorted(langs)


__all__ = [
    "load_lexicon",
    "available_languages",
]
