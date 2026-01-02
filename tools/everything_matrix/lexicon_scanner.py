# tools/everything_matrix/lexicon_scanner.py
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union, List

logger = logging.getLogger(__name__)

LEXICON_SCANNER_VERSION = "lexicon_scanner/3.0"

# -----------------------------------------------------------------------------
# Everything Matrix – Lexicon Scanner (Zone B only)
#
# Contract (used by build_index orchestrator):
#   scan_all_lexicons(lex_root: Path) -> dict[iso2, {"SEED":float,"CONC":float,"WIDE":float,"SEM":float}]
#
# Notes:
# - Side-effect free by default (no writes, no print, no logging config).
# - Normalizes all discovered lexicon folders to canonical ISO-639-1 (iso2) keys,
#   using config/iso_to_wiki.json (prefers iso2 when multiple codes map to same wiki).
# - Deep per-language scan stays available as debug:
#     scan_lexicon_health(code, lex_root) -> stats (includes diagnostics)
# -----------------------------------------------------------------------------

# v3.x maturity targets
TARGETS = {
    "core_low": 50,     # "functional" seed floor (5/10)
    "core_high": 200,   # production-ish seed (10/10)
    "conc_low": 50,     # "functional" domain floor (5/10)
    "conc_high": 500,   # production-ish domain (10/10)
}

PRIMARY_DOMAIN_SHARDS = (
    "people.json",
    "geography.json",
    "science.json",
)

# Non-domain / control files inside a language folder (ignored for domain totals)
NON_DOMAIN_FILES = {
    "core.json",
    "wide.json",
    "dialog.json",
    "schema.json",
}

MAX_WIDE_BYTES_TO_LOAD = 5_000_000  # 5 MB

# Internal collector for CLI warnings (populated during scans)
_SCAN_WARNINGS: List[str] = []

# -----------------------------------------------------------------------------
# Repo/normalization helpers
# -----------------------------------------------------------------------------
def _project_root_from_lex_root(lex_root: Path) -> Path:
    """
    lex_root is typically <repo>/data/lexicon.
    Best-effort derive repo root without relying on CWD.
    """
    p = lex_root.resolve()
    if p.name.lower() == "lexicon" and p.parent.name.lower() == "data":
        return p.parent.parent
    # fallback: go up two levels (reasonable for most layouts)
    try:
        return p.parents[1]
    except Exception:
        return p.parent


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


@lru_cache(maxsize=8)
def _load_iso_to_wiki(repo_root_str: str) -> Dict[str, Any]:
    repo = Path(repo_root_str)
    data = _read_json(repo / "config" / "iso_to_wiki.json")
    return data if isinstance(data, dict) else {}


def _build_wiki_to_iso2(iso_to_wiki: Mapping[str, Any]) -> Dict[str, str]:
    """
    Build reverse index: any (iso2/iso3/wiki) -> preferred iso2.
    Preference: for a given wiki code, choose the 2-letter ISO key if present.
    """
    preferred: Dict[str, str] = {}

    for k, v in iso_to_wiki.items():
        if not (isinstance(k, str) and len(k.strip()) == 2 and isinstance(v, dict)):
            continue
        wiki = v.get("wiki")
        if isinstance(wiki, str) and wiki.strip():
            preferred[wiki.strip().casefold()] = k.strip().casefold()

    wiki_to_iso2: Dict[str, str] = {}
    for k, v in iso_to_wiki.items():
        if not (isinstance(k, str) and isinstance(v, dict)):
            continue
        kk = k.strip().casefold()
        wiki = v.get("wiki")
        if not (isinstance(wiki, str) and wiki.strip()):
            continue
        wk = wiki.strip().casefold()
        iso2 = preferred.get(wk)
        if iso2 and len(iso2) == 2:
            wiki_to_iso2[kk] = iso2
            wiki_to_iso2[wk] = iso2

    return wiki_to_iso2


def _norm_to_iso2(code: str, *, wiki_to_iso2: Mapping[str, str]) -> Optional[str]:
    if not isinstance(code, str):
        return None
    k = code.strip().casefold()
    if not k:
        return None
    iso2 = wiki_to_iso2.get(k)
    if iso2 and len(iso2) == 2:
        return iso2
    if len(k) == 2:
        return k
    return None


# -----------------------------------------------------------------------------
# JSON extraction helpers (supports V2 and legacy shapes)
# -----------------------------------------------------------------------------
JsonObj = Union[Dict[str, Any], list, str, int, float, bool, None]


def _safe_load_json(path: Path) -> Optional[JsonObj]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        msg = f"Failed to load {path.name}: {e}"
        # Log to debug so as not to spam stdout during normal runs,
        # but collect it for the report 'warnings' block.
        logger.debug(msg)
        _SCAN_WARNINGS.append(f"{path.name}: {str(e)}")
        return {}


def _extract_section_maps(payload: JsonObj) -> Tuple[Dict[str, Mapping[str, Any]], Mapping[str, Any]]:
    """
    Returns (sections, meta):

    - sections: name -> mapping(lemma_key -> entry_obj)
      Supports:
        * V2: {"_meta": {...}, "entries": {...}}
        * Legacy: {"lemmas": {...}}
        * Mixed: {"entries": {...}, "professions": {...}, ...}
        * Flat dict of entries (best-effort)
    - meta: best-effort "_meta" dict (empty if missing)
    """
    meta: Mapping[str, Any] = {}
    sections: Dict[str, Mapping[str, Any]] = {}

    if not isinstance(payload, dict):
        return sections, meta

    raw_meta = payload.get("_meta") or payload.get("meta")
    if isinstance(raw_meta, dict):
        meta = raw_meta

    for key in ("entries", "lemmas", "lexemes", "items", "professions", "nationalities", "titles"):
        v = payload.get(key)
        if isinstance(v, dict):
            sections[key] = v

    if sections:
        return sections, meta

    filtered: Dict[str, Any] = {
        k: v
        for k, v in payload.items()
        if isinstance(k, str)
        and k not in ("_meta", "meta")
        and not k.startswith("_")
        and k not in ("timestamp", "version", "schema_version", "language", "domain", "source")
    }
    if filtered and all(isinstance(v, dict) for v in filtered.values()):
        sections["entries"] = filtered

    return sections, meta


def _iter_entry_dicts(sections: Mapping[str, Mapping[str, Any]]) -> Iterable[Dict[str, Any]]:
    for sec in sections.values():
        for v in sec.values():
            if isinstance(v, dict):
                yield v


def _looks_like_qid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    return s.startswith("Q") and s[1:].isdigit()


def _entry_has_qid(entry: Mapping[str, Any]) -> bool:
    for k in ("qid", "wikidata_qid", "wikidata_id"):
        if _looks_like_qid(entry.get(k)):
            return True

    meta = entry.get("metadata")
    if isinstance(meta, dict):
        for k in ("qid", "wikidata_qid", "wikidata_id"):
            if _looks_like_qid(meta.get(k)):
                return True

    return False


def _entry_has_forms(entry: Mapping[str, Any]) -> bool:
    forms = entry.get("forms")
    if isinstance(forms, dict) and len(forms) > 0:
        return True
    dem = entry.get("demonym")
    if isinstance(dem, dict) and len(dem) > 0:
        return True
    return False


def _count_sections(sections: Mapping[str, Mapping[str, Any]]) -> int:
    return int(sum(len(sec) for sec in sections.values()))


def _score_count(count: int, *, low: int, high: int) -> float:
    """
    Piecewise scale:
      - 0 -> 0
      - low -> 5
      - high -> 10
    """
    if count <= 0:
        return 0.0
    if low <= 0 or high <= low:
        return float(min(10.0, round((count / max(1, high)) * 10.0, 1)))

    if count < low:
        return float(round((count / low) * 5.0, 1))
    if count < high:
        return float(round(5.0 + ((count - low) / (high - low)) * 5.0, 1))
    return 10.0


# -----------------------------------------------------------------------------
# Single-language deep scan (debug tool)
# -----------------------------------------------------------------------------
def scan_lexicon_health(lang_code: str, lex_root: Path) -> Dict[str, float]:
    """
    Deep scan of Zone B lexicon health for one language.

    Returns (0..10) scores plus diagnostics:
      - SEED, CONC, WIDE, SEM
      - COUNT_* diagnostics and ratios

    NOTE: Zone C is NOT computed here anymore (moved to app_scanner per upgrade plan).
    """
    stats: Dict[str, float] = {
        "SEED": 0.0,
        "CONC": 0.0,
        "WIDE": 0.0,
        "SEM": 0.0,
        # diagnostics
        "COUNT_CORE": 0.0,
        "COUNT_PEOPLE": 0.0,
        "COUNT_EXTRA": 0.0,
        "COUNT_TOTAL": 0.0,
        "COUNT_QID": 0.0,
        "COUNT_FORMS": 0.0,
        "QID_RATIO": 0.0,
        "FORMS_RATIO": 0.0,
        "WIDE_PRESENT": 0.0,   # 1 if any wide artifact exists
        "WIDE_BYTES": 0.0,
    }

    if not isinstance(lex_root, Path):
        return stats
    lex_root = lex_root.resolve()
    if not lex_root.is_dir():
        return stats

    repo = _project_root_from_lex_root(lex_root)
    iso_to_wiki = _load_iso_to_wiki(str(repo))
    wiki_to_iso2 = _build_wiki_to_iso2(iso_to_wiki)

    # Normalize request to iso2 if possible
    iso2_req = _norm_to_iso2(lang_code, wiki_to_iso2=wiki_to_iso2)
    if not iso2_req:
        return stats

    # Find a matching folder:
    # - prefer exact iso2 folder if present
    # - otherwise, scan for any folder that normalizes to iso2_req
    lang_path: Optional[Path] = None
    exact = lex_root / iso2_req
    if exact.is_dir():
        lang_path = exact
    else:
        for p in sorted(lex_root.iterdir(), key=lambda x: x.name.casefold()):
            if not p.is_dir():
                continue
            iso2 = _norm_to_iso2(p.name, wiki_to_iso2=wiki_to_iso2)
            if iso2 == iso2_req:
                lang_path = p
                break

    if not lang_path:
        return stats

    # 1) core.json => SEED
    core_file = lang_path / "core.json"
    core_payload = _safe_load_json(core_file)
    core_sections, _ = _extract_section_maps(core_payload)
    core_count = _count_sections(core_sections)
    stats["COUNT_CORE"] = float(core_count)
    stats["SEED"] = _score_count(core_count, low=TARGETS["core_low"], high=TARGETS["core_high"])

    # 2) domain shards => CONC + SEM inputs
    domain_files: Dict[str, Path] = {}

    for name in PRIMARY_DOMAIN_SHARDS:
        p = lang_path / name
        if p.is_file():
            domain_files[name] = p

    for p in lang_path.glob("*.json"):
        if p.name in NON_DOMAIN_FILES:
            continue
        if p.name not in domain_files:
            domain_files[p.name] = p

    people_count = 0
    extra_count = 0
    total_entries = 0
    qid_entries = 0
    forms_entries = 0

    # include core entries in SEM totals too
    total_entries += core_count
    for e in _iter_entry_dicts(core_sections):
        if _entry_has_qid(e):
            qid_entries += 1
        if _entry_has_forms(e):
            forms_entries += 1

    for fname, p in sorted(domain_files.items(), key=lambda kv: kv[0]):
        payload = _safe_load_json(p)
        sections, _ = _extract_section_maps(payload)
        n = _count_sections(sections)

        total_entries += n
        for e in _iter_entry_dicts(sections):
            if _entry_has_qid(e):
                qid_entries += 1
            if _entry_has_forms(e):
                forms_entries += 1

        if fname == "people.json":
            people_count += n
        else:
            extra_count += n

    stats["COUNT_PEOPLE"] = float(people_count)
    stats["COUNT_EXTRA"] = float(extra_count)

    domain_total = people_count + extra_count
    stats["CONC"] = _score_count(domain_total, low=TARGETS["conc_low"], high=TARGETS["conc_high"])

    # 3) WIDE: wide.json OR legacy data/imports/<folder>_wide.csv
    wide_json = lang_path / "wide.json"
    wide_present = False

    if wide_json.is_file():
        wide_present = True
        try:
            stats["WIDE_BYTES"] = float(wide_json.stat().st_size)
        except OSError:
            pass

    imports_dir = repo / "data" / "imports"
    if imports_dir.is_dir():
        candidates = {
            f"{lang_path.name.strip().lower()}_wide.csv",
            f"{iso2_req}_wide.csv",
        }
        for name in candidates:
            if (imports_dir / name).is_file():
                wide_present = True
                break

    if wide_present:
        stats["WIDE_PRESENT"] = 1.0
        stats["WIDE"] = 10.0

    # Optional: include wide.json in SEM counts if not huge
    if wide_json.is_file():
        try:
            if wide_json.stat().st_size <= MAX_WIDE_BYTES_TO_LOAD:
                payload = _safe_load_json(wide_json)
                sections, _ = _extract_section_maps(payload)
                wide_entries = _count_sections(sections)

                total_entries += wide_entries
                for e in _iter_entry_dicts(sections):
                    if _entry_has_qid(e):
                        qid_entries += 1
                    if _entry_has_forms(e):
                        forms_entries += 1
        except OSError:
            pass

    # 4) SEM: QID + small forms lift
    stats["COUNT_TOTAL"] = float(total_entries)
    stats["COUNT_QID"] = float(qid_entries)
    stats["COUNT_FORMS"] = float(forms_entries)

    if total_entries > 0:
        q_ratio = qid_entries / total_entries
        f_ratio = forms_entries / total_entries
        stats["QID_RATIO"] = float(round(q_ratio, 4))
        stats["FORMS_RATIO"] = float(round(f_ratio, 4))

        sem = (0.85 * q_ratio + 0.15 * f_ratio) * 10.0
        sem = float(round(min(10.0, sem), 1))

        # If wide import is present, keep SEM from being pinned at 0 due to large wide.json
        if wide_present:
            sem = max(sem, 5.0)

        stats["SEM"] = sem

    return stats


# -----------------------------------------------------------------------------
# Orchestrator contract: scan all lexicons once
# -----------------------------------------------------------------------------
def scan_all_lexicons(lex_root: Path) -> Dict[str, Dict[str, float]]:
    """
    Contract for build_index.py (one-shot scan):
      returns {iso2: {"SEED":..,"CONC":..,"WIDE":..,"SEM":..}}

    Determinism:
      - If both "en/" and "eng/" exist and map to the same iso2, we prefer the
        2-letter folder ("en") over longer aliases.
    """
    if not isinstance(lex_root, Path):
        return {}
    lex_root = lex_root.resolve()
    if not lex_root.is_dir():
        logger.warning(f"Lexicon root not found: {lex_root}")
        return {}

    logger.info(f"Scanning lexicon root: {lex_root}")

    repo = _project_root_from_lex_root(lex_root)
    iso_to_wiki = _load_iso_to_wiki(str(repo))
    wiki_to_iso2 = _build_wiki_to_iso2(iso_to_wiki)

    out: Dict[str, Dict[str, float]] = {}
    winner_len: Dict[str, int] = {}
    
    # Clear warnings before new scan
    _SCAN_WARNINGS.clear()

    scan_start = time.time()
    folders = sorted(lex_root.iterdir(), key=lambda x: x.name.casefold())
    
    for p in folders:
        if not p.is_dir():
            continue

        iso2 = _norm_to_iso2(p.name, wiki_to_iso2=wiki_to_iso2)
        if not iso2:
            continue

        stats = scan_lexicon_health(iso2, lex_root)
        zone_b = {
            "SEED": float(stats.get("SEED", 0.0) or 0.0),
            "CONC": float(stats.get("CONC", 0.0) or 0.0),
            "WIDE": float(stats.get("WIDE", 0.0) or 0.0),
            "SEM": float(stats.get("SEM", 0.0) or 0.0),
        }

        # Prefer shortest folder name for same iso2 (typically the iso2 folder).
        cur_len = len(p.name.strip())
        prev_len = winner_len.get(iso2, 10**9)
        if iso2 not in out or cur_len < prev_len:
            out[iso2] = zone_b
            winner_len[iso2] = cur_len
    
    duration = time.time() - scan_start
    logger.info(f"Scanned {len(out)} languages in {duration:.2f}s")
    
    return out


# -----------------------------------------------------------------------------
# Debug CLI
# -----------------------------------------------------------------------------
def _main() -> None:
    # 1. Setup Logging (Stdout)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True
    )
    
    start_time = time.time()
    
    ap = argparse.ArgumentParser(description="Lexicon scanner (Zone B). Debug tool.")
    ap.add_argument(
        "--lex-root",
        type=str,
        default="data/lexicon",
        help="Path to lexicon root (default: data/lexicon)",
    )
    ap.add_argument(
        "--lang",
        type=str,
        default="",
        help="If set, scan only this language code (iso2/iso3/wiki alias).",
    )
    args = ap.parse_args()

    # 2. Header
    print(f"=== LEXICON SCANNER ({LEXICON_SCANNER_VERSION}) ===")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Lex Root:  {args.lex_root}")
    print("-" * 40)

    lex_root = Path(args.lex_root)

    # 3. Single Language Mode
    if args.lang.strip():
        print(f"Scanning single language: {args.lang}")
        stats = scan_lexicon_health(args.lang.strip(), lex_root)
        
        # Diagnostics Output
        print("\n--- Diagnostics ---")
        for k, v in stats.items():
            print(f"{k:<15}: {v}")
            
        print("\n--- JSON Output ---")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    # 4. Batch Mode
    all_stats = scan_all_lexicons(lex_root)

    # 5. Calculate Meta Stats
    total_lemmas = 0 # This is approximate since scan_all_lexicons returns scores, not raw counts
                     # For exact counts we'd need to expose the inner loop, but this is a debug CLI.
                     # We will report number of languages instead.
                     
    # Generate Sample (Top 3 / Bottom 3 by SEED score)
    sorted_langs = sorted(all_stats.items(), key=lambda x: x[1].get("SEED", 0.0), reverse=True)
    sample_size = 3
    sample = {}
    
    if sorted_langs:
        for iso, data in sorted_langs[:sample_size]:
            sample[f"TOP_{iso}"] = data
        for iso, data in sorted_langs[-sample_size:]:
            sample[f"BOT_{iso}"] = data

    # 6. Structured Output
    output = {
        "meta": {
            "scanner": LEXICON_SCANNER_VERSION,
            "lexicon_root": str(lex_root),
            "language_count": len(all_stats),
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "key_mode": "iso2",
            "schema_version": "v2"
        },
        "warnings": _SCAN_WARNINGS[:20], # Limit warnings to prevent flooding
        "sample": sample,
        "languages": all_stats
    }
    
    # 7. Final Summary
    print("\n--- Summary ---")
    print(f"Languages Scanned: {len(all_stats)}")
    print(f"Duration:          {output['meta']['duration_ms']}ms")
    print(f"Warnings:          {len(_SCAN_WARNINGS)} (showing max 20 in JSON)")
    
    if _SCAN_WARNINGS:
        print("\n[Latest Warnings]")
        for w in _SCAN_WARNINGS[:5]:
            print(f" - {w}")
    
    # 8. Print Full JSON
    print("\n--- JSON Result ---")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()