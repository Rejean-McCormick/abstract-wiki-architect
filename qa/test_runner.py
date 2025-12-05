"""
qa/test_runner.py

CSV-based integration test runner for Abstract Wiki Architect.

This script:

- Scans a directory for test-suite CSV files.
- For each row with an expected output, calls the main rendering entrypoint
  (via the router) to generate an actual output.
- Compares ACTUAL vs EXPECTED and prints per-language and global statistics.
- Prints a short mismatch report for debugging.

Default assumptions:

- Test CSVs live in:
    - qa_tools/generated_datasets/   (preferred), or
    - qa/generated_datasets/         (fallback)
- Filenames are of the form:
    - test_suite_it.csv
    - test_suite_tr.csv
    - etc.
- Each CSV has an EXPECTED_* column and enough information to build
  a bio-like sentence (name, gender, profession, nationality).
  Column names are probed in a tolerant way.

If your router / entry function uses a different signature or your CSV
schema is different, adjust `compute_output_from_row` accordingly.

Notes:

- This runner is intentionally simple and focused on one-sentence bios:
  it calls `router.render_bio(...)`, which in turn builds a semantic
  `BioFrame` internally and routes to the right family engine.
- For more complex, construction-level tests, use
  `qa_tools/universal_test_runner.py`.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from router import render_bio  # type: ignore[attr-defined]
except ImportError:
    render_bio = None  # will be guarded later


# ---------------------------------------------------------------------------
# Configuration / helpers
# ---------------------------------------------------------------------------

DEFAULT_DATASET_DIR_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "qa_tools", "generated_datasets"),
    os.path.join(PROJECT_ROOT, "qa", "generated_datasets"),
]


EXPECTED_COLUMN_CANDIDATES = [
    "EXPECTED_OUTPUT",
    "EXPECTED_FULL_SENTENCE",
    "expected_output",
    "expected_full_sentence",
    "EXPECTED",
    "expected",
    "gold",
    "GOLD",
]

LANG_COLUMN_CANDIDATES = [
    "LANG",
    "lang",
    "LANGUAGE",
    "language",
    "language_code",
]

# Input columns for a typical biographical sentence
NAME_COLUMN_CANDIDATES = ["NAME", "name", "Name"]
GENDER_COLUMN_CANDIDATES = ["GENDER", "gender", "Gender", "Gender (Male/Female)"]
PROF_COLUMN_CANDIDATES = [
    "PROFESSION_LEMMA",
    "profession_lemma",
    "PROFESSION",
    "profession",
]
NAT_COLUMN_CANDIDATES = [
    "NATIONALITY_LEMMA",
    "nationality_lemma",
    "NATIONALITY",
    "nationality",
]


@dataclass
class CaseResult:
    index: Any
    lang: str
    file: str
    expected: str
    actual: str
    passed: bool
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LanguageStats:
    lang: str
    total: int = 0
    passed: int = 0
    failed: int = 0


# ---------------------------------------------------------------------------
# Core mapping from CSV row → router call
# ---------------------------------------------------------------------------


def _first_present(row: pd.Series, candidates: List[str]) -> Optional[Any]:
    for key in candidates:
        if key in row and not pd.isna(row[key]) and str(row[key]).strip() != "":
            return row[key]
    return None


def _find_val_by_prefix(row: pd.Series, prefix: str) -> Optional[Any]:
    """Find value in first column starting with prefix."""
    for col in row.index:
        if str(col).startswith(prefix):
            val = row[col]
            if not pd.isna(val) and str(val).strip() != "":
                return val
    return None


def infer_lang_from_filename(filename: str) -> Optional[str]:
    """
    Try to infer a language code from the CSV filename.

    Expected patterns:
      - test_suite_it.csv  → "it"
      - test_suite_es.csv  → "es"
      - it.csv             → "it"
    """
    base = os.path.basename(filename)
    m = re.match(r"test_suite_([a-zA-Z0-9\-]+)\.csv$", base)
    if m:
        return m.group(1)
    # Fallback: strip extension and use the last segment
    stem, _ = os.path.splitext(base)
    if stem:
        return stem
    return None


def compute_output_from_row(row: pd.Series, lang_code: str) -> str:
    """
    Compute the model output for a single CSV row and language code.

    By default, this assumes the primary entrypoint is:

        router.render_bio(
            name=...,
            gender=...,
            profession_lemma=...,
            nationality_lemma=...,
            lang_code=...
        )

    If your router / engine uses a different function or signature,
    modify this function accordingly.
    """
    if render_bio is None:
        raise RuntimeError(
            "router.render_bio could not be imported. "
            "Ensure the router exposes a render_bio(...) function "
            "or adjust compute_output_from_row() to your API."
        )

    name = _first_present(row, NAME_COLUMN_CANDIDATES)
    gender = _first_present(row, GENDER_COLUMN_CANDIDATES)

    prof = _first_present(row, PROF_COLUMN_CANDIDATES)
    if prof is None:
        prof = _find_val_by_prefix(row, "Profession_Lemma")

    nat = _first_present(row, NAT_COLUMN_CANDIDATES)
    if nat is None:
        nat = _find_val_by_prefix(row, "Nationality_Lemma")

    if name is None or gender is None or prof is None or nat is None:
        raise ValueError(
            f"Missing required input fields for row {row.name} "
            f"(name={name}, gender={gender}, prof={prof}, nat={nat})"
        )

    # Convert to str to avoid pandas NA / float surprises
    name_str = str(name)
    gender_str = str(gender)

    # Clean placeholder brackets from generator if present (e.g. "[Actor]" -> "Actor")
    prof_str = str(prof).replace("[", "").replace("]", "")
    nat_str = str(nat).replace("[", "").replace("]", "")

    lang_str = str(lang_code)

    # Call the main entrypoint
    output = render_bio(
        name=name_str,
        gender=gender_str,
        profession_lemma=prof_str,
        nationality_lemma=nat_str,
        lang_code=lang_str,
    )
    # Ensure string
    return "" if output is None else str(output)


# ---------------------------------------------------------------------------
# Running over CSV files
# ---------------------------------------------------------------------------


def find_dataset_dir(explicit: Optional[str] = None) -> str:
    if explicit:
        abs_path = os.path.abspath(explicit)
        if not os.path.isdir(abs_path):
            raise FileNotFoundError(f"Dataset directory not found: {abs_path}")
        return abs_path

    for candidate in DEFAULT_DATASET_DIR_CANDIDATES:
        if os.path.isdir(candidate):
            return candidate

    raise FileNotFoundError(
        "No generated_datasets directory found.\n"
        "Tried:\n" + "\n".join(f"  - {p}" for p in DEFAULT_DATASET_DIR_CANDIDATES)
    )


def find_expected_column(df: pd.DataFrame) -> Optional[str]:
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in EXPECTED_COLUMN_CANDIDATES:
        lc = cand.lower()
        if lc in lower_cols:
            return lower_cols[lc]
    return None


def find_lang_column(df: pd.DataFrame) -> Optional[str]:
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in LANG_COLUMN_CANDIDATES:
        lc = cand.lower()
        if lc in lower_cols:
            return lower_cols[lc]
    return None


def run_tests_on_file(
    path: str,
    allowed_langs: Optional[Set[str]] = None,
) -> Tuple[List[CaseResult], List[str]]:
    """
    Run tests on a single CSV file.

    If `allowed_langs` is not None, rows whose language code (or filename-
    inferred language) is not in that set are skipped.
    """
    df = pd.read_csv(path, dtype=str).fillna("")

    expected_col = find_expected_column(df)
    if not expected_col:
        return [], [f"{path}: no EXPECTED_* column found, skipping."]

    lang_col = find_lang_column(df)
    file_lang = infer_lang_from_filename(path)

    results: List[CaseResult] = []
    warnings: List[str] = []

    for idx, row in df.iterrows():
        expected = row.get(expected_col, "").strip()
        if not expected:
            # No gold sentence provided → skip
            continue

        # Determine language code
        lang = ""
        if lang_col:
            lang = str(row.get(lang_col, "")).strip()
        if not lang and file_lang:
            lang = file_lang

        if not lang:
            warnings.append(
                f"{path} (row {idx}): no language code; could not infer from file or column."
            )
            continue

        if allowed_langs is not None and lang not in allowed_langs:
            # Explicitly filtered out
            continue

        try:
            actual = compute_output_from_row(row, lang)
        except Exception as e:
            warnings.append(
                f"{path} (row {idx}): ERROR during rendering for lang='{lang}': {e}"
            )
            actual = f"[ERROR: {e}]"

        passed = actual.strip() == expected.strip()

        results.append(
            CaseResult(
                index=idx,
                lang=lang,
                file=os.path.basename(path),
                expected=expected,
                actual=actual,
                passed=passed,
                meta={},
            )
        )

    return results, warnings


def aggregate_stats(results: List[CaseResult]) -> Dict[str, LanguageStats]:
    by_lang: Dict[str, LanguageStats] = {}
    for r in results:
        stats = by_lang.setdefault(r.lang, LanguageStats(lang=r.lang))
        stats.total += 1
        if r.passed:
            stats.passed += 1
        else:
            stats.failed += 1
    return by_lang


def print_report(results: List[CaseResult], warnings: List[str]) -> None:
    by_lang = aggregate_stats(results)

    total_cases = len(results)
    total_passed = sum(r.passed for r in results)
    total_failed = total_cases - total_passed

    print("\n=== QA TEST RUN SUMMARY ===\n")

    print("Per-language stats:")
    for lang, stats in sorted(by_lang.items(), key=lambda x: x[0]):
        pct = 0.0 if stats.total == 0 else (100.0 * stats.passed / stats.total)
        print(
            f"  {lang:<5}: {stats.passed:4d}/{stats.total:4d} passed "
            f"({pct:5.1f}%); failed={stats.failed}"
        )

    print("\nGlobal stats:")
    pct_global = 0.0 if total_cases == 0 else (100.0 * total_passed / total_cases)
    print(
        f"  TOTAL: {total_passed}/{total_cases} passed "
        f"({pct_global:5.1f}%); failed={total_failed}"
    )

    # Show a few mismatches for inspection
    failed_cases = [r for r in results if not r.passed]
    if failed_cases:
        print("\nSample mismatches:")
        for r in failed_cases[:20]:
            print(
                f"- {r.file} [row={r.index}, lang={r.lang}]\n"
                f"    EXPECTED: {r.expected}\n"
                f"    ACTUAL:   {r.actual}\n"
            )
    else:
        print("\nNo mismatches; all checked cases passed.")

    if warnings:
        print("\nWarnings / errors:")
        for w in warnings:
            print(f"  - {w}")

    print("")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run CSV-based integration tests for Abstract Wiki Architect."
    )
    parser.add_argument(
        "--data-dir",
        "-d",
        dest="data_dir",
        default=None,
        help=(
            "Directory containing test_suite_*.csv files. "
            "If omitted, tries qa_tools/generated_datasets/ and qa/generated_datasets/."
        ),
    )
    parser.add_argument(
        "--pattern",
        "-p",
        dest="pattern",
        default="test_suite_*.csv",
        help="Glob pattern for selecting CSV files (default: test_suite_*.csv).",
    )
    parser.add_argument(
        "--langs",
        "-l",
        nargs="*",
        dest="langs",
        help=(
            "Optional list of language codes to restrict evaluation to "
            "(e.g. it fr es). If omitted, all languages present in the "
            "CSV files are included."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        dataset_dir = find_dataset_dir(args.data_dir)
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

    print(f"Using dataset directory: {dataset_dir}")

    # Collect CSV files
    import glob

    pattern = os.path.join(dataset_dir, args.pattern)
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No CSV files found with pattern: {pattern}")
        sys.exit(1)

    allowed_langs: Optional[Set[str]] = None
    if args.langs:
        allowed_langs = {lang.strip() for lang in args.langs if lang.strip()}
        if not allowed_langs:
            allowed_langs = None

    all_results: List[CaseResult] = []
    all_warnings: List[str] = []

    for path in files:
        print(f"Processing: {os.path.basename(path)}")
        file_results, file_warnings = run_tests_on_file(
            path, allowed_langs=allowed_langs
        )
        all_results.extend(file_results)
        all_warnings.extend(file_warnings)

    print_report(all_results, all_warnings)


if __name__ == "__main__":
    main()
