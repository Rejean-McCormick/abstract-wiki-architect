# app/adapters/api/routers/tools.py
from __future__ import annotations

import datetime
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.api.dependencies import verify_api_key
from app.shared.config import settings

# -----------------------------------------------------------------------------
# Enterprise-grade Tools Router
# - Strict allowlist registry (no arbitrary execution)
# - Runs from configured repo root (FILESYSTEM_REPO_PATH)
# - Optional arg allowlisting (prevents flag injection)
# - Output truncation + timeouts
# - Protected by API key
# - Rich Telemetry & Lifecycle Events
# -----------------------------------------------------------------------------

router = APIRouter(dependencies=[Depends(verify_api_key)])

PYTHON_EXE = sys.executable

REPO_ROOT = Path(settings.FILESYSTEM_REPO_PATH).resolve()
if not REPO_ROOT.exists():
    raise RuntimeError(f"FILESYSTEM_REPO_PATH does not exist: {REPO_ROOT}")

TOOL_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")

MAX_OUTPUT_CHARS = int(os.getenv("ARCHITECT_TOOLS_MAX_OUTPUT_CHARS", "200000"))
DEFAULT_TIMEOUT_SEC = int(os.getenv("ARCHITECT_TOOLS_DEFAULT_TIMEOUT_SEC", "600"))
AI_TOOLS_ENABLED = os.getenv("ARCHITECT_ENABLE_AI_TOOLS", "").strip().lower() in {"1", "true", "yes", "y"}


def _safe_join_cmd(parts: Sequence[str]) -> str:
    try:
        return shlex.join(list(parts))
    except Exception:
        return " ".join(shlex.quote(p) for p in parts)


def _resolve_repo_path(rel_path: str) -> Path:
    p = (REPO_ROOT / rel_path).resolve()
    # Ensure path stays inside repo root
    if p != REPO_ROOT and REPO_ROOT not in p.parents:
        raise HTTPException(status_code=400, detail="Invalid tool path (outside repo root).")
    return p


def _ensure_exists(p: Path, rel_path: str) -> None:
    if not p.exists():
        # 404 because the tool_id exists but the underlying file is missing.
        raise HTTPException(status_code=404, detail=f"Tool target missing on disk: {rel_path}")


def _truncate(text: str) -> Tuple[str, bool]:
    if text is None:
        return "", False
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    # Keep the head, discard the tail
    return text[:MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]", True


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    description: str
    rel_target: str
    cmd: Tuple[str, ...]  # supports "{target}" placeholder
    timeout_sec: int = DEFAULT_TIMEOUT_SEC
    allow_args: bool = False
    allowed_flags: Tuple[str, ...] = ()
    allow_positionals: bool = False
    requires_ai_enabled: bool = False

    # Arg-shape policy (so UI can pass "--flag value" safely)
    flags_with_value: Tuple[str, ...] = ()        # consumes exactly 1 value token
    flags_with_multi_value: Tuple[str, ...] = ()  # consumes 1+ value tokens until next flag


def _py_script(
    tool_id: str,
    rel_script: str,
    description: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
    allow_positionals: bool = False,
    requires_ai_enabled: bool = False,
    flags_with_value: Sequence[str] = (),
    flags_with_multi_value: Sequence[str] = (),
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        description=description,
        rel_target=rel_script,
        cmd=(PYTHON_EXE, "-u", "{target}"),
        timeout_sec=timeout_sec,
        allow_args=allow_args,
        allowed_flags=tuple(allowed_flags),
        allow_positionals=allow_positionals,
        requires_ai_enabled=requires_ai_enabled,
        flags_with_value=tuple(flags_with_value),
        flags_with_multi_value=tuple(flags_with_multi_value),
    )


def _pytest_file(
    tool_id: str,
    rel_test_file: str,
    description: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
    flags_with_value: Sequence[str] = (),
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        description=description,
        rel_target=rel_test_file,
        cmd=(PYTHON_EXE, "-u", "-m", "pytest", "{target}"),
        timeout_sec=timeout_sec,
        allow_args=allow_args,
        allowed_flags=tuple(allowed_flags),
        allow_positionals=False,
        requires_ai_enabled=False,
        flags_with_value=tuple(flags_with_value),
        flags_with_multi_value=(),
    )


# -----------------------------------------------------------------------------
# Allowlist Registry
# -----------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, ToolSpec] = {
    # --- MAINTENANCE ---
    "language_health": _py_script(
        "language_health",
        "tools/language_health.py",
        "Language health/diagnostics utility (status checks and reporting).",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=(
            "--mode",
            "--fast",
            "--parallel",
            "--api-url",
            "--api-key",
            "--timeout",
            "--langs",
            "--no-disable-script",
            "--verbose",
            "--json",
        ),
        allow_positionals=False,
        flags_with_value=("--mode", "--parallel", "--api-url", "--api-key", "--timeout"),
        flags_with_multi_value=("--langs",),
    ),
    # Legacy aliases (kept for backward compat with frontend/power users)
    "audit_languages": _py_script(
        "audit_languages",
        "tools/language_health.py",
        "Legacy alias for language_health.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=(
            "--mode",
            "--fast",
            "--parallel",
            "--api-url",
            "--api-key",
            "--timeout",
            "--langs",
            "--no-disable-script",
            "--verbose",
            "--json",
        ),
        allow_positionals=False,
        flags_with_value=("--mode", "--parallel", "--api-url", "--api-key", "--timeout"),
        flags_with_multi_value=("--langs",),
    ),
    "check_all_languages": _py_script(
        "check_all_languages",
        "tools/language_health.py",
        "Legacy alias for language_health.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=(
            "--mode",
            "--fast",
            "--parallel",
            "--api-url",
            "--api-key",
            "--timeout",
            "--langs",
            "--no-disable-script",
            "--verbose",
            "--json",
        ),
        allow_positionals=False,
        flags_with_value=("--mode", "--parallel", "--api-url", "--api-key", "--timeout"),
        flags_with_multi_value=("--langs",),
    ),
    "diagnostic_audit": _py_script(
        "diagnostic_audit",
        "tools/diagnostic_audit.py",
        "Forensics audit for stale artifacts / zombie outputs.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("--verbose", "--json"),
    ),
    "cleanup_root": _py_script(
        "cleanup_root",
        "tools/cleanup_root.py",
        "Cleans root artifacts and moves loose GF files into expected folders.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("--dry-run", "--verbose", "--json"),
    ),
    # --- HEALTH & DEBUGGING ---
    "profiler": _py_script(
        "profiler",
        "tools/health/profiler.py",
        "Benchmarks Grammar Engine performance (TPS, Latency, Memory).",
        timeout_sec=300,
        allow_args=True,
        allowed_flags=("--lang", "--iterations", "--update-baseline", "--threshold", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--lang", "--iterations", "--threshold"),
    ),
    "visualize_ast": _py_script(
        "visualize_ast",
        "tools/debug/visualize_ast.py",
        "Generates JSON Abstract Syntax Tree from sentence or intent.",
        timeout_sec=60,
        allow_args=True,
        allowed_flags=("--lang", "--sentence", "--ast", "--pgf"),
        allow_positionals=False,
        flags_with_value=("--lang", "--sentence", "--ast", "--pgf"),
    ),
    # --- BUILD ---
    "build_index": _py_script(
        "build_index",
        "tools/everything_matrix/build_index.py",
        "Rebuilds everything_matrix.json by scanning repo (languages, lexicon, QA).",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=(
            "--out",
            "--verbose",
            "--langs",
            "--force",
            "--regen-rgl",
            "--regen-lex",
            "--regen-app",
            "--regen-qa",
        ),
        allow_positionals=False,
        flags_with_value=("--out",),
        flags_with_multi_value=("--langs",),
    ),
    "app_scanner": _py_script(
        "app_scanner",
        "tools/everything_matrix/app_scanner.py",
        "Scans app/frontend/backend surfaces for language support signals.",
        timeout_sec=600,
    ),
    "lexicon_scanner": _py_script(
        "lexicon_scanner",
        "tools/everything_matrix/lexicon_scanner.py",
        "Scores lexicon maturity by scanning shard coverage.",
        timeout_sec=600,
    ),
    "qa_scanner": _py_script(
        "qa_scanner",
        "tools/everything_matrix/qa_scanner.py",
        "Parses QA output/logs to update quality scoring.",
        timeout_sec=600,
    ),
    "rgl_scanner": _py_script(
        "rgl_scanner",
        "tools/everything_matrix/rgl_scanner.py",
        "Audits RGL grammar module presence/consistency.",
        timeout_sec=600,
    ),
    "compile_pgf": _py_script(
        "compile_pgf",
        "builder/orchestrator.py",
        "Two-phase GF build orchestrator to produce AbstractWiki.pgf.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--strategy", "--langs", "--clean", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--strategy",),
        flags_with_multi_value=("--langs",),
    ),
    "bootstrap_tier1": _py_script(
        "bootstrap_tier1",
        "tools/bootstrap_tier1.py",
        "Bootstraps Tier 1 languages/wrappers.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--force", "--dry-run", "--verbose"),
        allow_positionals=False,
        flags_with_multi_value=("--langs",),
    ),
    # --- DATA REFINERY ---
    "gap_filler": _py_script(
        "gap_filler",
        "tools/lexicon/gap_filler.py",
        "Identifies missing vocabulary by comparing Target vs Pivot language.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("--target", "--pivot", "--data-dir", "--json-out", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--target", "--pivot", "--data-dir", "--json-out"),
    ),
    "harvest_lexicon": _py_script(
        "harvest_lexicon",
        "tools/harvest_lexicon.py",
        "Universal Lexicon Harvester. Subcommands: `wordnet` and `wikidata` (positional).",
        timeout_sec=1800,
        allow_args=True,
        # NOTE: tools/harvest_lexicon.py uses positional subcommands:
        #   wordnet --root <path> --lang <iso2> [--out <dir>]
        #   wikidata --lang <iso2> --input <qids.json> [--domain <shard>]
        allowed_flags=(
            "--root",
            "--lang",
            "--out",
            "--input",
            "--domain",
        ),
        allow_positionals=True,  # expects "wordnet" or "wikidata"
        flags_with_value=("--root", "--lang", "--out", "--input", "--domain"),
        flags_with_multi_value=(),
    ),
    "build_lexicon_wikidata": _py_script(
        "build_lexicon_wikidata",
        "tools/build_lexicon_from_wikidata.py",
        "Builds lexicon shards directly from Wikidata (online).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--lang", "--out", "--limit", "--dry-run", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--lang", "--out", "--limit"),
    ),
    "refresh_index": _py_script(
        "refresh_index",
        "utils/refresh_lexicon_index.py",
        "Rebuilds the fast lexicon lookup index used by API.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("--langs", "--root", "--out", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--root", "--out"),
        flags_with_multi_value=("--langs",),
    ),
    "migrate_schema": _py_script(
        "migrate_schema",
        "utils/migrate_lexicon_schema.py",
        "Migrates lexicon JSON shards to newer schema versions.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--root", "--in-place", "--dry-run", "--from", "--to", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--root", "--from", "--to"),
    ),
    "dump_stats": _py_script(
        "dump_stats",
        "utils/dump_lexicon_stats.py",
        "Prints lexicon coverage/size statistics.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("--langs", "--root", "--format", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--root", "--format"),
        flags_with_multi_value=("--langs",),
    ),
    # --- QA & TESTING ---
    "ambiguity_detector": _py_script(
        "ambiguity_detector",
        "tools/qa/ambiguity_detector.py",
        "Uses AI to generate ambiguous sentences and checks for multiple parse trees.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--lang", "--sentence", "--topic", "--json-out", "--verbose"),
        allow_positionals=False,
        requires_ai_enabled=True,
        flags_with_value=("--lang", "--sentence", "--topic", "--json-out"),
    ),
    "run_smoke_tests": _pytest_file(
        "run_smoke_tests",
        "tests/test_lexicon_smoke.py",
        "Lexicon schema/syntax smoke tests.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
        flags_with_value=("-k", "-m", "--maxfail"),
    ),
    "run_judge": _pytest_file(
        "run_judge",
        "tests/integration/test_quality.py",
        "Executes Golden Standard regression checks (AI Judge integration).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
        flags_with_value=("-k", "-m", "--maxfail"),
    ),
    "eval_bios": _py_script(
        "eval_bios",
        "tools/qa/eval_bios.py",
        "Compares generated biographies against Wikidata facts.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--limit", "--out", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--limit", "--out"),
        flags_with_multi_value=("--langs",),
    ),
    "lexicon_coverage": _py_script(
        "lexicon_coverage",
        "tools/qa/lexicon_coverage_report.py",
        "Coverage report for intended vs implemented lexicon.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--format", "--verbose", "--fail-on-errors"),
        allow_positionals=False,
        flags_with_value=("--out", "--format"),
        flags_with_multi_value=("--langs",),
    ),
    "universal_test_runner": _py_script(
        "universal_test_runner",
        "tools/qa/universal_test_runner.py",
        "Advanced CSV test runner (supports more complex constructions).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--suite", "--in", "--out", "--langs", "--limit", "--verbose", "--fail-fast", "--strict"),
        allow_positionals=False,
        flags_with_value=("--suite", "--in", "--out", "--limit"),
        flags_with_multi_value=("--langs",),
    ),
    # Legacy alias for frontend registry
    "test_runner": _py_script(
        "test_runner",
        "tools/qa/universal_test_runner.py",
        "Legacy alias for universal_test_runner.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--suite", "--in", "--out", "--langs", "--limit", "--verbose", "--fail-fast", "--strict"),
        allow_positionals=False,
        flags_with_value=("--suite", "--in", "--out", "--limit"),
        flags_with_multi_value=("--langs",),
    ),
    "batch_test_generator": _py_script(
        "batch_test_generator",
        "tools/qa/batch_test_generator.py",
        "Bulk generation of test datasets for regression.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--limit", "--seed", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--out", "--limit", "--seed"),
        flags_with_multi_value=("--langs",),
    ),
    "test_suite_generator": _py_script(
        "test_suite_generator",
        "tools/qa/test_suite_generator.py",
        "Generates empty CSV templates for manual/AI fill-in.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--verbose"),
        allow_positionals=False,
        flags_with_value=("--out",),
        flags_with_multi_value=("--langs",),
    ),
    "generate_lexicon_regression_tests": _py_script(
        "generate_lexicon_regression_tests",
        "tools/qa/generate_lexicon_regression_tests.py",
        "Builds regression tests from lexicon for CI/QA.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--limit", "--verbose", "--lexicon-dir"),
        allow_positionals=False,
        flags_with_value=("--out", "--limit", "--lexicon-dir"),
        flags_with_multi_value=("--langs",),
    ),
    # --- AI SERVICES (gated) ---
    "seed_lexicon": _py_script(
        "seed_lexicon",
        "utils/seed_lexicon_ai.py",
        "Uses LLM to generate core vocabulary for new languages.",
        timeout_sec=3600,
        allow_args=True,
        allowed_flags=("--langs", "--limit", "--dry-run", "--verbose"),
        allow_positionals=False,
        requires_ai_enabled=True,
        flags_with_value=("--limit",),
        flags_with_multi_value=("--langs",),
    ),
    "ai_refiner": _py_script(
        "ai_refiner",
        "tools/ai_refiner.py",
        "Attempts to upgrade Pidgin grammars to full RGL.",
        timeout_sec=3600,
        allow_args=True,
        allowed_flags=("--langs", "--dry-run", "--verbose"),
        allow_positionals=True,
        requires_ai_enabled=True,
        flags_with_multi_value=("--langs",),
    ),
    # --- TESTS (Inventory) ---
    "test_api_smoke": _pytest_file(
        "test_api_smoke",
        "tests/test_api_smoke.py",
        "API smoke tests (fast signal).",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
        flags_with_value=("-k", "-m", "--maxfail"),
    ),
    "test_gf_dynamic": _pytest_file(
        "test_gf_dynamic",
        "tests/test_gf_dynamic.py",
        "Validates dynamic loading/linearization of GF grammars.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
        flags_with_value=("-k", "-m", "--maxfail"),
    ),
    "test_multilingual_generation": _pytest_file(
        "test_multilingual_generation",
        "tests/test_multilingual_generation.py",
        "Multilingual generation regression tests.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
        flags_with_value=("-k", "-m", "--maxfail"),
    ),
}

# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------
try:
    from pydantic import ConfigDict as _PydConfigDict  # type: ignore
except Exception:  # pragma: no cover
    _PydConfigDict = None  # type: ignore


class ToolRunRequest(BaseModel):
    tool_id: str = Field(..., description="Allowlisted tool identifier.")
    args: List[str] = Field(default_factory=list, description="Optional argv-style args for the tool.")
    dry_run: bool = Field(False, description="If true, returns the command without executing.")

    if _PydConfigDict is not None:
        model_config: ClassVar[_PydConfigDict] = _PydConfigDict(extra="ignore")  # type: ignore
    else:
        class Config:  # type: ignore
            extra = "ignore"


class ToolSummary(BaseModel):
    id: str
    label: str  # maps from ToolSpec.tool_id for now, or human-readable mapping
    description: str
    timeout_sec: int


class ToolRunEvent(BaseModel):
    ts: str
    level: str  # INFO, WARN, ERROR
    step: str
    message: str
    data: Optional[Dict[str, Any]] = None


class ToolRunTruncation(BaseModel):
    stdout: bool
    stderr: bool
    limit_chars: int


class ToolRunArgsRejected(BaseModel):
    arg: str
    reason: str


class ToolRunResponse(BaseModel):
    trace_id: str
    success: bool
    command: str
    # Streams
    output: str  # Back-compat alias for stdout
    error: str   # Back-compat alias for stderr
    stdout: str
    stderr: str
    stdout_chars: int
    stderr_chars: int
    # Lifecycle
    exit_code: int
    duration_ms: int
    started_at: str
    ended_at: str
    # Metadata
    cwd: str
    repo_root: str
    tool: ToolSummary
    # Arguments
    args_received: List[str]
    args_accepted: List[str]
    args_rejected: List[ToolRunArgsRejected]
    # Telemetry
    truncation: ToolRunTruncation
    events: List[ToolRunEvent]


class ToolMeta(BaseModel):
    tool_id: str
    description: str
    timeout_sec: int
    allow_args: bool
    requires_ai_enabled: bool
    available: bool


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _iso_now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _emit_event(
    events: List[ToolRunEvent],
    level: str,
    step: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    events.append(
        ToolRunEvent(ts=_iso_now(), level=level, step=step, message=message, data=data)
    )


def _validate_tool_id(tool_id: str) -> None:
    if not TOOL_ID_RE.match(tool_id):
        raise HTTPException(status_code=400, detail="Invalid tool_id format.")


def _model_dump(m: BaseModel) -> Dict[str, Any]:
    # pydantic v2: model_dump(); v1: dict()
    if hasattr(m, "model_dump"):
        return getattr(m, "model_dump")()  # type: ignore[no-any-return]
    return m.dict()  # type: ignore[no-any-return]


def _tool_summary_from_spec(spec: Optional[ToolSpec], tool_id: str) -> ToolSummary:
    if spec is None:
        return ToolSummary(id=tool_id, label=tool_id, description="", timeout_sec=0)
    return ToolSummary(
        id=spec.tool_id,
        label=spec.tool_id,
        description=spec.description,
        timeout_sec=spec.timeout_sec,
    )


def _error_envelope(
    *,
    http_status: int,
    trace_id: str,
    started_at: str,
    ended_at: str,
    tool_id: str,
    spec: Optional[ToolSpec],
    command: str,
    message: str,
    events: List[ToolRunEvent],
    args_received: List[str],
    args_accepted: List[str],
    args_rejected: List[ToolRunArgsRejected],
) -> JSONResponse:
    # Keep ToolRunResponse shape so frontend never gets {detail: "..."}.
    res = ToolRunResponse(
        trace_id=trace_id,
        success=False,
        command=command,
        output="",
        error=message,
        stdout="",
        stderr=message,
        stdout_chars=0,
        stderr_chars=len(message or ""),
        exit_code=1,
        duration_ms=0,
        started_at=started_at,
        ended_at=ended_at,
        cwd=str(REPO_ROOT),
        repo_root=str(REPO_ROOT),
        tool=_tool_summary_from_spec(spec, tool_id),
        args_received=args_received,
        args_accepted=args_accepted,
        args_rejected=args_rejected,
        truncation=ToolRunTruncation(stdout=False, stderr=False, limit_chars=MAX_OUTPUT_CHARS),
        events=events,
    )
    return JSONResponse(status_code=http_status, content=_model_dump(res))


def _validate_args(spec: ToolSpec, args: Sequence[str]) -> Tuple[List[str], List[ToolRunArgsRejected]]:
    """
    Validate args against tool spec.
    Returns (accepted_args, rejected_args_list).

    Supports:
      - --flag=value
      - --flag value
      - --langs en fr (multi-value flags)
    """
    if not args:
        return [], []

    accepted: List[str] = []
    rejected: List[ToolRunArgsRejected] = []

    # 1. Global format checks (Security)
    for a in args:
        if not isinstance(a, str):
            raise HTTPException(status_code=400, detail="All args must be strings.")
        if "\x00" in a or "\n" in a or "\r" in a:
            raise HTTPException(status_code=400, detail="Invalid characters in args.")
        if len(a) > 512:
            raise HTTPException(status_code=400, detail="Arg too long.")

    # 2. Spec checks
    if not spec.allow_args:
        for a in args:
            rejected.append(ToolRunArgsRejected(arg=a, reason="Tool does not accept arguments."))
        return [], rejected

    allowed = set(spec.allowed_flags) if spec.allowed_flags else set()
    flags_with_value = set(spec.flags_with_value or ())
    flags_with_multi = set(spec.flags_with_multi_value or ())

    i = 0
    n = len(args)
    while i < n:
        a = args[i]

        if a.startswith("-"):
            flag = a.split("=", 1)[0]

            if allowed and flag not in allowed:
                rejected.append(ToolRunArgsRejected(arg=a, reason=f"Flag '{flag}' not in allowed_flags."))
                i += 1
                continue

            accepted.append(a)

            # If it's --flag=value, we're done.
            if "=" in a:
                i += 1
                continue

            # Multi-value flag: consume 1+ non-flag tokens.
            if flag in flags_with_multi:
                j = i + 1
                consumed_any = False
                while j < n and not args[j].startswith("-"):
                    accepted.append(args[j])
                    consumed_any = True
                    j += 1
                if not consumed_any:
                    rejected.append(ToolRunArgsRejected(arg=flag, reason="Flag requires one or more values."))
                i = j
                continue

            # Single-value flag: consume exactly 1 non-flag token.
            if flag in flags_with_value:
                if i + 1 < n and not args[i + 1].startswith("-"):
                    accepted.append(args[i + 1])
                    i += 2
                else:
                    rejected.append(ToolRunArgsRejected(arg=flag, reason="Flag requires a value."))
                    i += 1
                continue

            # Boolean / no-value flag
            i += 1
            continue

        # Positional
        if not spec.allow_positionals:
            rejected.append(ToolRunArgsRejected(arg=a, reason="Positional arguments not allowed."))
        else:
            accepted.append(a)
        i += 1

    return accepted, rejected


def _render_cmd(spec: ToolSpec) -> List[str]:
    target_path = _resolve_repo_path(spec.rel_target)
    _ensure_exists(target_path, spec.rel_target)
    return [part.format(target=str(target_path)) for part in spec.cmd]


# app/adapters/api/routers/tools.py

def _run_process_extended(
    cmd: Sequence[str],
    timeout_sec: int,
    env_updates: Dict[str, str],
) -> Tuple[int, str, str, int]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(env_updates)

    started = time.time()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",      # <--- FIX 1: Support Emojis
            errors="replace",      # <--- FIX 2: Prevent Crashes
            timeout=timeout_sec,
            check=False,
        )
        duration_ms = int((time.time() - started) * 1000)
        return proc.returncode, proc.stdout or "", proc.stderr or "", duration_ms
    except Exception as e:
        # <--- FIX 3: Catch OS errors so the frontend gets a real error message
        duration_ms = int((time.time() - started) * 1000)
        return 127, "", f"CRITICAL RUNNER ERROR: {str(e)}", duration_ms

    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - started) * 1000)
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
        stderr += f"\nProcess timed out (limit: {timeout_sec}s)."
        return 124, stdout, stderr, duration_ms

    except Exception as e:
        # [FIX] Catch-all for OS errors (permissions, missing file, etc.)
        duration_ms = int((time.time() - started) * 1000)
        # Return 127 (Command Not Found standard) or 1 for generic error
        error_msg = f"CRITICAL RUNNER ERROR: {str(e)}\n"
        return 127, "", error_msg, duration_ms


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.get("/registry", response_model=List[ToolMeta])
async def list_tools() -> List[ToolMeta]:
    metas: List[ToolMeta] = []
    for spec in sorted(TOOL_REGISTRY.values(), key=lambda s: s.tool_id):
        try:
            available = _resolve_repo_path(spec.rel_target).exists()
        except Exception:
            available = False

        metas.append(
            ToolMeta(
                tool_id=spec.tool_id,
                description=spec.description,
                timeout_sec=spec.timeout_sec,
                allow_args=spec.allow_args,
                requires_ai_enabled=spec.requires_ai_enabled,
                available=available,
            )
        )
    return metas


@router.post("/run", response_model=ToolRunResponse)
async def run_tool(payload: ToolRunRequest) -> ToolRunResponse:
    trace_id = str(uuid.uuid4())
    start_time = _iso_now()
    events: List[ToolRunEvent] = []

    _emit_event(events, "INFO", "request_received", "Tool run request received", {"tool_id": payload.tool_id})

    # 1) Validate tool_id format (return envelope, not FastAPI {detail})
    try:
        _validate_tool_id(payload.tool_id)
    except HTTPException as e:
        _emit_event(events, "ERROR", "tool_validated", f"Invalid tool ID: {e.detail}")
        return _error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=start_time,
            ended_at=_iso_now(),
            tool_id=payload.tool_id,
            spec=None,
            command="",
            message=str(e.detail),
            events=events,
            args_received=payload.args or [],
            args_accepted=[],
            args_rejected=[],
        )

    spec = TOOL_REGISTRY.get(payload.tool_id)
    if not spec:
        _emit_event(events, "ERROR", "tool_validated", f"Tool '{payload.tool_id}' not found in registry.")
        return _error_envelope(
            http_status=404,
            trace_id=trace_id,
            started_at=start_time,
            ended_at=_iso_now(),
            tool_id=payload.tool_id,
            spec=None,
            command="",
            message=f"Tool '{payload.tool_id}' not found in registry.",
            events=events,
            args_received=payload.args or [],
            args_accepted=[],
            args_rejected=[],
        )

    _emit_event(events, "INFO", "tool_validated", "Tool found in registry", {"description": spec.description})

    # 2) AI gating (return envelope)
    if spec.requires_ai_enabled and not AI_TOOLS_ENABLED:
        msg = "AI tools are disabled. Set ARCHITECT_ENABLE_AI_TOOLS=1 to enable."
        _emit_event(events, "ERROR", "tool_check", msg)
        return _error_envelope(
            http_status=403,
            trace_id=trace_id,
            started_at=start_time,
            ended_at=_iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=msg,
            events=events,
            args_received=payload.args or [],
            args_accepted=[],
            args_rejected=[],
        )

    # 3) Validate arguments
    try:
        args_accepted, args_rejected = _validate_args(spec, payload.args or [])
    except HTTPException as e:
        _emit_event(events, "ERROR", "args_validated", f"Argument validation error: {e.detail}")
        return _error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=start_time,
            ended_at=_iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=str(e.detail),
            events=events,
            args_received=payload.args or [],
            args_accepted=[],
            args_rejected=[],
        )

    if args_rejected:
        _emit_event(
            events,
            "WARN",
            "args_validated",
            "Some arguments were rejected.",
            {"accepted_count": len(args_accepted), "rejected_count": len(args_rejected)},
        )
    else:
        _emit_event(events, "INFO", "args_validated", f"All {len(args_accepted)} arguments accepted.")

    # 4) Prepare command (return envelope on failures)
    try:
        base_cmd = _render_cmd(spec)
    except HTTPException as e:
        _emit_event(events, "ERROR", "cmd_prepared", f"Command preparation failed: {e.detail}")
        return _error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=start_time,
            ended_at=_iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=str(e.detail),
            events=events,
            args_received=payload.args or [],
            args_accepted=args_accepted,
            args_rejected=args_rejected,
        )

    final_cmd_list = list(base_cmd) + args_accepted
    final_cmd_str = _safe_join_cmd(final_cmd_list)

    if payload.dry_run:
        _emit_event(events, "INFO", "dry_run", "Returning dry-run response.")
        return ToolRunResponse(
            trace_id=trace_id,
            success=True,
            command=final_cmd_str,
            output="",
            error="",
            stdout="",
            stderr="",
            stdout_chars=0,
            stderr_chars=0,
            exit_code=0,
            duration_ms=0,
            started_at=start_time,
            ended_at=_iso_now(),
            cwd=str(REPO_ROOT),
            repo_root=str(REPO_ROOT),
            tool=_tool_summary_from_spec(spec, payload.tool_id),
            args_received=payload.args or [],
            args_accepted=args_accepted,
            args_rejected=args_rejected,
            truncation=ToolRunTruncation(stdout=False, stderr=False, limit_chars=MAX_OUTPUT_CHARS),
            events=events,
        )

    # 5) Execution
    _emit_event(events, "INFO", "process_spawned", f"Executing command with timeout {spec.timeout_sec}s")

    env_vars = {"TOOL_TRACE_ID": trace_id}
    exit_code, stdout, stderr, duration_ms = _run_process_extended(final_cmd_list, spec.timeout_sec, env_vars)

    ended_at = _iso_now()
    _emit_event(events, "INFO", "process_exited", f"Process exited with code {exit_code}", {"duration_ms": duration_ms})

    # 6) Truncation
    out_trunc, out_was_trunc = _truncate(stdout)
    err_trunc, err_was_trunc = _truncate(stderr)

    if out_was_trunc:
        _emit_event(events, "WARN", "output_truncated", "Stdout exceeded limit and was truncated.")
    if err_was_trunc:
        _emit_event(events, "WARN", "output_truncated", "Stderr exceeded limit and was truncated.")

    # 7) Construct response
    return ToolRunResponse(
        trace_id=trace_id,
        success=(exit_code == 0),
        command=final_cmd_str,
        # Back-compat fields
        output=out_trunc,
        error=err_trunc,
        # Precise fields
        stdout=out_trunc,
        stderr=err_trunc,
        stdout_chars=len(stdout),
        stderr_chars=len(stderr),
        exit_code=exit_code,
        duration_ms=duration_ms,
        started_at=start_time,
        ended_at=ended_at,
        cwd=str(REPO_ROOT),
        repo_root=str(REPO_ROOT),
        tool=_tool_summary_from_spec(spec, payload.tool_id),
        args_received=payload.args or [],
        args_accepted=args_accepted,
        args_rejected=args_rejected,
        truncation=ToolRunTruncation(stdout=out_was_trunc, stderr=err_was_trunc, limit_chars=MAX_OUTPUT_CHARS),
        events=events,
    )
