# tools/qa/universal_test_runner.py
"""
Universal CSV Test Runner (Enterprise)

Purpose
- Execute generated CSV test suites (default: tools/qa/generated_datasets/test_suite_*.csv)
- Supports BOTH:
  (A) v2 template (recommended): Profession_ID / Nationality_ID (+ optional Frame_Type)
  (B) legacy templates: dynamic Profession_Lemma* / Nationality_Lemma* columns

Default behavior
- Skips rows with empty EXPECTED text (authoring workflow)
- Exits non-zero if any FAIL/CRASH, or if zero tests actually ran

CSV Schemas

(Recommended v2)
- Test_ID (optional)
- Frame_Type (optional; defaults to "bio")
- Name
- Gender
- Profession_ID     (QID like "Q33999") OR Profession_Lemma* column
- Nationality_ID    (QID like "Q38")    OR Nationality_Lemma* column
- EXPECTED_TEXT     (or EXPECTED_FULL_SENTENCE / EXPECTED_FULL_TEXT)

(Legacy)
- Name
- Gender or "Gender (Male/Female)"
- Profession_Lemma* column (e.g., Profession_Lemma_in_Italian)
- Nationality_Lemma* column
- EXPECTED_FULL_SENTENCE

Notes
- For QID resolution, this script uses app.shared.lexicon.LexiconRuntime if available.
- For rendering, it directly instantiates the GFGrammarEngine (v2.1 Adapter).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import asyncio
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------------
# Project bootstrap (avoid brittle sys.path hacks; still works from subprocess)
# -----------------------------------------------------------------------------
def _find_project_root(start: Path) -> Optional[Path]:
    """Walk up until we find a plausible repo root."""
    for p in [start, *start.parents]:
        if (p / "manage.py").exists() and (p / "app").exists():
            return p
        if (p / "pyproject.toml").exists() and (p / "app").exists():
            return p
    return None


THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _find_project_root(THIS_DIR) or _find_project_root(Path.cwd())
if PROJECT_ROOT and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# [REFACTOR] Use standardized logger
try:
    from utils.tool_logger import ToolLogger
    logger = ToolLogger(__file__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("TestRunner")


# -----------------------------------------------------------------------------
# Column detection (v2 + legacy)
# -----------------------------------------------------------------------------
NAME_COLUMN_CANDIDATES = ["Name", "name", "SUBJECT_NAME"]
GENDER_COLUMN_CANDIDATES = ["Gender", "gender", "Gender (Male/Female)"]
FRAME_COLUMN_CANDIDATES = ["Frame_Type", "FRAME_TYPE", "frame_type"]

EXPECTED_COLUMN_CANDIDATES = [
    "EXPECTED_TEXT",
    "EXPECTED_FULL_SENTENCE",
    "EXPECTED_FULL_TEXT",
    "EXPECTED",
]

TEST_ID_COLUMN_CANDIDATES = ["Test_ID", "TEST_ID", "ID"]

PROF_ID_COLUMN_CANDIDATES = ["Profession_ID", "PROFESSION_ID", "profession_id", "PROFESSION_QID", "Profession_QID"]
NAT_ID_COLUMN_CANDIDATES = ["Nationality_ID", "NATIONALITY_ID", "nationality_id", "NATIONALITY_QID", "Nationality_QID"]

# Legacy dynamic lemma columns
PROF_LEMMA_PREFIXES = ["Profession_Lemma", "PROFESSION_LEMMA", "profession_lemma"]
NAT_LEMMA_PREFIXES = ["Nationality_Lemma", "NATIONALITY_LEMMA", "nationality_lemma"]


def _first_present(fieldnames: List[str], candidates: List[str]) -> Optional[str]:
    lower_map = {f.lower(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def _first_prefixed(fieldnames: List[str], prefixes: List[str]) -> Optional[str]:
    for f in fieldnames:
        for pref in prefixes:
            if f.lower().startswith(pref.lower()):
                return f
    return None


def _clean_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    # Clean common authoring bracket style: "[Actor]" -> "Actor"
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        s = s[1:-1].strip()
    return s


def _infer_lang_from_filename(filename: str) -> Optional[str]:
    # test_suite_it.csv -> it
    m = re.search(r"(?:test_suite_|suite_)([a-z]{2,3})\.csv$", filename, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    # fallback: last token before .csv
    m = re.search(r"_([a-z]{2,3})\.csv$", filename, re.IGNORECASE)
    return m.group(1).lower() if m else None


# -----------------------------------------------------------------------------
# Lexicon resolver (optional)
# -----------------------------------------------------------------------------
class _LexiconResolver:
    def __init__(self) -> None:
        self._runtime = None
        try:
            # Preferred modern runtime
            from app.shared.lexicon import LexiconRuntime  # type: ignore

            self._runtime = LexiconRuntime()
        except Exception:
            self._runtime = None

    def available(self) -> bool:
        return self._runtime is not None

    def qid_to_lemma(self, qid: str, lang_code: str) -> Optional[str]:
        if not self._runtime:
            return None
        qid = _clean_cell(qid)
        if not qid:
            return None
        # If user already put a lemma instead of a QID, pass through.
        if not re.match(r"^Q\d+$", qid):
            return qid
        try:
            entry = self._runtime.lookup(qid, lang_code)  # returns LexiconEntry or None
            if not entry:
                return None
            # Most useful for router is lemma (human form), not gf_fun.
            lemma = getattr(entry, "lemma", None)
            return _clean_cell(lemma) or None
        except Exception:
            return None


# -----------------------------------------------------------------------------
# Renderer (GF Engine Adapter)
# -----------------------------------------------------------------------------
class _Renderer:
    """
    Wraps the v2.1 Grammar Engine for the test runner.
    Resolves the 'Missing Router' issue by using the Adapter directly.
    """
    def __init__(self) -> None:
        self._engine = None
        try:
            from app.adapters.engines.gf_wrapper import GFGrammarEngine
            self._engine = GFGrammarEngine()
        except Exception as e:
            logger.warning(f"Failed to initialize GFGrammarEngine: {e}")
            self._engine = None

    def available(self) -> bool:
        return self._engine is not None and self._engine.grammar is not None

    def render_bio(self, *, name: str, gender: str, profession: str, nationality: str, lang_code: str) -> str:
        if not self.available():
            raise RuntimeError("Grammar Engine not available. Check PGF file and gf-rgl installation.")

        from app.core.domain.frame import BioFrame
        
        # Construct v2.1 BioFrame
        # Note: We manually construct the frame here to mock the API ingress
        frame = BioFrame(
            frame_type="bio",
            subject={
                "name": name,
                "gender": gender,
                "profession": profession,
                "nationality": nationality
            }
        )

        try:
            # Run async engine method synchronously
            sentence = asyncio.run(self._engine.generate(lang_code, frame))
            return sentence.text
        except Exception as e:
            raise RuntimeError(f"Generation failed: {e}")


# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------
@dataclass
class CaseResult:
    file: str
    lang: str
    test_id: str
    frame_type: str
    status: str  # PASS/FAIL/SKIP/CRASH
    expected: str = ""
    actual: str = ""
    detail: str = ""


@dataclass
class RunSummary:
    started_at: float
    finished_at: float
    duration_s: float
    files: int
    passed: int
    failed: int
    skipped: int
    crashed: int
    total: int


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------
DEFAULT_DATASET_DIR_CANDIDATES = [
    # Preferred (new layout)
    THIS_DIR / "generated_datasets",
    # Legacy (older layout)
    (PROJECT_ROOT / "qa_tools" / "generated_datasets") if PROJECT_ROOT else None,
    (PROJECT_ROOT / "tools" / "qa" / "generated_datasets") if PROJECT_ROOT else None,
    (PROJECT_ROOT / "generated_datasets") if PROJECT_ROOT else None,
]


def _resolve_dataset_dir(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p
    env = os.getenv("AWA_TEST_DATASET_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    for c in DEFAULT_DATASET_DIR_CANDIDATES:
        if c and c.exists() and c.is_dir():
            return c
    # fall back to THIS_DIR/generated_datasets even if missing (we'll error nicely)
    return THIS_DIR / "generated_datasets"


def _iter_csv_files(dataset_dir: Path, pattern: str) -> List[Path]:
    if not dataset_dir.exists():
        return []
    return sorted(dataset_dir.glob(pattern))


def _extract_inputs_from_row(
    row: Dict[str, Any],
    *,
    fieldnames: List[str],
    lang_code: str,
    lexicon: _LexiconResolver,
) -> Tuple[str, str, str, str, str, str]:
    test_id_col = _first_present(fieldnames, TEST_ID_COLUMN_CANDIDATES)
    frame_col = _first_present(fieldnames, FRAME_COLUMN_CANDIDATES)
    name_col = _first_present(fieldnames, NAME_COLUMN_CANDIDATES)
    gender_col = _first_present(fieldnames, GENDER_COLUMN_CANDIDATES)
    expected_col = _first_present(fieldnames, EXPECTED_COLUMN_CANDIDATES)

    # Legacy lemma columns
    prof_lemma_col = _first_prefixed(fieldnames, PROF_LEMMA_PREFIXES)
    nat_lemma_col = _first_prefixed(fieldnames, NAT_LEMMA_PREFIXES)

    # v2 ID columns
    prof_id_col = _first_present(fieldnames, PROF_ID_COLUMN_CANDIDATES)
    nat_id_col = _first_present(fieldnames, NAT_ID_COLUMN_CANDIDATES)

    test_id = _clean_cell(row.get(test_id_col or "", "")) or "Unknown"
    frame_type = _clean_cell(row.get(frame_col or "", "")) or "bio"

    if not name_col:
        raise ValueError("Missing required column: Name")
    if not gender_col:
        raise ValueError("Missing required column: Gender")

    name = _clean_cell(row.get(name_col, ""))
    gender = _clean_cell(row.get(gender_col, "")) or "Unknown"

    expected = _clean_cell(row.get(expected_col or "", ""))

    # Profession / Nationality resolution strategy:
    # 1) Prefer lemma columns if present (legacy authoring style)
    # 2) Else use ID columns and resolve via lexicon runtime (QIDs -> lemma)
    profession = ""
    nationality = ""

    if prof_lemma_col:
        profession = _clean_cell(row.get(prof_lemma_col, ""))
    if nat_lemma_col:
        nationality = _clean_cell(row.get(nat_lemma_col, ""))

    if not profession and prof_id_col:
        qid = _clean_cell(row.get(prof_id_col, ""))
        profession = lexicon.qid_to_lemma(qid, lang_code) or ""
    if not nationality and nat_id_col:
        qid = _clean_cell(row.get(nat_id_col, ""))
        nationality = lexicon.qid_to_lemma(qid, lang_code) or ""

    return test_id, frame_type, name, gender, profession, nationality, expected


def run_universal_tests(
    *,
    dataset_dir: Path,
    pattern: str,
    lang_filter: Optional[List[str]],
    limit_per_file: Optional[int],
    fail_fast: bool,
    strict: bool,
    max_failures_to_print: int,
    json_report_path: Optional[Path],
    verbose: bool,
) -> int:
    logger.info("========================================")
    logger.info("   UNIVERSAL TEST RUNNER (Enterprise)   ")
    logger.info("========================================")
    logger.info(f"Dataset dir: {dataset_dir}")
    logger.info(f"Pattern:     {pattern}")
    if lang_filter:
        logger.info(f"Lang filter: {', '.join(lang_filter)}")

    if not dataset_dir.exists():
        logger.error(f"Test directory not found: {dataset_dir}")
        logger.info("Hint: Run tools/qa/test_suite_generator.py first, or set AWA_TEST_DATASET_DIR.")
        return 2

    csv_files = _iter_csv_files(dataset_dir, pattern)
    if not csv_files:
        logger.error("No CSV files found.")
        logger.info("Hint: Run tools/qa/test_suite_generator.py first.")
        return 2

    renderer = _Renderer()
    if not renderer.available():
        logger.error("Grammar Engine not available.")
        logger.info("Hint: Check if AbstractWiki.pgf exists in 'gf/' and 'pgf' library is installed.")
        return 2

    lexicon = _LexiconResolver()
    if verbose:
        logger.info(f"Lexicon resolver: {'ON' if lexicon.available() else 'OFF'}")

    started = time.time()
    results: List[CaseResult] = []

    total_passed = total_failed = total_skipped = total_crashed = 0
    total_active = 0

    for fpath in csv_files:
        lang = _infer_lang_from_filename(fpath.name) or "unknown"
        if lang_filter and lang.lower() not in {x.lower() for x in lang_filter}:
            continue

        logger.info("")
        logger.info("----------------------------------------")
        logger.info(f"Suite: {fpath.name}  [lang={lang}]")
        logger.info("----------------------------------------")

        file_pass = file_fail = file_skip = file_crash = 0
        file_active = 0

        with fpath.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                logger.error("CSV has no headers.")
                continue

            fieldnames = list(reader.fieldnames)
            row_count = 0

            for row in reader:
                row_count += 1
                if limit_per_file and row_count > limit_per_file:
                    break

                try:
                    test_id, frame_type, name, gender, profession, nationality, expected = _extract_inputs_from_row(
                        row, fieldnames=fieldnames, lang_code=lang, lexicon=lexicon
                    )

                    # Authoring workflow: skip rows missing expected, unless strict
                    if not expected:
                        if strict:
                            file_fail += 1
                            total_failed += 1
                            results.append(
                                CaseResult(
                                    file=fpath.name,
                                    lang=lang,
                                    test_id=test_id,
                                    frame_type=frame_type,
                                    status="FAIL",
                                    expected="(missing EXPECTED)",
                                    actual="",
                                    detail="Expected text is empty (strict mode).",
                                )
                            )
                            if fail_fast:
                                raise RuntimeError("Fail-fast: missing EXPECTED in strict mode.")
                        else:
                            file_skip += 1
                            total_skipped += 1
                            results.append(
                                CaseResult(
                                    file=fpath.name,
                                    lang=lang,
                                    test_id=test_id,
                                    frame_type=frame_type,
                                    status="SKIP",
                                    expected="",
                                    actual="",
                                    detail="Missing EXPECTED text.",
                                )
                            )
                        continue

                    # Only bio supported here (universal runner can be extended later)
                    if frame_type.lower() not in {"bio", "biography"}:
                        file_skip += 1
                        total_skipped += 1
                        results.append(
                            CaseResult(
                                file=fpath.name,
                                lang=lang,
                                test_id=test_id,
                                frame_type=frame_type,
                                status="SKIP",
                                expected=expected,
                                actual="",
                                detail=f"Unsupported frame_type: {frame_type}",
                            )
                        )
                        continue

                    # Must have resolved inputs
                    if not name or not profession or not nationality:
                        msg = f"Missing inputs (name={bool(name)}, profession={bool(profession)}, nationality={bool(nationality)})"
                        if strict:
                            file_fail += 1
                            total_failed += 1
                            results.append(
                                CaseResult(
                                    file=fpath.name,
                                    lang=lang,
                                    test_id=test_id,
                                    frame_type=frame_type,
                                    status="FAIL",
                                    expected=expected,
                                    actual="",
                                    detail=msg,
                                )
                            )
                            if fail_fast:
                                raise RuntimeError("Fail-fast: missing required inputs in strict mode.")
                        else:
                            file_skip += 1
                            total_skipped += 1
                            results.append(
                                CaseResult(
                                    file=fpath.name,
                                    lang=lang,
                                    test_id=test_id,
                                    frame_type=frame_type,
                                    status="SKIP",
                                    expected=expected,
                                    actual="",
                                    detail=msg,
                                )
                            )
                        continue

                    file_active += 1
                    total_active += 1

                    actual = renderer.render_bio(
                        name=name,
                        gender=gender,
                        profession=profession,
                        nationality=nationality,
                        lang_code=lang,
                    ).strip()

                    if actual == expected:
                        file_pass += 1
                        total_passed += 1
                        results.append(
                            CaseResult(
                                file=fpath.name,
                                lang=lang,
                                test_id=test_id,
                                frame_type=frame_type,
                                status="PASS",
                                expected=expected,
                                actual=actual,
                            )
                        )
                    else:
                        file_fail += 1
                        total_failed += 1
                        results.append(
                            CaseResult(
                                file=fpath.name,
                                lang=lang,
                                test_id=test_id,
                                frame_type=frame_type,
                                status="FAIL",
                                expected=expected,
                                actual=actual,
                                detail=f"Input: {name} ({gender}) | {profession} | {nationality}",
                            )
                        )

                        if max_failures_to_print > 0 and file_fail <= max_failures_to_print:
                            logger.error(f"FAIL {test_id}")
                            logger.info(f"  Input:    {name} ({gender}) | {profession} | {nationality}")
                            logger.info(f"  Expected: {expected}")
                            logger.info(f"  Actual:   {actual}")

                        if fail_fast:
                            raise RuntimeError("Fail-fast: first mismatch encountered.")

                except Exception as e:
                    # Crash for this row
                    file_crash += 1
                    total_crashed += 1
                    results.append(
                        CaseResult(
                            file=fpath.name,
                            lang=lang,
                            test_id=_clean_cell(row.get("Test_ID", "")) or "Unknown",
                            frame_type=_clean_cell(row.get("Frame_Type", "")) or "bio",
                            status="CRASH",
                            expected=_clean_cell(row.get("EXPECTED_TEXT", "")),
                            actual="",
                            detail=str(e),
                        )
                    )
                    logger.error(f"CRASH: {str(e)}")
                    if fail_fast:
                        break

        # File summary
        denom = file_pass + file_fail
        if denom > 0:
            rate = (file_pass / denom) * 100.0
            logger.info(f"Result: {file_pass} passed, {file_fail} failed, {file_skip} skipped, {file_crash} crashed  ({rate:.1f}% pass)")
        else:
            logger.info(f"Result: {file_pass} passed, {file_fail} failed, {file_skip} skipped, {file_crash} crashed")

        if fail_fast and (file_fail > 0 or file_crash > 0):
            break

    finished = time.time()
    duration = finished - started

    logger.info("")
    logger.info("========================================")
    logger.info(f"RUN COMPLETE in {duration:.2f}s")
    logger.info("========================================")
    logger.info(f"Passed:  {total_passed}")
    logger.info(f"Failed:  {total_failed}")
    logger.info(f"Skipped: {total_skipped}")
    logger.info(f"Crashed: {total_crashed}")
    logger.info(f"Active:  {total_active}")

    summary = RunSummary(
        started_at=started,
        finished_at=finished,
        duration_s=duration,
        files=len(csv_files),
        passed=total_passed,
        failed=total_failed,
        skipped=total_skipped,
        crashed=total_crashed,
        total=(total_passed + total_failed + total_skipped + total_crashed),
    )

    if json_report_path:
        payload = {
            "summary": asdict(summary),
            "results": [asdict(r) for r in results],
        }
        json_report_path.parent.mkdir(parents=True, exist_ok=True)
        json_report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"\nWrote JSON report: {json_report_path}")

    # Exit codes:
    # 0 = success (no fail/crash and at least 1 active test)
    # 1 = fail/crash present
    # 2 = misconfigured / nothing ran
    
    exit_code = 0
    if total_failed > 0 or total_crashed > 0:
        exit_code = 1
    if total_active == 0:
        exit_code = 2

    # [REFACTOR] Standardized Summary for GUI
    summary_msg = f"Passed: {total_passed}, Failed: {total_failed}, Crashed: {total_crashed}."
    
    if hasattr(logger, "finish"):
        logger.finish(
            message=summary_msg,
            success=(exit_code == 0),
            details=asdict(summary)
        )
        
    return exit_code


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Universal CSV Test Runner (Enterprise)")
    p.add_argument("--dataset-dir", default=None, help="Directory containing CSV suites.")
    p.add_argument("--pattern", default="test_suite_*.csv", help="Glob pattern for CSV files.")
    p.add_argument("--langs", default=None, help="Comma-separated language filter (e.g., en,fr,it).")
    p.add_argument("--limit", type=int, default=None, help="Max rows per file.")
    p.add_argument("--fail-fast", action="store_true", help="Stop on first FAIL/CRASH.")
    p.add_argument("--strict", action="store_true", help="Treat missing EXPECTED or inputs as FAIL (not SKIP).")
    p.add_argument("--print-failures", type=int, default=10, help="Print first N failures per file (0 = none).")
    p.add_argument("--json-report", default=None, help="Write a JSON report to this path.")
    p.add_argument("--verbose", action="store_true", help="Verbose diagnostics.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    # [REFACTOR] Standardized Start
    if hasattr(logger, "start"):
        logger.start("Universal Test Runner")

    args = _parse_args(argv)

    dataset_dir = _resolve_dataset_dir(args.dataset_dir)
    lang_filter = [x.strip() for x in (args.langs or "").split(",") if x.strip()] or None
    json_report_path = Path(args.json_report).expanduser().resolve() if args.json_report else None

    return run_universal_tests(
        dataset_dir=dataset_dir,
        pattern=args.pattern,
        lang_filter=lang_filter,
        limit_per_file=args.limit,
        fail_fast=bool(args.fail_fast),
        strict=bool(args.strict),
        max_failures_to_print=max(0, int(args.print_failures)),
        json_report_path=json_report_path,
        verbose=bool(args.verbose),
    )


if __name__ == "__main__":
    raise SystemExit(main())