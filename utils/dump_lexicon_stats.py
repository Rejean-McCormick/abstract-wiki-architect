# utils/dump_lexicon_stats.py
"""
utils/dump_lexicon_stats.py
---------------------------

Quick statistics over the JSON lexicon files in data/lexicon/.

This is a lightweight, data-driven script: it reads the raw JSON files
directly, without requiring the full `lexicon` Python package to be
implemented. It assumes the files follow the schema used in this
project:

    {
      "_meta": { ... },
      "lemmas": {
        "lemma_string": {
          "pos": "NOUN" | "ADJ" | "VERB" | ...,
          "human": true/false (optional),
          "nationality": true/false (optional),
          ...
        },
        ...
      }
    }

By default it scans all *.json files under data/lexicon/, merges files
for the same language (e.g. en_lexicon.json + en_people.json), and
prints per-language stats.

Usage
=====

From project root:

    python utils/dump_lexicon_stats.py
    python utils/dump_lexicon_stats.py --langs en fr
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

# ---------------------------------------------------------------------------
# Project root & logging
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
    
DEFAULT_LEXICON_DIR = os.path.join(PROJECT_ROOT, "data", "lexicon")

# [REFACTOR] Use the standardized ToolLogger for GUI-compatible output
try:
    from utils.tool_logger import ToolLogger
    logger = ToolLogger(__file__)
except ImportError:
    # Fallback for standalone runs without the new logger module
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    logger = logging.getLogger("dump_stats")


# ---------------------------------------------------------------------------
# Helpers for finding / grouping lexicon files
# ---------------------------------------------------------------------------


def _infer_lang_from_filename(filename: str) -> str:
    """
    Infer a language code from a lexicon JSON filename.

    Heuristic:
        - Take the stem (filename without extension).
        - Use the part before the first underscore, if present.
          Example: "en_lexicon" -> "en", "en_people" -> "en"
        - Otherwise use the whole stem.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    if "_" in stem:
        return stem.split("_", 1)[0]
    return stem


def find_lexicon_files(
    lexicon_dir: str, langs: Iterable[str] | None = None
) -> Dict[str, List[str]]:
    """
    Scan lexicon_dir for JSON lexicon files and group them by language code.

    Args:
        lexicon_dir:
            Directory containing *.json lexicon files.
        langs:
            Optional iterable of language codes to restrict to. If None,
            all languages are included.

    Returns:
        Mapping: lang_code → list of JSON file paths (absolute).
    """
    if langs is not None:
        target_langs = {s.strip() for s in langs if s.strip()}
    else:
        target_langs = None

    by_lang: Dict[str, List[str]] = defaultdict(list)

    if not os.path.isdir(lexicon_dir):
        # We raise here because this is a critical setup error
        logger.error(f"Lexicon directory not found: {lexicon_dir}")
        raise FileNotFoundError(f"Lexicon directory not found: {lexicon_dir}")

    for entry in os.listdir(lexicon_dir):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(lexicon_dir, entry)
        if not os.path.isfile(path):
            continue

        lang = _infer_lang_from_filename(entry)
        if target_langs is not None and lang not in target_langs:
            continue

        by_lang[lang].append(path)

    return by_lang


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------


def load_lemmas_from_files(files: Iterable[str]) -> Dict[str, dict]:
    """
    Load and merge lemma dictionaries from a list of JSON files.

    For identical lemma keys across files for the same language,
    later files override earlier ones.
    """
    merged: Dict[str, dict] = {}
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lemmas = data.get("lemmas", {})
            if not isinstance(lemmas, dict):
                continue
            merged.update(lemmas)
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
            
    return merged


def compute_stats_for_lang(
    lang: str, lemmas: Dict[str, dict]
) -> Tuple[Counter, int, int, int]:
    """
    Compute basic statistics for a single language.

    Returns:
        pos_counts:
            Counter mapping POS → count of lemmas.
        total_human_nouns:
            Count of lemmas with pos=NOUN and human=true.
        total_nationality_adjs:
            Count of lemmas with pos=ADJ and nationality=true.
        total_lemmas:
            Total number of lemma entries.
    """
    pos_counts: Counter = Counter()
    human_nouns = 0
    nationality_adjs = 0

    for lemma, entry in lemmas.items():
        if not isinstance(entry, dict):
            continue
        pos = entry.get("pos", "").upper().strip()
        if pos:
            pos_counts[pos] += 1

        if pos == "NOUN" and bool(entry.get("human", False)):
            human_nouns += 1

        if pos == "ADJ" and bool(entry.get("nationality", False)):
            nationality_adjs += 1

    total_lemmas = len(lemmas)
    return pos_counts, human_nouns, nationality_adjs, total_lemmas


def print_stats(
    lang: str,
    files: List[str],
    pos_counts: Counter,
    human_nouns: int,
    nationality_adjs: int,
    total_lemmas: int,
) -> None:
    """
    Pretty-print stats for a single language using the standardized logger.
    """
    # Use logger.info instead of print so it's captured by the GUI console stream
    logger.info(f"=== Lexicon stats for '{lang}' ===")
    
    file_list = ", ".join(os.path.basename(f) for f in files)
    logger.info(f"  Files: {file_list}")
    logger.info(f"  Total lemmas: {total_lemmas}")

    if total_lemmas == 0:
        logger.warning("  No lemmas found.")
        return

    logger.info("  By POS:")
    for pos, count in pos_counts.most_common():
        pct = 100.0 * count / total_lemmas
        logger.info(f"    {pos:<8} {count:5d} ({pct:5.1f}%)")

    logger.info("  Selected categories:")
    logger.info(f"    Human nouns:          {human_nouns}")
    logger.info(f"    Nationality adjectives: {nationality_adjs}")
    logger.info("") # Spacer


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dump basic statistics about lexicon JSON files."
    )
    parser.add_argument(
        "--lexicon-dir",
        "-d",
        default=DEFAULT_LEXICON_DIR,
        help=f"Directory containing lexicon JSON files (default: {DEFAULT_LEXICON_DIR})",
    )
    parser.add_argument(
        "--langs",
        "-l",
        nargs="*",
        help="Optional list of language codes to restrict to (e.g. en fr ru). "
        "If omitted, all languages found in the directory are included.",
    )
    return parser


def main(argv: List[str] | None = None) -> None:
    # [REFACTOR] Standardized Start
    if hasattr(logger, "start"):
        logger.start("Lexicon Stats Dump")

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    lexicon_dir = os.path.abspath(args.lexicon_dir)
    
    try:
        lang_files = find_lexicon_files(lexicon_dir, langs=args.langs)
    except FileNotFoundError:
        # Error already logged inside find_lexicon_files
        sys.exit(1)

    if not lang_files:
        if args.langs:
            logger.warning(
                f"No lexicon JSON files found for languages {args.langs} in {lexicon_dir}."
            )
        else:
            logger.warning(f"No lexicon JSON files found in {lexicon_dir}.")
        
        # Early exit if nothing to do
        if hasattr(logger, "finish"):
            logger.finish("No files found.", success=False)
        sys.exit(0)

    logger.info(f"Lexicon directory: {lexicon_dir}")
    logger.info(f"Languages found: {', '.join(sorted(lang_files.keys()))}")

    # Accumulate global stats for the summary
    global_lemmas = 0
    langs_processed = 0

    for lang, files in sorted(lang_files.items()):
        lemmas = load_lemmas_from_files(files)
        pos_counts, human_nouns, nationality_adjs, total_lemmas = (
            compute_stats_for_lang(lang, lemmas)
        )
        print_stats(
            lang, files, pos_counts, human_nouns, nationality_adjs, total_lemmas
        )
        global_lemmas += total_lemmas
        langs_processed += 1

    # [REFACTOR] Standardized Summary
    summary_data = {
        "languages_scanned": langs_processed,
        "total_lemmas_found": global_lemmas
    }
    
    if hasattr(logger, "finish"):
        logger.finish(
            message=f"Stats dump complete. Found {global_lemmas} entries across {langs_processed} languages.",
            details=summary_data
        )


if __name__ == "__main__":
    main()