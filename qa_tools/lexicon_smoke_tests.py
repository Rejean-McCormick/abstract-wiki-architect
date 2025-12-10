"""
qa_tools/lexicon_smoke_tests.py
===============================

Lightweight structural checks for all lexicon data.

This module is designed to work both:

- As a pytest test file (functions named `test_*`), and
- As a standalone script:

      python qa_tools/lexicon_smoke_tests.py

It validates:

1. That the data/lexicon directory exists.
2. That at least one language is detected.
3. That each language has a valid directory structure.
4. That the merged lexicon data (core + people + etc.) passes
   `lexicon.schema.validate_lexicon_structure`.
"""

from __future__ import annotations

import os
from typing import List, Tuple

from lexicon.loader import available_languages, load_lexicon
from lexicon.schema import SchemaIssue, validate_lexicon_structure

from utils.logging_setup import get_logger

log = get_logger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEXICON_DIR = os.path.join(PROJECT_ROOT, "data", "lexicon")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_schema_issues() -> List[Tuple[str, List[SchemaIssue]]]:
    """
    For all available languages, load the full merged lexicon and run schema 
    validation. Returns a list of (lang_code, issues) pairs.
    """
    results: List[Tuple[str, List[SchemaIssue]]] = []

    langs = available_languages()
    for lang in langs:
        try:
            # We use the official loader to get the final merged structure
            # exactly as the engine sees it.
            data = load_lexicon(lang)
        except Exception as e:
            # Treat a load failure as a single fatal error issue
            issue = SchemaIssue(
                path="loader",
                message=f"Failed to load/merge lexicon files for '{lang}': {e}",
                level="error",
            )
            results.append((lang, [issue]))
            continue

        # Validate the merged data structure
        issues = validate_lexicon_structure(lang, data)
        results.append((lang, issues))

    return results


# ---------------------------------------------------------------------------
# Pytest tests
# ---------------------------------------------------------------------------


def test_lexicon_directory_exists() -> None:
    """
    Ensure the data/lexicon directory exists.
    """
    assert os.path.isdir(LEXICON_DIR), f"Lexicon directory not found: {LEXICON_DIR}"


def test_at_least_one_language_detected() -> None:
    """
    Ensure the loader finds at least one language configuration.
    """
    langs = available_languages()
    assert (
        len(langs) > 0
    ), f"No language directories found in {LEXICON_DIR}. Expected at least one folder (e.g. 'en', 'fr')."


def test_language_directories_integrity() -> None:
    """
    For every language discovered by available_languages(), ensure
    a corresponding directory or legacy file exists.
    """
    missing = []
    for lang in available_languages():
        # It must be either a directory (new standard) or a file (legacy fallback)
        dir_path = os.path.join(LEXICON_DIR, lang)
        file_path = os.path.join(LEXICON_DIR, f"{lang}_lexicon.json")
        
        if not os.path.isdir(dir_path) and not os.path.isfile(file_path):
            missing.append(lang)

    assert not missing, f"Missing lexicon source for languages: {missing}"


def test_lexicon_schema_has_no_errors() -> None:
    """
    Validate merged lexicon structure for each language and ensure there are
    no *error*-level issues. Warnings are allowed.
    """
    problems: List[str] = []

    for lang, issues in _collect_schema_issues():
        error_messages = [
            f"{lang}::{issue.path}: {issue.message}"
            for issue in issues
            if issue.level.lower() == "error"
        ]
        if error_messages:
            problems.extend(error_messages)

    assert not problems, "Lexicon schema validation failed:\n  - " + "\n  - ".join(
        problems
    )


# ---------------------------------------------------------------------------
# Standalone CLI runner
# ---------------------------------------------------------------------------


def _print_human_report() -> int:
    """
    Run schema checks and print a human-readable report.

    Returns:
        0 if all lexica pass without errors, 1 otherwise.
    """
    if not os.path.isdir(LEXICON_DIR):
        print(f"❌ Lexicon directory not found: {LEXICON_DIR}")
        return 1

    langs = available_languages()
    if not langs:
        print(f"❌ No language data found in {LEXICON_DIR}")
        return 1

    print(f"📚 Found {len(langs)} language(s): {', '.join(sorted(langs))}\n")

    all_ok = True
    for lang, issues in _collect_schema_issues():
        errors = [i for i in issues if i.level.lower() == "error"]
        warnings = [i for i in issues if i.level.lower() != "error"]

        if errors:
            all_ok = False
            print(f"❌ {lang}: {len(errors)} error(s), {len(warnings)} warning(s)")
            for issue in errors:
                print(f"    [ERROR] {issue.path}: {issue.message}")
            for issue in warnings:
                print(f"    [WARN ] {issue.path}: {issue.message}")
        else:
            if warnings:
                print(f"⚠️  {lang}: 0 errors, {len(warnings)} warning(s)")
                for issue in warnings:
                    print(f"    [WARN ] {issue.path}: {issue.message}")
            else:
                print(f"✅ {lang}: schema OK (no issues)")

        print("")

    if all_ok:
        print("✅ All lexica passed schema checks without errors.")
        return 0
    else:
        print("❌ Some lexica have schema errors. See report above.")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = _print_human_report()
    sys.exit(exit_code)