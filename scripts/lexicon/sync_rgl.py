# scripts/lexicon/sync_rgl.py
# ============================================================================
# GF LEXICON SYNCHRONIZER (Filesystem Lexicon Edition)
#
# Purpose
# -------
# Perform a "Big Pull" from a compiled PGF (AbstractWiki.pgf / Wiki.pgf) into the
# on-disk lexicon shards under: data/lexicon/{iso_code}/{domain}.json
#
# What it does
# ------------
# 1) Loads the compiled PGF via `pgf.readPGF`.
# 2) Finds lexical abstract functions in the grammar (by suffix convention).
# 3) For each concrete language in the PGF:
#    - maps the GF concrete name (e.g., WikiEng) -> ISO code (e.g., en/eng)
#      using config/iso_to_wiki.json (same mapping used by GFGrammarEngine).
#    - linearizes each lexical function to a default surface form.
#    - upserts an entry keyed by the *GF function id* into {domain}.json:
#          entries[gf_fun] = { lemma, pos, gf_fun, source, forms, ... }
#
# Notes
# -----
# - This script does NOT require a database and does NOT use SQLAlchemy.
# - It intentionally only captures a default lemma (linearization). Full
#   morphology tables are not available unless your grammar/PGF exposes them
#   via dedicated helper code.
# - The output shard is designed to be safe to merge with your existing
#   domain-sharded lexicon setup (core/people/science/geography/wide).
#
# Usage
# -----
#   python scripts/lexicon/sync_rgl.py
#   python scripts/lexicon/sync_rgl.py --pgf gf/AbstractWiki.pgf --domain rgl_sync
#   python scripts/lexicon/sync_rgl.py --langs en,fr,de --max-funs 2000 --dry-run
# ============================================================================

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pgf  # type: ignore
except Exception as e:  # pragma: no cover
    pgf = None  # type: ignore
    _PGF_IMPORT_ERROR = e
else:
    _PGF_IMPORT_ERROR = None


# ----------------------------------------------------------------------------
# Path / project root helpers
# ----------------------------------------------------------------------------

def _find_project_root(start: Path) -> Path:
    anchors = {"manage.py", "pyproject.toml", "requirements.txt", "NoteBookIndex.json"}
    cur = start.resolve()
    for _ in range(8):
        if any((cur / a).exists() for a in anchors):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve().parents[2]


def _default_pgf_path(project_root: Path) -> Optional[Path]:
    candidates = [
        project_root / "gf" / "AbstractWiki.pgf",
        project_root / "gf" / "Wiki.pgf",
        project_root / "Wiki.pgf",
        project_root / "AbstractWiki.pgf",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ----------------------------------------------------------------------------
# Language mapping
# ----------------------------------------------------------------------------

def _load_iso_to_wiki(project_root: Path) -> Dict[str, Any]:
    # Fixed path: config is at root, not inside app/config
    path = project_root / "config" / "iso_to_wiki.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_suffix_to_iso2(iso_to_wiki: Dict[str, Any]) -> Dict[str, str]:
    """
    Builds a reverse map of GF Suffix -> ISO Code.
    Handles both legacy string values {"en": "Eng"} 
    and v2.0 object values {"en": {"wiki": "Eng", "name": "English"}}
    """
    out: Dict[str, str] = {}
    for iso, data in iso_to_wiki.items():
        suffix = None
        
        # 1. Handle legacy string format
        if isinstance(data, str):
            suffix = data
        # 2. Handle object format (v2.0)
        elif isinstance(data, dict):
            suffix = data.get("wiki")
            
        if suffix and isinstance(iso, str):
            # Allow 2-letter (ISO-1) or 3-letter (ISO-3) codes
            if 2 <= len(iso) <= 3:
                out[suffix] = iso
    return out


def _infer_iso2_from_concrete(concrete_name: str, suffix_to_iso2: Dict[str, str]) -> Optional[str]:
    name = concrete_name.strip()
    # Try suffix matching (e.g. WikiEng -> Eng)
    if name.startswith("Wiki") and len(name) > 4:
        suffix = name[4:]
        if suffix in suffix_to_iso2:
            return suffix_to_iso2[suffix]
            
    # Fallback to direct lookup if map has full names (rare)
    return suffix_to_iso2.get(name)


# ----------------------------------------------------------------------------
# Lexical function selection / category mapping
# ----------------------------------------------------------------------------

DEFAULT_SUFFIXES = ("_Entity", "_Property", "_VP", "_Mod")

def _pick_lexical_functions(fun_names: Iterable[str], suffixes: Sequence[str]) -> List[str]:
    suffixes_t = tuple(suffixes)
    return sorted([f for f in fun_names if f.endswith(suffixes_t)])


def _pos_from_fun_name(fun_name: str) -> str:
    if fun_name.endswith("_Entity"):
        return "NOUN"
    if fun_name.endswith("_Property"):
        return "ADJ"
    if fun_name.endswith("_VP"):
        return "VERB"
    if fun_name.endswith("_Mod"):
        return "ADV"
    return "X"


# ----------------------------------------------------------------------------
# JSON IO / validation helpers
# ----------------------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ensure_shard_template(lang: str, domain: str) -> Dict[str, Any]:
    now = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return {
        "_meta": {
            "language": lang,
            "domain": domain,
            "version": 1,
            "schema_version": 2,
            "generated_at": now,
            "source": "rgl_sync",
        },
        "entries": {},
        # Back-compat for legacy tools expecting "lemmas"
        "lemmas": {},
    }


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _validate_with_schema(lang: str, data: Dict[str, Any]) -> Tuple[int, int, List[str]]:
    project_root = _find_project_root(Path(__file__))
    persistence_dir = project_root / "app" / "adapters" / "persistence"
    if persistence_dir.exists() and str(persistence_dir) not in sys.path:
        sys.path.append(str(persistence_dir))

    try:
        from lexicon.schema import validate_lexicon_structure  # type: ignore
    except Exception:
        return (0, 0, ["(schema validation skipped: lexicon.schema not importable)"])

    try:
        issues = validate_lexicon_structure(lang, data)
    except Exception as e:
        return (1, 0, [f"schema validation crashed: {e!r}"])

    errors = [i for i in issues if getattr(i, "severity", "").upper() == "ERROR"]
    warns = [i for i in issues if getattr(i, "severity", "").upper() != "ERROR"]
    msgs: List[str] = []
    for i in errors[:25]:
        msgs.append(f"ERROR: {getattr(i, 'message', str(i))}")
    for i in warns[:25]:
        msgs.append(f"WARN: {getattr(i, 'message', str(i))}")
    if len(errors) > 25:
        msgs.append(f"... {len(errors) - 25} more errors")
    if len(warns) > 25:
        msgs.append(f"... {len(warns) - 25} more warnings")

    return (len(errors), len(warns), msgs)


# ----------------------------------------------------------------------------
# Main sync logic
# ----------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sync GF PGF lexical functions into data/lexicon shards.")
    p.add_argument("--pgf", dest="pgf_path", default=None, help="Path to compiled PGF (defaults to gf/AbstractWiki.pgf if present).")
    p.add_argument("--out-dir", dest="out_dir", default="data/lexicon", help="Output base dir (default: data/lexicon).")
    p.add_argument("--domain", default="rgl_sync", help="Domain shard filename (default: rgl_sync -> rgl_sync.json).")
    p.add_argument("--suffixes", default=",".join(DEFAULT_SUFFIXES), help="Comma-separated suffix filters for lexical functions.")
    p.add_argument("--langs", default=None, help="Comma-separated ISO-2/3 language allowlist (e.g., en,fr,de or eng,fra).")
    p.add_argument("--max-funs", type=int, default=None, help="Process at most N lexical functions (for quick runs).")
    p.add_argument("--dry-run", action="store_true", help="Do not write files; just report.")
    p.add_argument("--validate", action="store_true", help="Run lexicon schema validation on output objects.")
    return p


def sync_lexicon(argv: Optional[List[str]] = None) -> int:
    if pgf is None:
        print(f"ERROR: Could not import `pgf` ({_PGF_IMPORT_ERROR!r}). Install GF's python bindings and try again.")
        return 2

    args = build_arg_parser().parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    project_root = _find_project_root(script_dir)

    pgf_path = Path(args.pgf_path) if args.pgf_path else _default_pgf_path(project_root)
    if not pgf_path or not pgf_path.exists():
        print("ERROR: No PGF file found. Use --pgf <path> (expected gf/AbstractWiki.pgf or gf/Wiki.pgf).")
        return 2

    out_base = (project_root / args.out_dir).resolve()
    domain = args.domain.strip()
    shard_filename = f"{domain}.json"

    iso_to_wiki = _load_iso_to_wiki(project_root)
    suffix_to_iso2 = _build_suffix_to_iso2(iso_to_wiki)
    if not suffix_to_iso2:
        print("WARN: config/iso_to_wiki.json not found or empty; language mapping may be incomplete.")

    try:
        grammar = pgf.readPGF(str(pgf_path))
    except Exception as e:
        print(f"ERROR: Failed to read PGF at {pgf_path}: {e!r}")
        return 2

    concrete_names = sorted(grammar.languages.keys())
    print(f"Loaded PGF: {pgf_path}")
    print(f"Concrete languages in PGF: {len(concrete_names)}")

    allow_langs: Optional[set[str]] = None
    if args.langs:
        allow_langs = {x.strip() for x in args.langs.split(",") if x.strip()}

    suffixes = [s.strip() for s in args.suffixes.split(",") if s.strip()]
    lexical_funs = _pick_lexical_functions(grammar.functions.keys(), suffixes)
    if args.max_funs is not None:
        lexical_funs = lexical_funs[: max(0, args.max_funs)]
    print(f"Lexical functions selected: {len(lexical_funs)} (suffixes={suffixes})")

    expr_cache: Dict[str, Any] = {}
    for fun in lexical_funs:
        try:
            expr_cache[fun] = pgf.readExpr(fun)
        except Exception:
            continue

    overall_added = 0
    overall_updated = 0
    overall_skipped = 0
    per_lang_reports: List[Tuple[str, int, int, int]] = []

    for concrete_name in concrete_names:
        iso2 = _infer_iso2_from_concrete(concrete_name, suffix_to_iso2)
        if not iso2:
            overall_skipped += 1
            continue
        if allow_langs is not None and iso2 not in allow_langs:
            continue

        concrete = grammar.languages[concrete_name]
        shard_path = out_base / iso2 / shard_filename

        existing = _load_json(shard_path)
        if not existing:
            existing = _ensure_shard_template(iso2, domain)

        meta = existing.get("_meta") or {}
        if isinstance(meta, dict):
            meta.setdefault("language", iso2)
            meta.setdefault("domain", domain)
            meta.setdefault("version", 1)
            meta.setdefault("schema_version", 2)
            meta["generated_at"] = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            meta.setdefault("source", "rgl_sync")
        existing["_meta"] = meta

        entries = existing.get("entries")
        if not isinstance(entries, dict):
            entries = {}
        lemmas = existing.get("lemmas")
        if not isinstance(lemmas, dict):
            lemmas = {}

        added = 0
        updated = 0
        skipped = 0

        for fun in lexical_funs:
            expr = expr_cache.get(fun)
            if expr is None:
                skipped += 1
                continue
            try:
                lemma = concrete.linearize(expr)
            except Exception:
                skipped += 1
                continue

            lemma = (lemma or "").strip()
            if not lemma or lemma == "?" or lemma.startswith("*"):
                skipped += 1
                continue

            pos = _pos_from_fun_name(fun)
            new_entry: Dict[str, Any] = {
                "lemma": lemma,
                "pos": pos,
                "gf_fun": fun,
                "source": "RGL_SYNC",
                "forms": {"default": lemma},
                "meta": {"concrete": concrete_name, "pgf": str(pgf_path)},
            }

            old = entries.get(fun)
            if not isinstance(old, dict):
                entries[fun] = new_entry
                lemmas[fun] = new_entry
                added += 1
            else:
                if old.get("lemma") != lemma or old.get("pos") != pos:
                    entries[fun] = {**old, **new_entry}
                    lemmas[fun] = entries[fun]
                    updated += 1
                else:
                    skipped += 1

        existing["entries"] = entries
        existing["lemmas"] = lemmas

        if args.validate:
            err_n, warn_n, msgs = _validate_with_schema(iso2, existing)
            if err_n or warn_n:
                print(f"[{iso2}] schema issues: {err_n} errors, {warn_n} warnings")
                for m in msgs[:10]:
                    print(f"  {m}")

        if args.dry_run:
            print(f"[{iso2}] would write {shard_path} (added={added}, updated={updated}, skipped={skipped})")
        else:
            _write_json(shard_path, existing)
            print(f"[{iso2}] wrote {shard_path} (added={added}, updated={updated}, skipped={skipped})")

        overall_added += added
        overall_updated += updated
        overall_skipped += skipped
        per_lang_reports.append((iso2, added, updated, skipped))

    print("\nSummary")
    print("-------")
    print(f"Languages processed: {len(per_lang_reports)}")
    print(f"Total added:    {overall_added}")
    print(f"Total updated: {overall_updated}")
    print(f"Total skipped: {overall_skipped}")
    if allow_langs is not None:
        print(f"Language allowlist: {sorted(allow_langs)}")
    print(f"Output base dir: {out_base}")
    print(f"Shard: {shard_filename}")

    return 0


if __name__ == "__main__":
    raise SystemExit(sync_lexicon())