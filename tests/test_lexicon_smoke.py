# tests/test_lexicon_smoke.py
"""
tests/test_lexicon_smoke.py
===========================

Lightweight structural checks for all lexicon data.

This module is designed to work both:

- As a pytest test file (functions named `test_*`), and
- As a standalone script:

      python tests/test_lexicon_smoke.py

It validates:

1. That the data/lexicon directory exists.
2. That at least one language is detected.
3. That each language has a valid directory structure.
4. That the merged lexicon data (core + people + etc.) passes
   `lexicon.schema.validate_lexicon_structure`.
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple, Dict

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lexicon.loader import available_languages, load_lexicon
from lexicon.schema import SchemaIssue, validate_lexicon_structure
from utils.logging_setup import get_logger, init_logging

log = get_logger(__name__)

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
    assert os.path.isdir(LEXICON_DIR), (
        f"Lexicon directory not found at expected path:\n"
        f"  Path: {LEXICON_DIR}\n"
        f"  Hint: Create the directory or check PROJECT_ROOT resolution."
    )


def test_at_least_one_language_detected() -> None:
    """
    Ensure the loader finds at least one language configuration.
    """
    langs = available_languages()
    assert len(langs) > 0, (
        f"No language directories found in {LEXICON_DIR}.\n"
        f"  Expected at least one folder (e.g. 'en', 'fr').\n"
        f"  Detected: {langs}"
    )


def test_language_directories_integrity() -> None:
    """
    For every language discovered by available_languages(), ensure
    a corresponding directory or legacy file exists.
    """
    missing = []
    langs = available_languages()
    
    for lang in langs:
        # It must be either a directory (new standard) or a file (legacy fallback)
        dir_path = os.path.join(LEXICON_DIR, lang)
        file_path = os.path.join(LEXICON_DIR, f"{lang}_lexicon.json")
        
        if not os.path.isdir(dir_path) and not os.path.isfile(file_path):
            missing.append(lang)

    assert not missing, (
        f"Missing lexicon source for languages: {missing}\n"
        f"  Root: {LEXICON_DIR}\n"
        f"  Hint: Run 'utils/seed_lexicon_ai.py --langs {','.join(missing)}' to bootstrap."
    )


def test_lexicon_schema_has_no_errors() -> None:
    """
    Validate merged lexicon structure for each language and ensure there are
    no *error*-level issues. Warnings are allowed.
    """
    problems_by_lang: Dict[str, List[str]] = {}
    total_errors = 0

    for lang, issues in _collect_schema_issues():
        error_messages = [
            f"{issue.path}: {issue.message}"
            for issue in issues
            if issue.level.lower() == "error"
        ]
        if error_messages:
            problems_by_lang[lang] = error_messages
            total_errors += len(error_messages)

    if total_errors > 0:
        msg = ["Lexicon schema validation failed."]
        for lang, errors in problems_by_lang.items():
            msg.append(f"\n[{lang.upper()}]: {len(errors)} errors")
            # Cap output at 5 errors per language to avoid spamming logs
            for err in errors[:5]:
                msg.append(f"  - {err}")
            if len(errors) > 5:
                msg.append(f"  ... and {len(errors) - 5} more.")
        
        msg.append("\n👉 Remediation Hint: Run 'python utils/migrate_lexicon_schema.py --all' to fix common schema issues.")
        
        raise AssertionError("\n".join(msg))


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
        print("👉 Hint: Try 'python utils/migrate_lexicon_schema.py --all' to auto-fix.")
        return 1


if __name__ == "__main__":
    init_logging()
    exit_code = _print_human_report()
    sys.exit(exit_code)