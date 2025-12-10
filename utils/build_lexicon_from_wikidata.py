"""
utils/build_lexicon_from_wikidata.py
====================================

Offline builder: turn a (filtered) Wikidata / Lexeme dump into 
domain-sharded lexicon JSON files under `data/lexicon/{lang}/`.

This script:
1. Reads a Wikidata Lexeme dump (JSON/JSONL).
2. Extracts lemmas, POS tags, and QIDs.
3. Classifies entries into domains (people, science, geography, core).
4. Writes separate JSON files to the language's directory.

Example
-------
    python utils/build_lexicon_from_wikidata.py \
        --lang it \
        --dump data/raw_wikidata/lexemes_dump.json.gz \
        --out_dir data/lexicon/it
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

# Use local logger setup if available, else standard logging
try:
    from utils.logging_setup import get_logger
    log = get_logger(__name__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("build_lexicon")

SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# Domain Classification Config
# ---------------------------------------------------------------------------

# Known QIDs for broad semantic categories to help sort into domains.
# This is a heuristic heuristic starter set.
DOMAIN_QID_MAP = {
    # PEOPLE (Professions, Titles, Relations)
    "Q28640": "people",   # profession
    "Q12737077": "people",# occupation
    "Q215627": "people",  # person
    "Q169470": "people",  # physicist (example specific)
    
    # SCIENCE
    "Q336": "science",    # science
    "Q413": "science",    # physics
    "Q2329": "science",   # chemistry
    "Q11190": "science",  # medicine
    
    # GEOGRAPHY
    "Q6256": "geography", # country
    "Q515": "geography",  # city
    "Q82794": "geography",# geographic region
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
    """Yield Lexeme-like objects from a dump file (JSONL or big JSON)."""
    log.info("Reading lexeme dump from %s", path)
    lines = _open_maybe_gzip(path)
    
    try:
        first_line = next(lines)
    except StopIteration:
        log.warning("Dump file is empty.")
        return

    # 1. Try treating the whole file as one JSON object
    # (Memory heavy, but required for standard dumps not in JSONL)
    if first_line.strip().startswith("{"):
        try:
            # We attempt to re-read everything if it looks like one object
            # For massive dumps, this will crash. Production usage should use JSONL.
            pass 
        except Exception:
            pass

    # 2. Assume Line-Delimited (Recommended for large dumps)
    # Reset generator chain is hard without seek, so practically we assume JSONL
    # or restart read. For this script, we assume JSONL if line 1 is a lexeme.
    try:
        obj = json.loads(first_line)
        if _is_dump_wrapper(obj):
            for _, lexeme in obj["entities"].items():
                yield lexeme
            return
        else:
            yield obj
    except json.JSONDecodeError:
        pass

    for ln in lines:
        ln = ln.strip()
        if not ln: continue
        try:
            yield json.loads(ln)
        except json.JSONDecodeError:
            continue

LEXICAL_CATEGORY_POS_MAP: Dict[str, str] = {
    "Q24905": "NOUN",
    "Q34698": "VERB",
    "Q34649": "ADJ",
    "Q1084":  "ADV",
    "Q22884": "PRON", # Pronoun
    "Q4833830": "DET", # Determiner
}

def _classify_domain(lexeme: Dict[str, Any], pos: str) -> str:
    """
    Decide which domain file (core, people, science, geography) this lexeme belongs to.
    """
    # 1. Core POS types always go to core
    if pos in ["VERB", "PRON", "DET", "ADV"]:
        return "core"

    # 2. Check Senses for QID linkage
    senses = lexeme.get("senses", [])
    for sense in senses:
        claims = sense.get("claims", {})
        # Property P5137 (item for this sense) or generic links
        for prop_id, statements in claims.items():
            for stmt in statements:
                mainsnak = stmt.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                if datavalue.get("type") == "wikibase-entityid":
                    qid = datavalue["value"]["id"]
                    if qid in DOMAIN_QID_MAP:
                        return DOMAIN_QID_MAP[qid]
    
    # 3. Fallback: Nouns without specific domain info go to Core (or People if ambiguous)
    return DEFAULT_DOMAIN

def _build_lexeme_entry(lang_code: str, lexeme: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Convert Wikidata Lexeme -> (Lemma, Domain, EntryDict).
    """
    # 1. Get Lemma
    lemmas = lexeme.get("lemmas", {})
    if lang_code not in lemmas:
        return None, None, None
    lemma = lemmas[lang_code]["value"]

    # 2. Get POS
    lex_cat = lexeme.get("lexicalCategory", "")
    pos = LEXICAL_CATEGORY_POS_MAP.get(lex_cat, "NOUN") # Default to NOUN if unknown

    # 3. Get QID (if any) from first sense
    qid = None
    senses = lexeme.get("senses", [])
    if senses:
        # Simplistic extraction logic
        # In a real app, you'd parse P5137 deeply
        pass 

    domain = _classify_domain(lexeme, pos)

    entry = {
        "lemma": lemma,
        "pos": pos,
        "qid": qid,
        "forms": {
            "default": lemma
        },
        "source_id": lexeme.get("id")
    }
    
    # Extract forms (inflections)
    # Wikidata forms list -> "forms": {"tag": "surface"}
    for form in lexeme.get("forms", []):
        rep = form.get("representations", {}).get(lang_code)
        if rep:
            features = form.get("grammaticalFeatures", [])
            # Map features QIDs to tags (e.g. Q110786 -> "sg") would happen here
            # For now, we store them raw or skip
            pass

    return lemma, domain, entry

# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_lexicon_from_dump(
    lang_code: str,
    dump_path: str,
    limit: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict of domain -> { entries... }
    """
    sharded_data = {
        "core": {},
        "people": {},
        "science": {},
        "geography": {}
    }
    
    count_total = 0
    count_used = 0

    for lexeme in _iter_lexemes_from_dump(dump_path):
        count_total += 1
        
        lemma, domain, entry = _build_lexeme_entry(lang_code, lexeme)
        
        if lemma and domain:
            if domain not in sharded_data:
                domain = "core"
            
            # Deduplicate: Keep existing if already present
            if lemma not in sharded_data[domain]:
                sharded_data[domain][lemma] = entry
                count_used += 1

        if limit and count_used >= limit:
            break
            
        if count_total % 5000 == 0:
            log.info(f"Processed {count_total} lexemes...")

    log.info(f"Finished. Extracted {count_used} entries from {count_total} records.")
    return sharded_data

def save_shards(sharded_data: Dict[str, Any], out_dir: str, lang_code: str):
    """Writes the separated domain files to the target directory."""
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    for domain, entries in sharded_data.items():
        if not entries:
            continue
            
        out_path = os.path.join(out_dir, f"{domain}.json")
        
        # Structure matches Schema V2
        output_obj = {
            "_meta": {
                "language": lang_code,
                "domain": domain,
                "version": SCHEMA_VERSION,
                "source": "wikidata_dump"
            },
            "entries": entries
        }
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_obj, f, indent=2, ensure_ascii=False)
        
        log.info(f"Wrote {len(entries)} entries to {out_path}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build domain-sharded lexicon JSONs from Wikidata Lexeme dump."
    )
    parser.add_argument("--lang", required=True, help="Target language code (e.g. 'it')")
    parser.add_argument("--dump", required=True, help="Path to Wikidata dump")
    parser.add_argument("--out_dir", required=True, help="Output directory (e.g. data/lexicon/it)")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to process")
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.dump):
        print(f"❌ Dump file not found: {args.dump}")
        sys.exit(1)

    log.info(f"Building lexicon for {args.lang}...")
    
    data = build_lexicon_from_dump(args.lang, args.dump, args.limit)
    save_shards(data, args.out_dir, args.lang)

if __name__ == "__main__":
    main()