# utils/refresh_lexicon_index.py
"""
utils/refresh_lexicon_index.py
------------------------------

Rebuild and validate normalized lookup indexes for lexicon JSON files
under `data/lexicon/`.

What this script does
=====================

For each `*.json` lexicon file:

  1. Load the JSON.
  2. Extract lemma keys from `"lemmas"`.
  3. Build a normalized index:
          normalized_key -> [original_lemma_key, ...]
      using `app.adapters.persistence.lexicon.normalization.normalize_for_lookup`.
  4. Detect collisions:
          two different lemma keys that normalize to the same canonical key.
  5. Print a structured report per file and an overall summary.

Notes
=====

- This script does *not* persist indices as separate files.
- It is intended as a sanity-check / maintenance tool to ensure lexicon files
  are compatible with the runtime normalization strategy.
- Output is written to stdout via ToolLogger (GUI-friendly).

Usage
=====

From project root:

    python utils/refresh_lexicon_index.py

Options:

    python utils/refresh_lexicon_index.py --data-dir data/lexicon
    python utils/refresh_lexicon_index.py --strict

Exit codes:

    0  → all lexicon files validated (no collisions), OR strict mode is off
    1  → collisions/errors found AND strict mode is on
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Project root on sys.path (so "app." and "utils." imports work when run as CLI)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from utils.tool_logger import ToolLogger

log = ToolLogger("refresh_lexicon_index")

# ---------------------------------------------------------------------------
# Imports (runtime normalization)
# ---------------------------------------------------------------------------

try:
    from app.adapters.persistence.lexicon.normalization import normalize_for_lookup
except Exception as exc:
    # Must be stdout + fatal for GUI visibility
    log.error(
        "CRITICAL: Could not import 'normalize_for_lookup' from "
        "app.adapters.persistence.lexicon.normalization. "
        "Check that app/adapters/persistence/lexicon/normalization.py exists "
        "and that PROJECT_ROOT is correct.\n"
        f"Details: {exc}",
        fatal=True,
    )
    raise  # unreachable, but helps type-checkers


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileReport:
    path: Path
    language: str
    total_lemmas: int
    collisions: List[Tuple[str, List[str]]]  # (normalized_key, [raw_keys])
    errors: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_probably_language_code(s: str) -> bool:
    # Keep permissive: "en", "fr", "pt", "pt-br", "sr-latn", etc.
    s = (s or "").strip().lower()
    if not s:
        return False
    if len(s) in (2, 3) and s.isalpha():
        return True
    if "-" in s:
        head = s.split("-", 1)[0]
        return len(head) in (2, 3) and head.isalpha()
    return False


def infer_language(path: Path, data_dir: Path) -> str:
    """
    Infer language from:
      - directory layout: data/lexicon/<lang>/.../*.json
      - filename prefix:  <lang>_something.json
    """
    try:
        rel = path.resolve().relative_to(data_dir.resolve())
        if len(rel.parts) >= 2 and _is_probably_language_code(rel.parts[0]):
            return rel.parts[0]
    except Exception:
        pass

    stem = path.stem
    if "_" in stem:
        cand = stem.split("_", 1)[0]
        if _is_probably_language_code(cand):
            return cand

    return ""


def find_lexicon_files(data_dir: Path) -> List[Path]:
    """
    Recursively find *.json under data_dir, skipping obvious junk folders.
    """
    if not data_dir.exists() or not data_dir.is_dir():
        return []

    skip_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules"}
    out: List[Path] = []

    for p in data_dir.rglob("*.json"):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        out.append(p)

    return sorted(out)


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def validate_lexicon_file(path: Path, data_dir: Path) -> FileReport:
    language = infer_language(path, data_dir)

    collisions: List[Tuple[str, List[str]]] = []
    errors: List[str] = []

    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        errors.append(f"Failed to read JSON: {exc}")
        return FileReport(
            path=path,
            language=language,
            total_lemmas=0,
            collisions=collisions,
            errors=errors,
        )

    if not isinstance(data, dict):
        errors.append("Top-level JSON is not an object.")
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

    normalized_to_raw: Dict[str, List[str]] = {}
    for raw_key in lemma_keys:
        try:
            norm = normalize_for_lookup(raw_key)
        except Exception as exc:
            errors.append(f"Normalization failed for lemma '{raw_key}': {exc}")
            continue

        if not norm:
            errors.append(f"Empty normalized key for lemma '{raw_key}'")
            continue

        normalized_to_raw.setdefault(norm, []).append(raw_key)

    for norm_key, raw_keys in normalized_to_raw.items():
        if len(raw_keys) > 1:
            collisions.append((norm_key, sorted(raw_keys)))

    return FileReport(
        path=path,
        language=language,
        total_lemmas=total_lemmas,
        collisions=collisions,
        errors=errors,
    )


def emit_report(reports: List[FileReport], *, data_dir: Path) -> bool:
    """
    Log a readable summary to stdout via ToolLogger.
    Returns True if no collisions/errors; False otherwise.
    """
    ok = True

    total_files = len(reports)
    total_lemmas = sum(r.total_lemmas for r in reports)
    total_collisions = sum(len(r.collisions) for r in reports)
    total_errors = sum(len(r.errors) for r in reports)

    log.info("")
    log.info("=== LEXICON INDEX REFRESH REPORT ===")
    log.info("")

    for r in reports:
        rel_path = str(r.path.resolve().relative_to(PROJECT_ROOT))
        lang_label = f" [{r.language}]" if r.language else ""
        log.info(f"- {rel_path}{lang_label}:")
        log.info(f"    lemmas:     {r.total_lemmas}")
        log.info(f"    collisions: {len(r.collisions)}")
        log.info(f"    errors:     {len(r.errors)}")

        if r.errors:
            ok = False
            for err in r.errors:
                log.error(f"Error: {err}")  # keep "Error:" prefix stable

        if r.collisions:
            ok = False
            for norm_key, raw_keys in r.collisions:
                joined = ", ".join(raw_keys)
                log.warning(f"Warning: COLLISION '{norm_key}' <- {joined}")  # keep "Warning:" prefix stable

        log.info("")

    log.info("Global summary:")
    log.info(f"  data_dir:   {data_dir}")
    log.info(f"  files:      {total_files}")
    log.info(f"  lemmas:     {total_lemmas}")
    log.info(f"  collisions: {total_collisions}")
    log.info(f"  errors:     {total_errors}")
    log.info("")

    if ok:
        log.info("✅ All lexicon files validated without collisions.")
    else:
        log.warning("Warning: Problems detected. See details above.")

    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild and validate normalized lemma indices for lexicon JSON "
            "files under data/lexicon/."
        )
    )
    parser.add_argument(
        "--data-dir",
        "-d",
        default=str(PROJECT_ROOT / "data" / "lexicon"),
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


def main(argv: List[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)

    data_dir = Path(args.data_dir).expanduser().resolve()

    log.header({"Data Dir": str(data_dir), "Strict Mode": bool(args.strict)})

    if not data_dir.exists() or not data_dir.is_dir():
        log.error(f"Lexicon directory not found: {data_dir}", fatal=True)

    log.stage("Scan", f"Searching for lexicon JSON files under {data_dir} ...")
    files = find_lexicon_files(data_dir)
    if not files:
        log.error(f"No lexicon JSON files found in: {data_dir}", fatal=True)

    log.stage("Validate", f"Validating normalized keys across {len(files)} files ...")
    reports: List[FileReport] = [validate_lexicon_file(p, data_dir) for p in files]

    ok = emit_report(reports, data_dir=data_dir)

    log.summary(
        {
            "Files Scanned": len(files),
            "Total Lemmas": sum(r.total_lemmas for r in reports),
            "Files With Collisions": sum(1 for r in reports if r.collisions),
            "Files With Errors": sum(1 for r in reports if r.errors),
            "Validation Passed": ok,
        },
        success=ok,
    )

    if not ok and args.strict:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()