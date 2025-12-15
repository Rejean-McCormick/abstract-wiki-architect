# lexicon\wikidata_bridge.py
"""
lexicon/wikidata_bridge.py
--------------------------

Helpers for turning Wikidata *lexeme* JSON records into internal
`Lexeme` objects (from `lexicon.index`).

Design goals
============

- Treat Wikidata as a *source* for building / refreshing local lexicon
  JSON files under `data/lexicon/`.
- Keep this module **offline-friendly**:
  - The main entry points operate on already-downloaded dumps
    (JSON or JSON-lines, plain or gzipped).
  - Any online / HTTP usage can be added on top, but is not required.
- Do not overfit to every detail of the Wikidata schema; instead:
  - Extract lemmas, lexical category, and simple glosses.
  - Preserve the full record in `Lexeme.data["wikidata_raw"]` for
    advanced consumers.

Typical usage (offline)
=======================

In `utils/build_lexicon_from_wikidata.py` you might do::

    from pathlib import Path
    from lexicon.wikidata_bridge import build_lexemes_from_lexeme_dump

    lang = "en"
    dump_path = Path("data/raw_wikidata/lexemes_dump.json.gz")
    lexemes = build_lexemes_from_lexeme_dump(lang, dump_path)

    # Convert to your local JSON schema and save under
    # data/lexicon/en_lexicon.json

We deliberately keep this module generic; how you group / label the
lexemes (professions vs nationalities vs general nouns) is up to the
builder script.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

from .index import Lexeme


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------


def _iter_json_records(path: Path) -> Iterator[Mapping[str, Any]]:
    """
    Yield JSON objects from a Wikidata dump file.

    The function is tolerant to two common formats:

        1. One JSON object per line (NDJSON).
        2. A single large JSON array of objects.

    It also supports gzipped files if the extension is `.gz`.
    """
    if not path.exists():
        raise FileNotFoundError(f"Wikidata dump file not found: {path}")

    opener = gzip.open if path.suffix == ".gz" else open

    with opener(path, "rt", encoding="utf-8") as f:
        # Try naive NDJSON first (one JSON object per line).
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Skip array delimiters in some dump formats
            if line in ("[", "]", ","):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # If the file is a single giant JSON array,
                # restart and parse once.
                f.seek(0)
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        "Failed to parse Wikidata dump as JSON or NDJSON: " f"{path}"
                    ) from e

                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield item
                return
            else:
                if isinstance(obj, dict):
                    yield obj
        # If we reach here, NDJSON mode exhausted successfully.


def _is_lexeme_record(record: Mapping[str, Any]) -> bool:
    """
    Decide whether a JSON record looks like a Wikidata Lexeme.

    Heuristics:
        - "type" == "lexeme" OR
        - "id" starts with "L" (e.g. "L1234") OR
        - has a "lemmas" top-level key.
    """
    rec_type = record.get("type")
    if rec_type == "lexeme":
        return True

    rec_id = str(record.get("id", ""))
    if rec_id.startswith("L"):
        return True

    if "lemmas" in record:
        return True

    return False


def _get_lemma_for_lang(
    record: Mapping[str, Any],
    lang_code: str,
) -> Optional[str]:
    """
    Extract a lemma string for a given language code from a Lexeme record.

    Wikidata Lexeme structure for lemmas is typically::

        {
          "lemmas": {
            "en": { "value": "physicist", "language": "en" },
            "fr": { "value": "physicien", "language": "fr" }
          }
        }

    This function:

      - looks for an exact match on `lang_code`,
      - falls back to the primary subtag (e.g. "en" for "en-GB").
    """
    lemmas = record.get("lemmas")
    if not isinstance(lemmas, dict):
        return None

    # Exact language match
    entry = lemmas.get(lang_code)
    if isinstance(entry, dict):
        value = entry.get("value")
        if isinstance(value, str) and value:
            return value

    # Fallback: primary subtag
    primary = lang_code.split("-", 1)[0]
    if primary and primary != lang_code:
        entry = lemmas.get(primary)
        if isinstance(entry, dict):
            value = entry.get("value")
            if isinstance(value, str) and value:
                return value

    return None


def _get_first_gloss_for_lang(
    record: Mapping[str, Any],
    lang_code: str,
) -> Optional[str]:
    """
    Extract the first sense gloss for a given language, if any.

    Lexeme senses are typically represented as::

        "senses": [
          {
            "id": "L1234-S1",
            "glosses": {
              "en": {
                "value": "person who does physics",
                "language": "en"
              }
            }
          }
        ]
    """
    senses = record.get("senses")
    if not isinstance(senses, list):
        return None

    primary = lang_code.split("-", 1)[0]

    for sense in senses:
        if not isinstance(sense, dict):
            continue
        glosses = sense.get("glosses")
        if not isinstance(glosses, dict):
            continue

        # Exact lang match first
        for code in (lang_code, primary):
            if not code:
                continue
            gloss_entry = glosses.get(code)
            if isinstance(gloss_entry, dict):
                value = gloss_entry.get("value")
                if isinstance(value, str) and value:
                    return value

    return None


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------


def lexeme_from_wikidata_record(
    record: Mapping[str, Any],
    lang_code: str,
    *,
    lexical_category_map: Optional[Mapping[str, str]] = None,
) -> Optional[Lexeme]:
    """
    Convert a single Wikidata lexeme record to a `Lexeme` for a
    specific language.

    Args:
        record:
            A JSON object representing a Wikidata Lexeme.
        lang_code:
            Target language code (e.g. "en", "fr", "ja").
        lexical_category_map:
            Optional mapping from Wikidata lexical category ID to
            coarse POS, for example::

                {"Q1084": "NOUN"}  # noun

            If not provided, `pos` is left as None.

    Returns:
        A `Lexeme` or None if the record does not have an appropriate
        lemma for the language.
    """
    if not _is_lexeme_record(record):
        return None

    lemma = _get_lemma_for_lang(record, lang_code)
    if not lemma:
        return None

    # Wikidata Lexeme IDs look like "L1234"
    lexeme_id = str(record.get("id") or "")

    # lexicalCategory may be something like
    # {"entity-type": "item", "id": "Q1084"}
    lexical_category = record.get("lexicalCategory")
    pos: Optional[str] = None
    if isinstance(lexical_category, dict):
        cat_id = lexical_category.get("id")
        if isinstance(cat_id, str) and lexical_category_map:
            pos = lexical_category_map.get(cat_id)

    gloss = _get_first_gloss_for_lang(record, lang_code)

    # Preserve the full record under a dedicated key for advanced users
    data: Dict[str, Any] = {
        "wikidata_lexeme_id": lexeme_id,
        "wikidata_language": lang_code,
    }
    # Shallow copy to avoid mutating the original
    data["wikidata_raw"] = dict(record)

    if gloss and "sense" not in data:
        data["sense"] = gloss

    # For now we use the lemma as key; callers can choose to rename keys
    # or disambiguate if necessary.
    key = lemma

    return Lexeme(
        language=lang_code,
        key=key,
        lemma=lemma,
        pos=pos,
        sense=gloss,
        data=data,
    )


def build_lexemes_from_lexeme_dump(
    lang_code: str,
    dump_path: Path,
    *,
    lexical_category_map: Optional[Mapping[str, str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Lexeme]:
    """
    Build a dictionary of `Lexeme` objects for a given language from a
    Wikidata lexeme dump.

    Args:
        lang_code:
            Target language (e.g. "en", "fr", "ja", "sw").
        dump_path:
            Path to a Wikidata Lexeme dump file. Can be plain JSON or
            gzipped (ending in `.gz`).
        lexical_category_map:
            Optional mapping from Wikidata lexical categories to coarse
            POS tags.

            Example::

                {
                    "Q1084": "NOUN",   # noun
                    "Q24905": "VERB",  # verb
                }

        limit:
            Optional maximum number of lexemes to extract (for testing).

    Returns:
        Dict[str, Lexeme]: mapping of key -> Lexeme.

        Keys are by default the lemma string. Post-processing code can
        re-key this dict if needed (for example, to avoid collisions).
    """
    lexemes: Dict[str, Lexeme] = {}
    count = 0

    for record in _iter_json_records(dump_path):
        if not _is_lexeme_record(record):
            continue

        lex = lexeme_from_wikidata_record(
            record,
            lang_code,
            lexical_category_map=lexical_category_map,
        )
        if lex is None:
            continue

        # Simple collision handling: keep the first, ignore later ones.
        # Builder scripts can implement more sophisticated strategies.
        if lex.key not in lexemes:
            lexemes[lex.key] = lex

        count += 1
        if limit is not None and count >= limit:
            break

    return lexemes


__all__ = [
    "lexeme_from_wikidata_record",
    "build_lexemes_from_lexeme_dump",
]
