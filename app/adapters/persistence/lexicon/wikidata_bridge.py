"""
app/adapters/persistence/lexicon/wikidata_bridge.py
--------------------------

Helpers for turning Wikidata *lexeme* JSON records into internal
lexicon entries and persisting them to disk.

Design goals
============

- Treat Wikidata as a *source* for building / refreshing local lexicon
  JSON files under `data/lexicon/`.
- Keep this module **offline-friendly**:
  - The main entry points operate on already-downloaded dumps
    (JSON or JSON-lines, plain or gzipped).
- Produce a **Structured Lexicon Artifact**:
  - Root metadata (language, version, source).
  - Flat lemma index (O(1) lookup).
  - Domain shards (core, people, science) for efficient loading.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Union

logger = logging.getLogger(__name__)

# Output schema version (must be int for loader + tests)
SCHEMA_VERSION: int = 2

# What tests expect for provenance
DEFAULT_SOURCE: str = "wikidata_lexeme_dump"

# Minimal POS mapping needed by unit tests (extend as desired)
DEFAULT_LEXICAL_CATEGORY_MAP: Dict[str, str] = {
    "Q24905": "NOUN",  # noun
    "Q34698": "ADJ",   # adjective (common)
    "Q36484": "VERB",  # verb (common)
    "Q380057": "PROPN",  # proper noun (sometimes used)
}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------


def _iter_json_records(path: Path) -> Iterator[Mapping[str, Any]]:
    """
    Yield JSON objects from a Wikidata dump file.
    Supports NDJSON, JSON Array (single-line or multi-line), and .gz compression.
    """
    if not path.exists():
        raise FileNotFoundError(f"Wikidata dump file not found: {path}")

    opener = gzip.open if path.suffix == ".gz" else open

    with opener(path, "rt", encoding="utf-8") as f:
        # Try NDJSON / JSON-array-per-line style first
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # Skip array delimiters and commas that appear in pretty-printed arrays
            if line in ("[", "]", ","):
                continue

            # Lines in JSON arrays are often " {...}," -> strip a trailing comma safely
            if line.endswith(","):
                line = line[:-1].rstrip()

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Not line-parseable; fall back to whole-file JSON parsing once.
                f.seek(0)
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            yield item
                elif isinstance(data, dict):
                    # Some dumps wrap records under a key; yield dict values if list-like
                    yield data
                return
            else:
                if isinstance(obj, dict):
                    yield obj
                elif isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict):
                            yield item


def _is_lexeme_record(record: Mapping[str, Any]) -> bool:
    """Decide whether a JSON record looks like a Wikidata Lexeme."""
    rec_type = record.get("type")
    if rec_type == "lexeme":
        return True

    rec_id = str(record.get("id", ""))
    if rec_id.startswith("L"):
        return True

    if "lemmas" in record:
        return True

    return False


def _get_lemma_for_lang(record: Mapping[str, Any], lang_code: str) -> Optional[str]:
    """Extract a lemma string for a given language code."""
    lemmas = record.get("lemmas")
    if not isinstance(lemmas, dict):
        return None

    # Exact language match
    entry = lemmas.get(lang_code)
    if isinstance(entry, dict):
        val = entry.get("value")
        return val if isinstance(val, str) and val else None

    # Fallback: primary subtag (e.g. "en" from "en-GB")
    primary = lang_code.split("-", 1)[0]
    if primary and primary != lang_code:
        entry = lemmas.get(primary)
        if isinstance(entry, dict):
            val = entry.get("value")
            return val if isinstance(val, str) and val else None

    return None


def _find_first_qid(obj: Any) -> Optional[str]:
    """Find the first string that looks like a Wikidata QID within a nested structure."""
    if isinstance(obj, str):
        return obj if obj.startswith("Q") else None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_first_qid(v)
            if found:
                return found
    if isinstance(obj, list):
        for v in obj:
            found = _find_first_qid(v)
            if found:
                return found
    return None


def _get_first_sense_qid(record: Mapping[str, Any]) -> Optional[str]:
    """Extract first sense QID (e.g., from sense.wikidataItem.id)."""
    senses = record.get("senses")
    if not isinstance(senses, list):
        return None
    for sense in senses:
        if not isinstance(sense, dict):
            continue
        # Prefer wikidataItem if present, otherwise search sense object
        qid = _find_first_qid(sense.get("wikidataItem")) or _find_first_qid(sense)
        if qid:
            return qid
    return None


def _extract_pos(
    record: Mapping[str, Any],
    lexical_category_map: Optional[Mapping[str, str]],
) -> Optional[str]:
    lexical_category = record.get("lexicalCategory")
    cat_id: Optional[str] = None

    if isinstance(lexical_category, dict):
        maybe = lexical_category.get("id")
        if isinstance(maybe, str):
            cat_id = maybe
    elif isinstance(lexical_category, str):
        cat_id = lexical_category

    if not cat_id:
        return None

    # Use provided map; fall back to defaults
    if lexical_category_map and cat_id in lexical_category_map:
        return lexical_category_map[cat_id]
    return DEFAULT_LEXICAL_CATEGORY_MAP.get(cat_id)


# ---------------------------------------------------------------------------
# Core Conversion Logic
# ---------------------------------------------------------------------------


def lexeme_from_wikidata_record(
    record: Mapping[str, Any],
    lang_code: str,
    *,
    lexical_category_map: Optional[Mapping[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Convert a Wikidata record to a dictionary compatible with the internal lemma-entry schema
    expected by unit tests:

      entry = {
        "lemma": "fisico",
        "pos": "NOUN",
        "qid": "Q169470",
        "forms": {"default": "fisico"},
        "features": {"lexeme_id": "L1"},
        "extra": {...}
      }
    """
    if not _is_lexeme_record(record):
        return None

    lemma = _get_lemma_for_lang(record, lang_code)
    if not lemma:
        return None

    lexeme_id = str(record.get("id") or "")
    pos = _extract_pos(record, lexical_category_map=lexical_category_map)
    qid = _get_first_sense_qid(record)

    entry: Dict[str, Any] = {
        "lemma": lemma,
        "pos": pos,
        "qid": qid,
        "forms": {"default": lemma},
        "features": {"lexeme_id": lexeme_id} if lexeme_id else {},
        "extra": {},
    }
    return entry


def _determine_domain(_entry: Dict[str, Any]) -> str:
    """
    Heuristic to determine which shard (file) a lexeme belongs to.
    Keep simple for now; default to 'core'.
    """
    return "core"


# ---------------------------------------------------------------------------
# Public Entry Points
# ---------------------------------------------------------------------------


def build_lexicon_from_dump(
    lang_code: str,
    dump_path: Union[str, Path],
    *,
    lexical_category_map: Optional[Mapping[str, str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Parses a Wikidata lexeme dump and constructs a structured lexicon dictionary.

    Returns:
        Dict with keys:
        - 'meta': Global metadata (language, schema_version, source, source_dump, entries_used, generated_at)
        - 'lemmas': Flat dictionary of {lemma: entry} for O(1) lookup.
        - 'domains': Optional shard mapping {domain: {lemma: entry}}
    """
    dump_path = Path(dump_path)

    # Prefer caller mapping, fall back to defaults for tests
    effective_map: Mapping[str, str] = lexical_category_map or DEFAULT_LEXICAL_CATEGORY_MAP

    lemmas: Dict[str, Any] = {}
    domains: Dict[str, Dict[str, Any]] = {}

    entries_used = 0

    for record in _iter_json_records(dump_path):
        entry = lexeme_from_wikidata_record(record, lang_code, lexical_category_map=effective_map)
        if not entry:
            continue

        lemma = entry["lemma"]

        # Duplicate handling: first wins
        if lemma in lemmas:
            continue

        domain = _determine_domain(entry)
        if domain not in domains:
            domains[domain] = {}

        lemmas[lemma] = entry
        domains[domain][lemma] = entry

        entries_used += 1
        if limit is not None and entries_used >= limit:
            break

    meta: Dict[str, Any] = {
        "language": lang_code,
        "schema_version": SCHEMA_VERSION,
        "source": DEFAULT_SOURCE,
        "source_dump": dump_path.name,
        "entries_used": entries_used,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "meta": meta,
        "lemmas": lemmas,
        "domains": domains,
    }


def save_shards(lexicon_data: Dict[str, Any], output_dir: Union[str, Path]) -> None:
    """
    Writes the 'domains' from the lexicon structure into separate JSON files.
    Shard format is loader-friendly:

      {
        "_meta": {...},
        "entries": { "lemma": {entry}, ... }
      }
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_meta = dict(lexicon_data.get("meta", {}) or {})
    domains = lexicon_data.get("domains", {}) or {}

    saved = 0
    for domain, entries in domains.items():
        if not entries:
            continue

        shard_file = output_path / f"{domain}.json"

        shard_content = {
            "_meta": {
                **base_meta,
                "domain": domain,
                "entries": len(entries),
            },
            "entries": entries,
        }

        with shard_file.open("w", encoding="utf-8") as f:
            json.dump(shard_content, f, indent=2, ensure_ascii=False)

        saved += 1

    logger.info("Saved %d shards to %s", saved, output_path)


__all__ = [
    "build_lexicon_from_dump",
    "save_shards",
    "lexeme_from_wikidata_record",
]
