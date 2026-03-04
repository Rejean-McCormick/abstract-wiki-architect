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

Notes
- For QID resolution, this script uses app.shared.lexicon.LexiconRuntime if available.
- For rendering, it instantiates the GFGrammarEngine (v2.1 Adapter).

Key reliability guarantees in this runner:
- The GFGrammarEngine is lazy-loaded; we *must* call health_check()/generate() once to load PGF.
- Async calls are executed via a dedicated background event loop thread (safe even if caller has a running loop).

CLI compatibility notes (GUI/tool-runner):
- --langs accepts BOTH: "--langs en fr" and "--langs en,fr"
- --print-failures accepts BOTH:
    * integer N (print first N failures per file, 0 = none)
    * a file path (write all FAIL/CRASH cases to that file)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, TypeVar

T = TypeVar("T")

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

# Ensure relative paths (like ".env") resolve as expected when tools execute from elsewhere.
if PROJECT_ROOT:
    try:
        os.chdir(str(PROJECT_ROOT))
    except Exception:
        pass

# [REFACTOR] Use standardized logger
IS_TOOL_LOGGER = False
try:
    from utils.tool_logger import ToolLogger  # type: ignore

    logger = ToolLogger(__file__)  # type: ignore
    IS_TOOL_LOGGER = True
except Exception:
    import logging

    # IMPORTANT: GUI reads stdout; keep fallback logger on stdout too.
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    logger = logging.getLogger("TestRunner")


def _log_info(msg: str = "") -> None:
    if hasattr(logger, "info"):
        logger.info(msg)  # type: ignore[attr-defined]
    else:
        print(msg)


def _log_error(msg: str) -> None:
    if IS_TOOL_LOGGER and hasattr(logger, "error"):
        logger.error(msg)  # type: ignore[attr-defined]
    else:
        # keep "Error:" prefix for compatibility with grep-based consumers
        _log_info(f"Error: {msg}")


def _log_warning(msg: str) -> None:
    if IS_TOOL_LOGGER and hasattr(logger, "warning"):
        logger.warning(msg)  # type: ignore[attr-defined]
    else:
        _log_info(f"Warning: {msg}")


# -----------------------------------------------------------------------------
# Async execution helper (robust + efficient)
# -----------------------------------------------------------------------------
class _AsyncLoopThread:
    """
    Runs an asyncio event loop on a dedicated background thread.

    Why:
    - Avoids calling asyncio.run() per test case (slow).
    - Works even when this script is invoked from an environment that already has a running loop.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

        def _thread_main() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            loop.run_forever()

            # graceful shutdown
            try:
                pending = asyncio.all_tasks(loop)
            except Exception:
                pending = set()

            for task in pending:
                task.cancel()

            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass

            try:
                loop.close()
            except Exception:
                pass

        self._thread = threading.Thread(
            target=_thread_main,
            name="universal_test_runner_loop",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=5)

    def run(self, coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
        if not self._loop:
            raise RuntimeError("Async loop thread failed to initialize.")
        fut = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
        return fut.result()

    def close(self) -> None:
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)


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
            lemma = getattr(entry, "lemma", None)
            return _clean_cell(lemma) or None
        except Exception:
            return None


# -----------------------------------------------------------------------------
# Renderer (GF Engine Adapter)
# -----------------------------------------------------------------------------
class _Renderer:
    """
    Wraps the v2.1 GFGrammarEngine for the test runner.

    Proper fix:
    - GFGrammarEngine is lazy-loaded; checking engine.grammar on init is wrong.
    - We call engine.health_check() once via a background loop to force loading.
    - Provide actionable diagnostics if loading fails.
    """

    def __init__(self) -> None:
        self._engine = None
        self._loop = _AsyncLoopThread()
        self._ready: bool = False
        self._supported_languages: List[str] = []
        self._diag: Dict[str, Any] = {}

        try:
            from app.adapters.engines.gf_wrapper import GFGrammarEngine
            import app.adapters.engines.gf_wrapper as gf_mod  # to inspect pgf import status

            self._engine = GFGrammarEngine()

            # Force lazy-load now (this is the key “proper” fix).
            self._ready = bool(self._loop.run(lambda: self._engine.health_check()))  # type: ignore[union-attr]

            if self._ready:
                self._supported_languages = list(
                    self._loop.run(lambda: self._engine.get_supported_languages())  # type: ignore[union-attr]
                )
            else:
                pgf_path = getattr(self._engine, "pgf_path", None)
                pgf_exists = bool(pgf_path and Path(str(pgf_path)).exists())
                pgf_bindings_ok = getattr(gf_mod, "pgf", None) is not None

                self._diag = {
                    "pgf_path": str(pgf_path) if pgf_path else None,
                    "pgf_exists": pgf_exists,
                    "pgf_bindings_importable": pgf_bindings_ok,
                    "cwd": os.getcwd(),
                    "project_root": str(PROJECT_ROOT) if PROJECT_ROOT else None,
                }

        except Exception as e:
            self._engine = None
            self._ready = False
            self._diag = {
                "error": str(e),
                "cwd": os.getcwd(),
                "project_root": str(PROJECT_ROOT) if PROJECT_ROOT else None,
            }

    def close(self) -> None:
        self._loop.close()

    def available(self) -> bool:
        return self._engine is not None and self._ready is True

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "ready": self._ready,
            "supported_languages_count": len(self._supported_languages),
            "supported_languages_sample": self._supported_languages[:10],
            **(self._diag or {}),
        }

    def render_bio(self, *, name: str, gender: str, profession: str, nationality: str, lang_code: str) -> str:
        if not self.available():
            diag = self.diagnostics()
            raise RuntimeError(
                "Grammar Engine not available.\n"
                f"Diagnostics: {json.dumps(diag, ensure_ascii=False)}\n"
                "Fix checklist:\n"
                "- Ensure the 'pgf' Python bindings are installed in the tool runner environment.\n"
                "- Ensure semantik_architect.pgf exists at the configured PGF path.\n"
                "- Ensure the PGF contains the target language (e.g., WikiEng / WikiIta etc.)."
            )

        from app.core.domain.frame import BioFrame

        frame = BioFrame(
            frame_type="bio",
            subject={
                "name": name,
                "gender": gender,
                "profession": profession,
                "nationality": nationality,
            },
        )

        try:
            sentence = self._loop.run(lambda: self._engine.generate(lang_code, frame))  # type: ignore[union-attr]
            return str(sentence.text)
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
    THIS_DIR / "generated_datasets",
    (PROJECT_ROOT / "qa_tools" / "generated_datasets") if PROJECT_ROOT else None,
    (PROJECT_ROOT / "tools" / "qa" / "generated_datasets") if PROJECT_ROOT else None,
    (PROJECT_ROOT / "generated_datasets") if PROJECT_ROOT else None,
]


def _resolve_dataset_dir(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.getenv("SKA_TEST_DATASET_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    for c in DEFAULT_DATASET_DIR_CANDIDATES:
        if c and c.exists() and c.is_dir():
            return c
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
) -> Tuple[str, str, str, str, str, str, str]:
    test_id_col = _first_present(fieldnames, TEST_ID_COLUMN_CANDIDATES)
    frame_col = _first_present(fieldnames, FRAME_COLUMN_CANDIDATES)
    name_col = _first_present(fieldnames, NAME_COLUMN_CANDIDATES)
    gender_col = _first_present(fieldnames, GENDER_COLUMN_CANDIDATES)
    expected_col = _first_present(fieldnames, EXPECTED_COLUMN_CANDIDATES)

    prof_lemma_col = _first_prefixed(fieldnames, PROF_LEMMA_PREFIXES)
    nat_lemma_col = _first_prefixed(fieldnames, NAT_LEMMA_PREFIXES)

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


def _write_failures_report(path: Path, results: List[CaseResult], summary: RunSummary) -> None:
    fails = [r for r in results if r.status in {"FAIL", "CRASH"}]
    lines: List[str] = []
    lines.append("UNIVERSAL TEST RUNNER - FAILURES REPORT")
    lines.append(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(summary.finished_at))}")
    lines.append(f"Failed: {summary.failed} | Crashed: {summary.crashed} | Total cases: {summary.total}")
    lines.append("")

    if not fails:
        lines.append("(No failures/crashes)")
    else:
        for r in fails:
            lines.append(f"[{r.status}] {r.file} :: {r.test_id} (lang={r.lang}, frame={r.frame_type})")
            if r.detail:
                lines.append(f"  Detail:   {r.detail}")
            if r.expected:
                lines.append(f"  Expected: {r.expected}")
            if r.actual:
                lines.append(f"  Actual:   {r.actual}")
            lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_universal_tests(
    *,
    dataset_dir: Path,
    pattern: str,
    lang_filter: Optional[List[str]],
    limit_per_file: Optional[int],
    fail_fast: bool,
    strict: bool,
    max_failures_to_print: int,
    failures_report_path: Optional[Path],
    json_report_path: Optional[Path],
    verbose: bool,
    diagnose_only: bool,
    list_languages: bool,
) -> int:
    if hasattr(logger, "header"):
        try:
            logger.header("Universal Test Runner")  # type: ignore[attr-defined]
        except Exception:
            pass
    else:
        _log_info("========================================")
        _log_info("   UNIVERSAL TEST RUNNER (Enterprise)   ")
        _log_info("========================================")

    _log_info(f"Dataset dir: {dataset_dir}")
    _log_info(f"Pattern:     {pattern}")
    if lang_filter:
        _log_info(f"Lang filter: {', '.join(lang_filter)}")

    renderer = _Renderer()
    try:
        if list_languages or diagnose_only:
            diag = renderer.diagnostics()
            _log_info("")
            _log_info("---- ENGINE DIAGNOSTICS ----")
            _log_info(json.dumps(diag, ensure_ascii=False, indent=2))
            if list_languages:
                _log_info("")
                _log_info("---- SUPPORTED LANGUAGES (sample) ----")
                for x in diag.get("supported_languages_sample", []):
                    _log_info(f"- {x}")
            return 0 if renderer.available() else 2

        if not dataset_dir.exists():
            _log_error(f"Test directory not found: {dataset_dir}")
            _log_info("Hint: Run tools/qa/test_suite_generator.py first, or set SKA_TEST_DATASET_DIR.")
            return 2

        csv_files = _iter_csv_files(dataset_dir, pattern)
        if not csv_files:
            _log_error("No CSV files found.")
            _log_info("Hint: Run tools/qa/test_suite_generator.py first.")
            return 2

        if not renderer.available():
            _log_error("Grammar Engine not available.")
            _log_info(f"Diagnostics: {json.dumps(renderer.diagnostics(), ensure_ascii=False)}")
            _log_info("Hint: Check if semantik_architect.pgf exists in 'gf/' and 'pgf' library is installed.")
            return 2

        lexicon = _LexiconResolver()
        if verbose:
            _log_info(f"Lexicon resolver: {'ON' if lexicon.available() else 'OFF'}")

        started = time.time()
        results: List[CaseResult] = []

        total_passed = total_failed = total_skipped = total_crashed = 0
        total_active = 0

        for fpath in csv_files:
            lang = _infer_lang_from_filename(fpath.name) or "unknown"
            if lang_filter and lang.lower() not in {x.lower() for x in lang_filter}:
                continue

            _log_info("")
            _log_info("----------------------------------------")
            _log_info(f"Suite: {fpath.name}  [lang={lang}]")
            _log_info("----------------------------------------")

            file_pass = file_fail = file_skip = file_crash = 0

            with fpath.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames:
                    _log_error("CSV has no headers.")
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

                        if not name or not profession or not nationality:
                            msg = (
                                f"Missing inputs (name={bool(name)}, profession={bool(profession)}, "
                                f"nationality={bool(nationality)})"
                            )
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
                                _log_error(f"FAIL {test_id}")
                                _log_info(f"  Input:    {name} ({gender}) | {profession} | {nationality}")
                                _log_info(f"  Expected: {expected}")
                                _log_info(f"  Actual:   {actual}")

                            if fail_fast:
                                raise RuntimeError("Fail-fast: first mismatch encountered.")

                    except Exception as e:
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
                        _log_error(f"CRASH: {str(e)}")
                        if fail_fast:
                            break

            denom = file_pass + file_fail
            if denom > 0:
                rate = (file_pass / denom) * 100.0
                _log_info(
                    f"Result: {file_pass} passed, {file_fail} failed, {file_skip} skipped, {file_crash} crashed  ({rate:.1f}% pass)"
                )
            else:
                _log_info(f"Result: {file_pass} passed, {file_fail} failed, {file_skip} skipped, {file_crash} crashed")

            if fail_fast and (file_fail > 0 or file_crash > 0):
                break

        finished = time.time()
        duration = finished - started

        _log_info("")
        _log_info("========================================")
        _log_info(f"RUN COMPLETE in {duration:.2f}s")
        _log_info("========================================")
        _log_info(f"Passed:  {total_passed}")
        _log_info(f"Failed:  {total_failed}")
        _log_info(f"Skipped: {total_skipped}")
        _log_info(f"Crashed: {total_crashed}")
        _log_info(f"Active:  {total_active}")

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
            _log_info(f"\nWrote JSON report: {json_report_path}")

        if failures_report_path:
            _write_failures_report(failures_report_path, results, summary)
            _log_info(f"Wrote failures report: {failures_report_path}")

        exit_code = 0
        if total_failed > 0 or total_crashed > 0:
            exit_code = 1
        if total_active == 0:
            exit_code = 2

        summary_msg = f"Passed: {total_passed}, Failed: {total_failed}, Crashed: {total_crashed}."
        if hasattr(logger, "finish"):
            try:
                logger.finish(message=summary_msg, success=(exit_code == 0), details=asdict(summary))  # type: ignore[attr-defined]
            except Exception:
                pass

        return exit_code

    finally:
        renderer.close()


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Universal CSV Test Runner (Enterprise)")
    p.add_argument("--dataset-dir", default=None, help="Directory containing CSV suites.")
    p.add_argument("--pattern", default="test_suite_*.csv", help="Glob pattern for CSV files.")
    p.add_argument(
        "--langs",
        nargs="*",
        default=None,
        help="Language filter (e.g., --langs en fr OR --langs en,fr,it).",
    )
    p.add_argument("--limit", type=int, default=None, help="Max rows per file.")
    p.add_argument("--fail-fast", action="store_true", help="Stop on first FAIL/CRASH.")
    p.add_argument("--strict", action="store_true", help="Treat missing EXPECTED or inputs as FAIL (not SKIP).")

    # GUI expects this to accept a value; support both int and path
    p.add_argument(
        "--print-failures",
        default="10",
        help="Either N (print first N failures per file; 0=none) OR a file path to write all FAIL/CRASH cases.",
    )

    p.add_argument("--json-report", default=None, help="Write a JSON report to this path.")
    p.add_argument("--verbose", action="store_true", help="Verbose diagnostics.")

    # Demo-friendly + production-friendly diagnostics/overrides
    p.add_argument("--pgf", default=None, help="Override PGF path (file or directory). Sets PGF_PATH env for this run.")
    p.add_argument("--diagnose", action="store_true", help="Print engine diagnostics and exit (0 if ready, else 2).")
    p.add_argument("--list-languages", action="store_true", help="List supported languages (requires engine ready).")
    return p.parse_args(argv)


def _parse_lang_filter(langs_arg: Optional[List[str]]) -> Optional[List[str]]:
    if not langs_arg:
        return None
    out: List[str] = []
    for item in langs_arg:
        if not item:
            continue
        # allow "en,fr" or "en fr"
        parts = re.split(r"[,\s]+", str(item).strip())
        for p in parts:
            p = p.strip()
            if p:
                out.append(p)
    return out or None


def _parse_print_failures(value: str) -> Tuple[int, Optional[Path]]:
    v = (value or "").strip()
    if not v:
        return 10, None
    if re.fullmatch(r"\d+", v):
        return max(0, int(v)), None
    # treat as path
    return 0, Path(v).expanduser().resolve()


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(logger, "start"):
        try:
            logger.start("Universal Test Runner")  # type: ignore[attr-defined]
        except Exception:
            pass

    args = _parse_args(argv)

    # Apply PGF override before importing/initializing engine (settings reads env).
    if args.pgf:
        raw = str(args.pgf).strip()
        if raw:
            p = Path(raw).expanduser()
            # If a directory is provided, assume semantik_architect.pgf inside it.
            if p.exists() and p.is_dir():
                p = p / "semantik_architect.pgf"
            os.environ["PGF_PATH"] = str(p)

    dataset_dir = _resolve_dataset_dir(args.dataset_dir)
    lang_filter = _parse_lang_filter(args.langs)

    max_failures_to_print, failures_report_path = _parse_print_failures(str(args.print_failures))
    json_report_path = Path(args.json_report).expanduser().resolve() if args.json_report else None

    return run_universal_tests(
        dataset_dir=dataset_dir,
        pattern=args.pattern,
        lang_filter=lang_filter,
        limit_per_file=args.limit,
        fail_fast=bool(args.fail_fast),
        strict=bool(args.strict),
        max_failures_to_print=max_failures_to_print,
        failures_report_path=failures_report_path,
        json_report_path=json_report_path,
        verbose=bool(args.verbose),
        diagnose_only=bool(args.diagnose),
        list_languages=bool(args.list_languages),
    )


if __name__ == "__main__":
    raise SystemExit(main())