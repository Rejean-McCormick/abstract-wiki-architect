# utils/refresh_lexicon_index.py
"""
utils/refresh_lexicon_index.py
------------------------------

Rebuild and validate normalized lookup indexes for all lexicon JSON
files under `data/lexicon/`.

What this script does
=====================

For each `*.json` lexicon file:

  1. Load the JSON.
  2. Extract lemma keys from `"lemmas"`.
  3. Build a normalized index:
          normalized_key -> original_lemma_key
      using `lexicon.normalization.normalize_for_lookup`.
  4. Detect collisions:
          two different lemma keys that normalize to the same
          canonical key.
  5. Print a short report per file and an overall summary.

This script does *not* currently persist indices as separate files.
It is intended as a sanity-check / maintenance tool to ensure that
lexicon files are compatible with the normalization strategy used
by the runtime lexicon subsystem.

Usage
=====

From project root:

    python utils/refresh_lexicon_index.py

Options:

    python utils/refresh_lexicon_index.py --data-dir data/lexicon
    python utils/refresh_lexicon_index.py --strict

Exit codes:

    0  → all lexicon files validated (no collisions), OR strict mode is off
    1  → collisions found AND strict mode is on
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.tool_logger import ToolLogger

# Fix: Import from the actual location in app/adapters, not top-level 'lexicon'
try:
    from app.adapters.persistence.lexicon.normalization import normalize_for_lookup
except ImportError:
    # Fallback/Error message if the path is still unreachable
    print("CRITICAL: Could not import 'normalize_for_lookup'. Check app/adapters/persistence/lexicon/normalization.py.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

log = ToolLogger("refresh_index")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileReport:
    path: str
    language: str
    total_lemmas: int
    collisions: List[Tuple[str, List[str]]]  # (normalized_key, [raw_keys])
    errors: List[str]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def infer_language_from_filename(filename: str) -> str:
    """
    Attempt to infer language code from lexicon filename.

    Expected naming conventions:

        en_lexicon.json
        en_science.json
        fr_people.json
        ...

    The language code is taken as the leading segment before the first
    underscore. Fallback: empty string if we cannot infer it.
    """
    base = os.path.basename(filename)
    stem, _ = os.path.splitext(base)
    if "_" in stem:
        return stem.split("_", 1)[0]
    return ""


def validate_lexicon_file(path: str) -> FileReport:
    """
    Load a lexicon JSON file, build a normalized index, and detect collisions.

    Returns:
        FileReport with summary stats and collision info.
    """
    language = infer_language_from_filename(path)

    collisions: List[Tuple[str, List[str]]] = []
    errors: List[str] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # pragma: no cover - defensive
        errors.append(f"Failed to read JSON: {e}")
        return FileReport(
            path=path,
            language=language,
            total_lemmas=0,
            collisions=collisions,
            errors=errors,
        )

    lemmas_obj = data.get("lemmas")
    if not isinstance(lemmas_obj, dict):
        errors.append("Top-level 'lemmas' key missing or not an object.")
        return FileReport(
            path=path,
            language=language,
            total_lemmas=0,
            collisions=collisions,
            errors=errors,
        )

    lemma_keys = list(lemmas_obj.keys())
    total_lemmas = len(lemma_keys)

    # Build normalized index and track collisions manually to provide
    # detailed reports.
    normalized_to_raw: Dict[str, List[str]] = {}
    for raw_key in lemma_keys:
        norm = normalize_for_lookup(raw_key)
        if not norm:
            errors.append(f"Empty normalized key for lemma '{raw_key}'")
            continue
        normalized_to_raw.setdefault(norm, []).append(raw_key)

    for norm_key, raw_keys in normalized_to_raw.items():
        if len(raw_keys) > 1:
            # Collision: multiple different raw keys map to the same
            # normalized key.
            # Only report it once per file.
            collisions.append((norm_key, sorted(raw_keys)))

    return FileReport(
        path=path,
        language=language,
        total_lemmas=total_lemmas,
        collisions=collisions,
        errors=errors,
    )


def find_lexicon_files(data_dir: str) -> List[str]:
    """
    Return a sorted list of *.json files in `data_dir`.
    """
    files: List[str] = []
    if not os.path.exists(data_dir):
        return []
        
    for entry in os.listdir(data_dir):
        if not entry.lower().endswith(".json"):
            continue
        full_path = os.path.join(data_dir, entry)
        if os.path.isfile(full_path):
            files.append(full_path)
    files.sort()
    return files


def print_report(reports: List[FileReport]) -> bool:
    """
    Print a human-readable summary to stdout.

    Returns:
        True if all files validated without collisions or errors,
        False otherwise.
    """
    ok = True
    total_files = len(reports)
    total_lemmas = sum(r.total_lemmas for r in reports)
    total_collisions = sum(len(r.collisions) for r in reports)
    total_errors = sum(len(r.errors) for r in reports)

    print("\n=== LEXICON INDEX REFRESH REPORT ===\n")

    for r in reports:
        rel_path = os.path.relpath(r.path, PROJECT_ROOT)
        lang_label = f" [{r.language}]" if r.language else ""
        print(f"- {rel_path}{lang_label}:")
        print(f"    lemmas:     {r.total_lemmas}")
        print(f"    collisions: {len(r.collisions)}")
        print(f"    errors:     {len(r.errors)}")

        if r.errors:
            ok = False
            for err in r.errors:
                print(f"      ERROR: {err}")

        if r.collisions:
            ok = False
            for norm_key, raw_keys in r.collisions:
                joined = ", ".join(raw_keys)
                print(f"      COLLISION: '{norm_key}' <- {joined}")

        print("")

    print("Global summary:")
    print(f"  files:      {total_files}")
    print(f"  lemmas:     {total_lemmas}")
    print(f"  collisions: {total_collisions}")
    print(f"  errors:     {total_errors}")
    print("")

    if ok:
        print("✅ All lexicon files validated without collisions.")
    else:
        print("❌ Problems detected. See details above.")

    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild and validate normalized lemma indices for lexicon "
            "JSON files under data/lexicon/."
        )
    )
    parser.add_argument(
        "--data-dir",
        "-d",
        default=os.path.join(PROJECT_ROOT, "data", "lexicon"),
        help="Directory containing lexicon JSON files (default: data/lexicon).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit with non-zero status if *any* collision or error is found "
            "(default behavior is to report but exit 0)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)

    log.header({"Data Dir": args.data_dir, "Strict Mode": args.strict})

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        log.error(f"Lexicon directory not found: {data_dir}", fatal=True)

    files = find_lexicon_files(data_dir)
    if not files:
        log.error(f"No lexicon JSON files found in: {data_dir}", fatal=True)

    log.stage("Scan", f"Found {len(files)} lexicon files.")

    reports: List[FileReport] = []
    for path in files:
        reports.append(validate_lexicon_file(path))

    # Print detailed report to stdout
    ok = print_report(reports)
    
    log.summary({"Files Scanned": len(files), "Validation Passed": ok}, success=ok)
    
    if not ok and args.strict:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()