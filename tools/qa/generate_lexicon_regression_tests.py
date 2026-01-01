# tools/qa/generate_lexicon_regression_tests.py
"""
tools/qa/generate_lexicon_regression_tests.py
--------------------------------------------

Generate a pytest module that performs *regression tests* on the lexicon
files under `data/lexicon/`.

What it does
============

- Recursively scans `data/lexicon/` for `*.json` lexicon shards.
- For each shard:
    - Loads the JSON.
    - Extracts lemma/entry keys from supported sections (currently: "entries", "lemmas").
    - Sorts keys and records the snapshot.
- Writes `tests/test_lexicon_regression.py` containing:
    - SNAPSHOTS = { "en/core.json": [...], "fr/science.json": [...], ... }
    - A parametrized test that recomputes keys and asserts exact match.

Usage
=====

From project root:

    python tools/qa/generate_lexicon_regression_tests.py

Or with overrides:

    python tools/qa/generate_lexicon_regression_tests.py --lexicon-dir data/lexicon --out tests/test_lexicon_regression.py

Then:

    pytest

Notes
=====

- This guards against unintended changes to lemma inventories (add/remove/rename/move).
- It does not validate lemma payload contents; use lexicon smoke/schema tests for that.
- Ignores hidden/special files and directories (names starting with "." or "_") and common schema/index files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

# ---------------------------------------------------------------------------
# Project root discovery (robust across working directories)
# ---------------------------------------------------------------------------


def _find_project_root(start: Path) -> Path:
    """
    Walk upward from `start` to find a directory that looks like the repo root.
    Heuristic: contains manage.py and data/.
    """
    start = start.resolve()
    for p in [start, *start.parents]:
        if (p / "manage.py").is_file() and (p / "data").is_dir():
            return p
    # Fallback: assume this file is at <root>/tools/qa/...
    # (parent = qa, parent = tools, parent = root)
    try:
        return start.parents[2]
    except Exception as e:
        raise RuntimeError(f"Unable to locate project root from: {start}") from e


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _find_project_root(SCRIPT_DIR)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logging_setup import get_logger, init_logging  # type: ignore  # noqa: E402

# Defaults
DEFAULT_LEXICON_DIR = PROJECT_ROOT / "data" / "lexicon"
DEFAULT_OUT = PROJECT_ROOT / "tests" / "test_lexicon_regression.py"

# Files to ignore anywhere in the lexicon tree
IGNORED_FILENAMES = {
    "lexicon_schema.json",
    "lexicon_index.json",
    "index.json",
}


# ---------------------------------------------------------------------------
# Lexicon snapshot logic
# ---------------------------------------------------------------------------


def _is_ignored_path(p: Path) -> bool:
    """
    Ignore:
      - any file/dir part starting with '.' or '_'
      - common schema/index files
      - non-json
    """
    if p.suffix.lower() != ".json":
        return True
    if p.name in IGNORED_FILENAMES:
        return True
    for part in p.parts:
        if part.startswith(".") or part.startswith("_"):
            return True
    return False


def _list_lexicon_files(lexicon_dir: Path) -> List[Path]:
    """
    Recursively list lexicon JSON files under lexicon_dir (absolute Paths),
    excluding schema / special files and hidden folders.
    """
    files: List[Path] = []
    for p in lexicon_dir.rglob("*.json"):
        if not p.is_file():
            continue
        if _is_ignored_path(p):
            continue
        files.append(p)
    files.sort(key=lambda x: x.as_posix())
    return files


def _extract_inventory_keys(data: Any) -> List[str]:
    """
    Extract a deterministic, sorted lemma inventory from a lexicon shard.

    Supported sections:
      - "entries" (current shard schema)
      - "lemmas"  (legacy/compat)

    If neither exists or isn't a dict, inventory is empty.
    """
    if not isinstance(data, dict):
        return []

    keys: Set[str] = set()

    entries = data.get("entries")
    if isinstance(entries, dict):
        keys.update(entries.keys())

    lemmas = data.get("lemmas")
    if isinstance(lemmas, dict):
        keys.update(lemmas.keys())

    return sorted(keys)


def _collect_snapshots(files: List[Path], lexicon_dir: Path) -> Dict[str, List[str]]:
    """
    Build mapping from lexicon-relative POSIX path (e.g. 'en/core.json')
    to a sorted list of lemma keys for that shard.
    """
    log = get_logger(__name__)
    snapshots: Dict[str, List[str]] = {}

    for path in files:
        rel = path.relative_to(lexicon_dir).as_posix()
        log.info("Collecting inventory from %s", rel)

        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON: {rel} ({path})") from e

        snapshots[rel] = _extract_inventory_keys(data)

    return snapshots


def _render_python_literal(obj: object, indent: int = 4) -> str:
    """
    Deterministic Python-literal rendering for dict/list/str.
    JSON is a safe subset for these types (no null/true/false expected here).
    """
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def _write_test_module(
    snapshots: Dict[str, List[str]],
    out_path: Path,
    lexicon_dir: Path,
    generator_relpath: str = "tools/qa/generate_lexicon_regression_tests.py",
) -> None:
    rel_lexicon_dir = lexicon_dir.relative_to(PROJECT_ROOT).as_posix()
    rel_out = out_path.relative_to(PROJECT_ROOT).as_posix()

    header = f'''"""Auto-generated lexicon regression tests.

DO NOT EDIT BY HAND.

Generated by:
    {generator_relpath}

This file snapshots lemma/entry inventories for each lexicon shard under:
    {rel_lexicon_dir}

If you intentionally modify the lexicon inventory (add/remove/rename/move keys),
regenerate this file:

    python {generator_relpath}
"""

from __future__ import annotations

import json
import os

import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEXICON_DIR = os.path.join(PROJECT_ROOT, "{rel_lexicon_dir.replace('"', '\\"')}")

# Snapshot of lemma keys per lexicon shard (lexicon-relative path -> sorted key list)
SNAPSHOTS = \\
'''

    # Ensure body starts cleanly; remove trailing backslash from header if present to avoid syntax errors
    # (Modified here to be safer: "SNAPSHOTS =" with no backslash, relying on Python's auto-concatenation or new lines)
    header = header.replace("SNAPSHOTS = \\", "SNAPSHOTS = ")

    body = _render_python_literal(snapshots, indent=4)

    tests = r'''

def _extract_inventory_keys(data):
    if not isinstance(data, dict):
        return []
    keys = set()

    entries = data.get("entries")
    if isinstance(entries, dict):
        keys.update(entries.keys())

    lemmas = data.get("lemmas")
    if isinstance(lemmas, dict):
        keys.update(lemmas.keys())

    return sorted(keys)


@pytest.mark.parametrize("relpath", sorted(SNAPSHOTS.keys()))
def test_lexicon_inventory_is_stable(relpath: str) -> None:
    """Ensure shard key inventories match the recorded snapshot."""  # noqa: D401
    path = os.path.normpath(os.path.join(LEXICON_DIR, relpath))
    assert os.path.isfile(path), f"Lexicon file not found: {path}"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    current = _extract_inventory_keys(data)
    expected = SNAPSHOTS[relpath]

    if current != expected:
        cur_set = set(current)
        exp_set = set(expected)

        added = sorted(cur_set - exp_set)
        removed = sorted(exp_set - cur_set)

        msg = (
            f"Lexicon inventory changed for {relpath}.\n"
            f"  Expected: {len(expected)} keys\n"
            f"  Current:  {len(current)} keys\n"
        )
        if added:
            msg += "  Added (first 50): " + ", ".join(added[:50]) + ("\n" if len(added) > 50 else "\n")
        if removed:
            msg += "  Removed (first 50): " + ", ".join(removed[:50]) + ("\n" if len(removed) > 50 else "\n")
        msg += "If this change was intentional, regenerate the regression tests."
        raise AssertionError(msg)
'''

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + body + tests, encoding="utf-8")

    log = get_logger(__name__)
    log.info("Wrote regression tests to %s", rel_out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: List[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate pytest regression tests for lexicon shard inventories.",
    )
    parser.add_argument(
        "--lexicon-dir",
        type=str,
        default=str(DEFAULT_LEXICON_DIR),
        help="Path to lexicon directory (default: data/lexicon).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DEFAULT_OUT),
        help="Output pytest module path (default: tests/test_lexicon_regression.py).",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    init_logging()
    log = get_logger(__name__)
    args = _parse_args(argv)

    lexicon_dir = Path(args.lexicon_dir).resolve()
    out_path = Path(args.out).resolve()

    if not lexicon_dir.is_dir():
        log.error("Lexicon directory not found: %s", lexicon_dir)
        print(f"ERROR: Lexicon directory not found: {lexicon_dir}", file=sys.stderr)
        raise SystemExit(1)

    files = _list_lexicon_files(lexicon_dir)
    if not files:
        log.error("No lexicon JSON files found in %s", lexicon_dir)
        print(f"ERROR: No lexicon JSON files found in: {lexicon_dir}", file=sys.stderr)
        raise SystemExit(1)

    snapshots = _collect_snapshots(files, lexicon_dir)
    _write_test_module(snapshots, out_path, lexicon_dir)

    rel_out = out_path.relative_to(PROJECT_ROOT).as_posix() if PROJECT_ROOT in out_path.parents else str(out_path)
    print(f"OK: Generated regression tests at {rel_out}")


if __name__ == "__main__":
    main()