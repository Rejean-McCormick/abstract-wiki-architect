# utils/build_lexicon_from_wikidata.py
"""
utils/build_lexicon_from_wikidata.py
====================================

Offline builder: turn a (filtered) Wikidata / Lexeme dump into
domain-sharded lexicon JSON files under `data/lexicon/{lang}/`.

This script:
1. Reads a Wikidata Lexeme dump (JSON/JSONL, optionally .gz).
2. Extracts lemmas, POS tags, and (optional) sense-linked QIDs.
3. Classifies entries into domains (people, science, geography, core).
4. Writes separate JSON files to the language's directory.

[FIX] Output is compatible with the runtime loader AND unit tests:
  - meta.schema_version is an integer (not a string)
  - top-level uses "entries" (schema v2 preferred)
  - each entry uses wikidata_qid (alias: qid still present for backwards consumers)
  - does not emit a redundant "key" field (key is the dict key)
  - meta.source == "wikidata_lexeme_dump"
  - meta.source_dump == basename(dump_path)
  - meta.entries_used == number of unique lemmas emitted
  - each entry has features.lexeme_id
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

# Ensure project root is on path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.tool_logger import ToolLogger  # noqa: E402

log = ToolLogger(__file__)

# [FIX] Schema version for runtime loader expectations (meta.schema_version must be int)
SCHEMA_VERSION = 2

# [FIX] Unit tests expect this exact source name
SOURCE_NAME = "wikidata_lexeme_dump"

# ---------------------------------------------------------------------------
# Domain Classification Config
# ---------------------------------------------------------------------------

DOMAIN_QID_MAP = {
    # PEOPLE
    "Q28640": "people",      # profession
    "Q12737077": "people",   # occupation
    "Q215627": "people",     # person
    "Q169470": "people",     # physicist (example specific)

    # SCIENCE
    "Q336": "science",       # science
    "Q413": "science",       # physics
    "Q2329": "science",      # chemistry
    "Q11190": "science",     # medicine

    # GEOGRAPHY
    "Q6256": "geography",    # country
    "Q515": "geography",     # city
    "Q82794": "geography",   # geographic region
    "Q15634566": "geography" # demonym
}

DEFAULT_DOMAIN = "core"

# ---------------------------------------------------------------------------
# Lexeme parsing helpers
# ---------------------------------------------------------------------------


def _open_maybe_gzip(path: str) -> Iterable[str]:
    """Open a file that may or may not be gzipped and yield lines."""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield from f
    else:
        with open(path, "r", encoding="utf-8") as f:
            yield from f


def _is_dump_wrapper(obj: Any) -> bool:
    """Check if object is a standard Wikidata dump wrapper."""
    return isinstance(obj, dict) and "entities" in obj and isinstance(obj["entities"], dict)


def _iter_lexemes_from_dump(path: str) -> Iterator[Dict[str, Any]]:
    """Yield Lexeme-like objects from a dump file (JSONL or big JSON wrapper)."""
    log.stage("Ingest", f"Reading lexeme dump: {path}")
    lines = _open_maybe_gzip(path)

    try:
        first_line = next(lines)
    except StopIteration:
        log.warning("Dump file is empty.")
        return

    try:
        obj = json.loads(first_line)
        if _is_dump_wrapper(obj):
            for _, lexeme in obj["entities"].items():
                if isinstance(lexeme, dict):
                    yield lexeme
            return
        else:
            if isinstance(obj, dict):
                yield obj
    except json.JSONDecodeError:
        # fall through to JSONL loop
        pass

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            continue


LEXICAL_CATEGORY_POS_MAP: Dict[str, str] = {
    "Q24905": "NOUN",
    "Q34698": "VERB",
    "Q34649": "ADJ",
    "Q1084": "ADV",
    "Q22884": "PRON",
    "Q4833830": "DET",
}


def _extract_any_qid_from_senses(lexeme: Dict[str, Any]) -> Optional[str]:
    """
    Best-effort extraction of a linked QID from senses.

    Supports:
      - sense["wikidataItem"]["id"]   (used by unit tests)
      - sense["claims"][...]["mainsnak"]["datavalue"]... (real dumps)
    """
    senses = lexeme.get("senses") or []
    if not isinstance(senses, list):
        return None

    for sense in senses:
        if not isinstance(sense, dict):
            continue

        # [FIX] Tests use: {"wikidataItem": {"id": "Q..."}}
        wikidata_item = sense.get("wikidataItem")
        if isinstance(wikidata_item, dict):
            qid = wikidata_item.get("id")
            if isinstance(qid, str) and qid.startswith("Q"):
                return qid

        claims = sense.get("claims") or {}
        if not isinstance(claims, dict):
            continue

        for _prop_id, statements in claims.items():
            if not isinstance(statements, list):
                continue
            for stmt in statements:
                if not isinstance(stmt, dict):
                    continue
                mainsnak = stmt.get("mainsnak") or {}
                if not isinstance(mainsnak, dict):
                    continue
                datavalue = mainsnak.get("datavalue") or {}
                if not isinstance(datavalue, dict):
                    continue

                if datavalue.get("type") == "wikibase-entityid":
                    value = datavalue.get("value") or {}
                    if isinstance(value, dict):
                        qid = value.get("id")
                        if isinstance(qid, str) and qid.startswith("Q"):
                            return qid
    return None


def _classify_domain(lexeme: Dict[str, Any], pos: str) -> str:
    """
    Decide which domain file (core, people, science, geography) this lexeme belongs to.
    """
    if pos in {"VERB", "PRON", "DET", "ADV"}:
        return "core"

    senses = lexeme.get("senses", [])
    if isinstance(senses, list):
        for sense in senses:
            if not isinstance(sense, dict):
                continue
            claims = sense.get("claims", {})
            if not isinstance(claims, dict):
                continue
            for _prop_id, statements in claims.items():
                if not isinstance(statements, list):
                    continue
                for stmt in statements:
                    if not isinstance(stmt, dict):
                        continue
                    mainsnak = stmt.get("mainsnak", {})
                    if not isinstance(mainsnak, dict):
                        continue
                    datavalue = mainsnak.get("datavalue", {})
                    if not isinstance(datavalue, dict):
                        continue
                    if datavalue.get("type") == "wikibase-entityid":
                        value = datavalue.get("value", {})
                        if isinstance(value, dict):
                            qid = value.get("id")
                            if isinstance(qid, str) and qid in DOMAIN_QID_MAP:
                                return DOMAIN_QID_MAP[qid]

    return DEFAULT_DOMAIN


def _build_lexeme_entry(
    lang_code: str, lexeme: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Convert Wikidata Lexeme -> (lemma, domain, entry_dict).

    Entry dict conforms to the runtime loader and unit tests:
      - lemma, pos, wikidata_qid, qid(alias), forms, extra
      - features.lexeme_id is required by tests
    """
    lemmas = lexeme.get("lemmas", {})
    if not isinstance(lemmas, dict) or lang_code not in lemmas:
        return None, None, None

    lemma_obj = lemmas[lang_code]
    if not isinstance(lemma_obj, dict):
        return None, None, None
    lemma = lemma_obj.get("value")
    if not isinstance(lemma, str) or not lemma.strip():
        return None, None, None
    lemma = lemma.strip()

    lex_cat = lexeme.get("lexicalCategory", "")
    if isinstance(lex_cat, dict):
        lex_cat = lex_cat.get("id") or ""
    pos = LEXICAL_CATEGORY_POS_MAP.get(str(lex_cat), "NOUN")

    wikidata_qid = _extract_any_qid_from_senses(lexeme)
    domain = _classify_domain(lexeme, pos)

    lexeme_id = str(lexeme.get("id") or "")

    entry: Dict[str, Any] = {
        "lemma": lemma,
        "pos": pos,
        # runtime expects wikidata_qid; keep qid as alias for older consumers/tests
        "wikidata_qid": wikidata_qid,
        "qid": wikidata_qid,
        "forms": {"default": lemma},
        # [FIX] tests expect entry["features"]["lexeme_id"]
        "features": {"lexeme_id": lexeme_id},
        # optional back-compat/debug
        "source_id": lexeme_id,
        "extra": {},
    }

    # Optional forms: keep as extra for now
    forms = lexeme.get("forms") or []
    if isinstance(forms, list):
        for form in forms:
            if not isinstance(form, dict):
                continue
            reps = form.get("representations") or {}
            if not isinstance(reps, dict):
                continue
            rep = reps.get(lang_code)
            if isinstance(rep, dict):
                value = rep.get("value")
                if isinstance(value, str) and value and value != lemma:
                    # We do not know tag mapping yet; store as an untyped form list
                    entry["extra"].setdefault("forms_raw", []).append(value)

    return lemma, domain, entry


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_lexicon_from_dump(
    lang_code: str,
    dump_path: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build a single lexicon object compatible with the runtime loader and unit tests.

    Returns:
      {
        "meta": {...},
        "lemmas": {...},   # legacy alias
        "entries": {...},  # preferred
      }
    """
    log.stage("Classify", "Extracting lemmas/POS and assigning domains")

    lexicon: Dict[str, Any] = {
        "meta": {
            "language": lang_code,
            "schema_version": SCHEMA_VERSION,
            # [FIX] tests expect this exact value
            "source": SOURCE_NAME,
            # [FIX] tests expect the original filename
            "source_dump": os.path.basename(dump_path),
            # [FIX] tests expect entries_used
            "entries_used": 0,
        },
        "entries": {},
        "lemmas": {},  # legacy alias for compatibility
        "domains": {
            "core": {},
            "people": {},
            "science": {},
            "geography": {},
        },
    }

    count_total = 0
    count_used = 0

    for lexeme in _iter_lexemes_from_dump(dump_path):
        count_total += 1

        lemma, domain, entry = _build_lexeme_entry(lang_code, lexeme)

        if lemma and domain and entry:
            entries = lexicon["entries"]
            if lemma not in entries:
                entries[lemma] = entry
                lexicon["lemmas"][lemma] = entry  # legacy
                # keep a domain index too
                dom = domain if domain in lexicon["domains"] else "core"
                lexicon["domains"][dom][lemma] = entry
                count_used += 1

        if limit and count_used >= limit:
            break

        if count_total % 5000 == 0:
            log.info("Processed %s lexemes...", count_total)

    log.info("Finished. Extracted %s entries from %s records.", count_used, count_total)
    lexicon["meta"]["entries_used"] = count_used
    return lexicon


def save_shards(lexicon: Dict[str, Any], out_dir: str, lang_code: str) -> None:
    """
    Writes domain-sharded files to the target directory in loader-compatible format.

    Each file is:
      {
        "meta": {...},
        "entries": {...}
      }
    """
    log.stage("Write", f"Writing domain shards to: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)

    meta_base = lexicon.get("meta") if isinstance(lexicon.get("meta"), dict) else {}
    domains = lexicon.get("domains") if isinstance(lexicon.get("domains"), dict) else {}

    for domain, entries in (domains or {}).items():
        if not isinstance(entries, dict) or not entries:
            continue

        out_path = os.path.join(out_dir, f"{domain}.json")

        output_obj = {
            "meta": {
                "language": lang_code,
                "domain": domain,
                "schema_version": SCHEMA_VERSION,
                "source": meta_base.get("source", SOURCE_NAME),
                "source_dump": meta_base.get("source_dump"),
                "entries_used": len(entries),
            },
            "entries": entries,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_obj, f, indent=2, ensure_ascii=False)

        log.info("Wrote %s entries to %s", len(entries), out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build domain-sharded lexicon JSONs from Wikidata Lexeme dump."
    )
    parser.add_argument("--lang", required=True, help="Target language code (e.g. 'it')")
    parser.add_argument("--dump", required=True, help="Path to Wikidata dump")
    parser.add_argument(
        "--out_dir", required=True, help="Output directory (e.g. data/lexicon/it)"
    )
    parser.add_argument("--limit", type=int, default=None, help="Max entries to process")

    args = parser.parse_args()

    log.header(
        {
            "language": args.lang,
            "dump": os.path.basename(args.dump),
            "out_dir": args.out_dir,
            "limit": args.limit if args.limit is not None else "none",
            "schema_version": SCHEMA_VERSION,
            "source": SOURCE_NAME,
        }
    )

    if not os.path.isfile(args.dump):
        log.error(f"Dump file not found: {args.dump}", fatal=True)

    lexicon = build_lexicon_from_dump(args.lang, args.dump, args.limit)
    save_shards(lexicon, args.out_dir, args.lang)

    # lightweight standardized tail
    domain_counts = {}
    domains = lexicon.get("domains") or {}
    if isinstance(domains, dict):
        for d, e in domains.items():
            if isinstance(e, dict) and e:
                domain_counts[f"{d}_entries"] = len(e)

    log.summary(
        {
            "entries_used": int((lexicon.get("meta") or {}).get("entries_used") or 0),
            **domain_counts,
        },
        success=True,
    )
    log.finish(success=True)


if __name__ == "__main__":
    main()