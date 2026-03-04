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

By default it scans all *.json files under data/lexicon/ (recursively),
merges files for the same language (e.g. en_lexicon.json + en_people.json),
and prints per-language stats.

Usage
=====

From project root:

    python utils/dump_lexicon_stats.py
    python utils/dump_lexicon_stats.py --langs en fr
    python utils/dump_lexicon_stats.py --format json --out /tmp/lexicon_stats.json

Machine-readable stdout JSON (no logs mixed in):
    python utils/dump_lexicon_stats.py --format json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Project root & logging
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DEFAULT_LEXICON_DIR = PROJECT_ROOT / "data" / "lexicon"


def _make_fallback_logger(name: str):
    """
    Fallback logger that writes to stdout (GUI-friendly).
    Exposes .info/.warning/.error and optional .start/.stage/.finish shims.
    """
    import logging

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False

    # Shims to match ToolLogger-ish calls
    def _start(title: str = "") -> None:
        if title:
            logger.info(title)

    def _stage(stage: str, message: str = "") -> None:
        logger.info(f"[{stage}] {message}".rstrip())

    def _finish(message: str = "", *, success: Optional[bool] = None, details: Optional[dict] = None) -> None:
        prefix = "OK" if success is True else ("FAIL" if success is False else "DONE")
        line = f"{prefix}: {message}".strip()
        logger.info(line)
        if details:
            logger.info(json.dumps(details, ensure_ascii=False))

    logger.start = _start  # type: ignore[attr-defined]
    logger.stage = _stage  # type: ignore[attr-defined]
    logger.finish = _finish  # type: ignore[attr-defined]
    return logger


# Prefer new standardized logger, fallback to stdout logger.
try:
    from utils.tool_logger import ToolLogger  # type: ignore

    log = ToolLogger(__file__)
except Exception:  # pragma: no cover
    log = _make_fallback_logger("dump_lexicon_stats")


def _call_if_exists(obj, method: str, *args, **kwargs) -> None:
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args, **kwargs)
        except TypeError:
            # Be forgiving if signatures differ slightly across logger versions.
            try:
                fn(*args)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helpers for finding / grouping lexicon files
# ---------------------------------------------------------------------------

def _infer_lang_from_filename(filename: str) -> str:
    """
    Infer a language code from a lexicon JSON filename.

    Heuristic:
      - Use the part before the first underscore, if present.
        Example: "en_lexicon" -> "en", "en_people" -> "en"
      - Otherwise use the whole stem.
    """
    stem = Path(filename).stem
    return stem.split("_", 1)[0] if "_" in stem else stem


def find_lexicon_files(lexicon_dir: str | Path, langs: Optional[Iterable[str]] = None) -> dict[str, List[str]]:
    """
    Scan lexicon_dir for JSON lexicon files (recursively) and group them by language code.
    """
    lexicon_dir = Path(lexicon_dir)

    target_langs = {s.strip() for s in langs if s and s.strip()} if langs is not None else None
    by_lang: dict[str, List[str]] = defaultdict(list)

    if not lexicon_dir.is_dir():
        raise FileNotFoundError(f"Lexicon directory not found: {lexicon_dir}")

    # Recursive scan, deterministic ordering (by relative path then name)
    all_json = sorted(
        (p for p in lexicon_dir.rglob("*.json") if p.is_file()),
        key=lambda p: str(p.relative_to(lexicon_dir)).lower(),
    )

    for path in all_json:
        lang = _infer_lang_from_filename(path.name)
        if target_langs is not None and lang not in target_langs:
            continue
        by_lang[lang].append(str(path.resolve()))

    # Deterministic ordering within language (by basename, then full path)
    for lang in list(by_lang.keys()):
        by_lang[lang].sort(key=lambda p: (os.path.basename(p).lower(), p.lower()))

    return by_lang


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

@dataclass
class MergeInfo:
    files_read: int = 0
    files_failed: int = 0
    overrides: int = 0
    invalid_lemmas_container: int = 0  # "lemmas" exists but is not a dict
    invalid_entries: int = 0           # lemma entry is not a dict


@dataclass
class LangStats:
    lang: str
    files: List[str]
    total_lemmas: int
    pos_counts: dict[str, int]
    human_nouns: int
    nationality_adjs: int
    overrides: int
    invalid_entries: int

    @property
    def human_nouns_pct(self) -> float:
        return (100.0 * self.human_nouns / self.total_lemmas) if self.total_lemmas else 0.0

    @property
    def nationality_adjs_pct(self) -> float:
        return (100.0 * self.nationality_adjs / self.total_lemmas) if self.total_lemmas else 0.0

    def to_json_dict(self) -> dict:
        d = asdict(self)
        d["human_nouns_pct"] = self.human_nouns_pct
        d["nationality_adjs_pct"] = self.nationality_adjs_pct
        return d


def load_lemmas_from_files(files: Iterable[str]) -> Tuple[dict[str, dict], MergeInfo]:
    """
    Load and merge lemma dictionaries from a list of JSON files.

    For identical lemma keys across files for the same language,
    later files override earlier ones.
    """
    merged: dict[str, dict] = {}
    info = MergeInfo()

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            info.files_read += 1

            lemmas = data.get("lemmas", {})
            if not isinstance(lemmas, dict):
                info.invalid_lemmas_container += 1
                continue

            for k, v in lemmas.items():
                if k in merged:
                    info.overrides += 1
                if isinstance(v, dict):
                    merged[str(k)] = v
                else:
                    info.invalid_entries += 1

        except Exception as e:
            info.files_failed += 1
            _call_if_exists(log, "warning", f"Failed to read {path}: {e}")

    return merged, info


def compute_stats_for_lang(lang: str, lemmas: Mapping[str, dict], merge_info: MergeInfo) -> LangStats:
    pos_counts: Counter[str] = Counter()
    human_nouns = 0
    nationality_adjs = 0
    invalid_entries = merge_info.invalid_entries

    for _, entry in lemmas.items():
        if not isinstance(entry, dict):
            invalid_entries += 1
            continue

        pos = str(entry.get("pos", "")).upper().strip()
        if pos:
            pos_counts[pos] += 1

        if pos == "NOUN" and bool(entry.get("human", False)):
            human_nouns += 1

        if pos == "ADJ" and bool(entry.get("nationality", False)):
            nationality_adjs += 1

    return LangStats(
        lang=lang,
        files=[],
        total_lemmas=len(lemmas),
        pos_counts=dict(pos_counts),
        human_nouns=human_nouns,
        nationality_adjs=nationality_adjs,
        overrides=merge_info.overrides,
        invalid_entries=invalid_entries,
    )


def print_stats(stats: LangStats, *, base_dir: Path) -> None:
    _call_if_exists(log, "info", f"=== Lexicon stats for '{stats.lang}' ===")

    # Friendlier file list: relative to base_dir if possible
    def _rel(p: str) -> str:
        try:
            return str(Path(p).resolve().relative_to(base_dir))
        except Exception:
            return os.path.basename(p)

    file_list = ", ".join(_rel(f) for f in stats.files)
    _call_if_exists(log, "info", f"  Files: {file_list}")
    _call_if_exists(log, "info", f"  Total lemmas: {stats.total_lemmas}")
    _call_if_exists(log, "info", f"  Merge overrides (later file wins): {stats.overrides}")
    if stats.invalid_entries:
        _call_if_exists(log, "warning", f"  Invalid lemma entries skipped: {stats.invalid_entries}")

    if stats.total_lemmas == 0:
        _call_if_exists(log, "warning", "  No lemmas found.")
        _call_if_exists(log, "info", "")
        return

    _call_if_exists(log, "info", "  By POS:")
    for pos, count in sorted(stats.pos_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = 100.0 * count / stats.total_lemmas
        _call_if_exists(log, "info", f"    {pos:<8} {count:5d} ({pct:5.1f}%)")

    _call_if_exists(log, "info", "  Selected categories:")
    _call_if_exists(
        log,
        "info",
        f"    Human nouns:             {stats.human_nouns} ({stats.human_nouns_pct:5.1f}%)",
    )
    _call_if_exists(
        log,
        "info",
        f"    Nationality adjectives:  {stats.nationality_adjs} ({stats.nationality_adjs_pct:5.1f}%)",
    )
    _call_if_exists(log, "info", "")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dump basic statistics about lexicon JSON files.")
    parser.add_argument(
        "--lexicon-dir",
        "-d",
        default=str(DEFAULT_LEXICON_DIR),
        help=f"Directory containing lexicon JSON files (default: {DEFAULT_LEXICON_DIR})",
    )
    parser.add_argument(
        "--langs",
        "-l",
        nargs="*",
        help="Optional list of language codes to restrict to (e.g. en fr ru). "
             "If omitted, all languages found in the directory are included.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. 'text' logs to console; 'json' emits a machine-readable summary.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output file path. If omitted and --format json, JSON is printed to stdout with no logs.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # If user wants machine-readable JSON on stdout, do NOT emit logs.
    machine_stdout_json = (args.format == "json" and not args.out)

    lexicon_dir = Path(args.lexicon_dir).expanduser().resolve()

    if not machine_stdout_json:
        _call_if_exists(log, "start", "Lexicon Stats Dump")
        _call_if_exists(log, "stage", "Scan", f"Directory: {lexicon_dir}")

    try:
        lang_files = find_lexicon_files(lexicon_dir, langs=args.langs)
    except FileNotFoundError:
        if machine_stdout_json:
            print(json.dumps({"error": "Lexicon directory not found", "lexicon_dir": str(lexicon_dir)}, indent=2))
        else:
            _call_if_exists(log, "error", f"Lexicon directory not found: {lexicon_dir}")
            _call_if_exists(log, "finish", "Lexicon directory not found.", success=False, details={"lexicon_dir": str(lexicon_dir)})
        sys.exit(1)

    if not lang_files:
        msg = (
            f"No lexicon JSON files found for languages {args.langs} in {lexicon_dir}."
            if args.langs
            else f"No lexicon JSON files found in {lexicon_dir}."
        )
        if machine_stdout_json:
            print(json.dumps({"error": msg, "lexicon_dir": str(lexicon_dir), "langs": args.langs or []}, indent=2))
        else:
            _call_if_exists(log, "warning", msg)
            _call_if_exists(log, "finish", "No files found.", success=False, details={"lexicon_dir": str(lexicon_dir)})
        sys.exit(0)

    if not machine_stdout_json:
        _call_if_exists(log, "info", f"Lexicon directory: {lexicon_dir}")
        _call_if_exists(log, "info", f"Languages found: {', '.join(sorted(lang_files.keys()))}")

    all_lang_stats: List[LangStats] = []
    global_lemmas = 0
    langs_processed = 0
    global_overrides = 0
    global_invalid_entries = 0

    for lang, files in sorted(lang_files.items(), key=lambda kv: kv[0]):
        if not machine_stdout_json:
            _call_if_exists(log, "stage", "Merge", f"{lang}: {len(files)} file(s)")

        lemmas, merge_info = load_lemmas_from_files(files)
        stats = compute_stats_for_lang(lang, lemmas, merge_info)
        stats.files = files

        all_lang_stats.append(stats)
        global_lemmas += stats.total_lemmas
        global_overrides += stats.overrides
        global_invalid_entries += stats.invalid_entries
        langs_processed += 1

        if args.format == "text" and not machine_stdout_json:
            print_stats(stats, base_dir=lexicon_dir)

    summary_data = {
        "lexicon_dir": str(lexicon_dir),
        "languages_scanned": langs_processed,
        "total_lemmas_found": global_lemmas,
        "total_merge_overrides": global_overrides,
        "total_invalid_entries": global_invalid_entries,
        "per_language": [s.to_json_dict() for s in all_lang_stats],
    }

    if args.format == "json":
        payload = json.dumps(summary_data, ensure_ascii=False, indent=2)
        if args.out:
            out_path = Path(args.out).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload, encoding="utf-8")
            if not machine_stdout_json:
                _call_if_exists(log, "info", f"Wrote JSON stats to: {out_path}")
        else:
            # Machine-readable stdout (no logger output mixed in)
            print(payload)

    if not machine_stdout_json:
        _call_if_exists(
            log,
            "finish",
            f"Stats dump complete. Found {global_lemmas} entries across {langs_processed} languages.",
            details={
                "languages_scanned": langs_processed,
                "total_lemmas_found": global_lemmas,
                "total_merge_overrides": global_overrides,
                "total_invalid_entries": global_invalid_entries,
            },
        )


if __name__ == "__main__":
    main()