# app/adapters/api/routers/tools.py
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, List, Sequence, Tuple

from fastapi import APIRouter, Depends, HTTPException
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
#
# Notes:
# - Avoid import-time crashes if tool files move/delete: existence is checked at
#   request time (registry/run), not at module import.
# - Legacy tool IDs are kept as aliases to newer scripts to avoid breaking older
#   clients.
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
    )


def _pytest_file(
    tool_id: str,
    rel_test_file: str,
    description: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
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
    )


# -----------------------------------------------------------------------------
# Allowlist Registry (Frontend tool_id -> executable command)
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
        ),
        allow_positionals=False,
    ),
    # Legacy aliases -> language_health.py
    "audit_languages": _py_script(
        "audit_languages",
        "tools/language_health.py",
        "Legacy alias: audits languages (use --mode compile|api|both).",
        timeout_sec=900,
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
        ),
        allow_positionals=False,
    ),
    "check_all_languages": _py_script(
        "check_all_languages",
        "tools/language_health.py",
        "Legacy alias: checks languages (use --mode api|both).",
        timeout_sec=900,
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
        ),
        allow_positionals=False,
    ),
    "diagnostic_audit": _py_script(
        "diagnostic_audit",
        "tools/diagnostic_audit.py",
        "Forensics audit for stale artifacts / zombie outputs.",
        timeout_sec=600,
    ),
    "cleanup_root": _py_script(
        "cleanup_root",
        "tools/cleanup_root.py",
        "Cleans root artifacts and moves loose GF files into expected folders.",
        timeout_sec=600,
    ),
    # --- BUILD ---
    "build_index": _py_script(
        "build_index",
        "tools/everything_matrix/build_index.py",
        "Rebuilds everything_matrix.json by scanning repo (languages, lexicon, QA).",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("--out", "--verbose", "--langs"),
        allow_positionals=False,
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
        allowed_flags=("--strategy", "--langs", "--clean"),
        allow_positionals=False,
    ),
    "bootstrap_tier1": _py_script(
        "bootstrap_tier1",
        "tools/bootstrap_tier1.py",
        "Bootstraps Tier 1 languages/wrappers.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--force", "--dry-run"),
        allow_positionals=False,
    ),
    # --- DATA REFINERY ---
    "harvest_lexicon": _py_script(
        "harvest_lexicon",
        "tools/harvest_lexicon.py",
        "Bulk lexicon mining/harvesting into shard JSON files.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=(
            "--lang",
            "--langs",
            "--out",
            "--root",
            "--limit",
            "--max",
            "--source",
            "--dry-run",
            "--verbose",
        ),
        allow_positionals=True,
    ),
    "build_lexicon_wikidata": _py_script(
        "build_lexicon_wikidata",
        "tools/build_lexicon_from_wikidata.py",
        "Builds lexicon shards directly from Wikidata (online).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--lang", "--out", "--limit", "--dry-run", "--verbose"),
        allow_positionals=False,
    ),
    "refresh_index": _py_script(
        "refresh_index",
        "utils/refresh_lexicon_index.py",
        "Rebuilds the fast lexicon lookup index used by API.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("--langs", "--root", "--out"),
        allow_positionals=False,
    ),
    "migrate_schema": _py_script(
        "migrate_schema",
        "utils/migrate_lexicon_schema.py",
        "Migrates lexicon JSON shards to newer schema versions.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--root", "--in-place", "--dry-run", "--from", "--to"),
        allow_positionals=False,
    ),
    "dump_stats": _py_script(
        "dump_stats",
        "utils/dump_lexicon_stats.py",
        "Prints lexicon coverage/size statistics.",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("--langs", "--root", "--format"),
        allow_positionals=False,
    ),
    # --- QA & TESTING ---
    "run_smoke_tests": _pytest_file(
        "run_smoke_tests",
        "tests/test_lexicon_smoke.py",
        "Lexicon schema/syntax smoke tests.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
    ),
    "run_judge": _pytest_file(
        "run_judge",
        "tests/integration/test_quality.py",
        "Executes Golden Standard regression checks (AI Judge integration).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
    ),
    "eval_bios": _py_script(
        "eval_bios",
        "tools/qa/eval_bios.py",
        "Compares generated biographies against Wikidata facts.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--limit", "--out", "--verbose"),
        allow_positionals=False,
    ),
    "lexicon_coverage": _py_script(
        "lexicon_coverage",
        "tools/qa/lexicon_coverage_report.py",
        "Coverage report for intended vs implemented lexicon.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--format", "--verbose"),
        allow_positionals=False,
    ),
    # Legacy alias: tools/qa/test_runner.py no longer exists; point to universal_test_runner.py
    "test_runner": _py_script(
        "test_runner",
        "tools/qa/universal_test_runner.py",
        "Legacy alias: standard CSV-based linguistic test suite runner.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--suite", "--in", "--out", "--langs", "--limit", "--verbose"),
        allow_positionals=False,
    ),
    "universal_test_runner": _py_script(
        "universal_test_runner",
        "tools/qa/universal_test_runner.py",
        "Advanced CSV test runner (supports more complex constructions).",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--suite", "--in", "--out", "--langs", "--limit", "--verbose"),
        allow_positionals=False,
    ),
    "batch_test_generator": _py_script(
        "batch_test_generator",
        "tools/qa/batch_test_generator.py",
        "Bulk generation of test datasets for regression.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--limit", "--seed", "--verbose"),
        allow_positionals=False,
    ),
    "test_suite_generator": _py_script(
        "test_suite_generator",
        "tools/qa/test_suite_generator.py",
        "Generates empty CSV templates for manual/AI fill-in.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--verbose"),
        allow_positionals=False,
    ),
    "generate_lexicon_regression_tests": _py_script(
        "generate_lexicon_regression_tests",
        "tools/qa/generate_lexicon_regression_tests.py",
        "Builds regression tests from lexicon for CI/QA.",
        timeout_sec=1800,
        allow_args=True,
        allowed_flags=("--langs", "--out", "--limit", "--verbose"),
        allow_positionals=False,
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
    ),
    # --- TESTS (select additional inventory tests) ---
    "test_api_smoke": _pytest_file(
        "test_api_smoke",
        "tests/test_api_smoke.py",
        "API smoke tests (fast signal).",
        timeout_sec=600,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
    ),
    "test_gf_dynamic": _pytest_file(
        "test_gf_dynamic",
        "tests/test_gf_dynamic.py",
        "Validates dynamic loading/linearization of GF grammars.",
        timeout_sec=900,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
    ),
    "test_multilingual_generation": _pytest_file(
        "test_multilingual_generation",
        "tests/test_multilingual_generation.py",
        "Multilingual generation regression tests.",
        timeout_sec=1200,
        allow_args=True,
        allowed_flags=("-q", "-vv", "-k", "-m", "--maxfail", "--disable-warnings"),
    ),
}

# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------
# Fix for Pydantic v2: avoid assigning ConfigDict in class body (it becomes a
# non-annotated attribute). Use a try/except and set `model_config` only.
try:
    from pydantic import ConfigDict as _PydConfigDict  # type: ignore
except Exception:  # pragma: no cover
    _PydConfigDict = None  # type: ignore


class ToolRunRequest(BaseModel):
    tool_id: str = Field(..., description="Allowlisted tool identifier.")
    args: List[str] = Field(default_factory=list, description="Optional argv-style args for the tool.")
    dry_run: bool = Field(False, description="If true, returns the command without executing.")

    # pydantic v2
    if _PydConfigDict is not None:
        model_config: ClassVar[_PydConfigDict] = _PydConfigDict(extra="ignore")  # type: ignore
    else:
        # pydantic v1
        class Config:  # type: ignore
            extra = "ignore"


class ToolRunResponse(BaseModel):
    success: bool
    command: str
    output: str
    error: str
    exit_code: int
    duration_ms: int
    truncated: bool


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
def _validate_tool_id(tool_id: str) -> None:
    if not TOOL_ID_RE.match(tool_id):
        raise HTTPException(status_code=400, detail="Invalid tool_id format.")


def _validate_args(spec: ToolSpec, args: Sequence[str]) -> List[str]:
    if not args:
        return []

    if not spec.allow_args:
        raise HTTPException(status_code=400, detail=f"Tool '{spec.tool_id}' does not accept args.")

    if len(args) > 40:
        raise HTTPException(status_code=400, detail="Too many args.")

    cleaned: List[str] = []
    for a in args:
        if not isinstance(a, str):
            raise HTTPException(status_code=400, detail="All args must be strings.")
        if "\x00" in a or "\n" in a or "\r" in a:
            raise HTTPException(status_code=400, detail="Invalid characters in args.")
        if len(a) > 512:
            raise HTTPException(status_code=400, detail="Arg too long.")
        cleaned.append(a)

    if spec.allowed_flags:
        allowed = set(spec.allowed_flags)
        for a in cleaned:
            if a.startswith("-"):
                flag = a.split("=", 1)[0]
                if flag not in allowed:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Flag not allowed for '{spec.tool_id}': {flag}",
                    )
            else:
                if not spec.allow_positionals:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Positional args not allowed for '{spec.tool_id}': {a}",
                    )

    return cleaned


def _render_cmd(spec: ToolSpec) -> List[str]:
    target_path = _resolve_repo_path(spec.rel_target)
    _ensure_exists(target_path, spec.rel_target)
    return [part.format(target=str(target_path)) for part in spec.cmd]


def _run_process(cmd: Sequence[str], timeout_sec: int) -> Tuple[int, str, str, int]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    started = time.time()
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        duration_ms = int((time.time() - started) * 1000)
        return proc.returncode, proc.stdout or "", proc.stderr or "", duration_ms
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - started) * 1000)
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
        stderr = (stderr + "\n" if stderr else "") + f"Process timed out (limit: {timeout_sec}s)."
        return 124, stdout, stderr, duration_ms


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
    _validate_tool_id(payload.tool_id)

    spec = TOOL_REGISTRY.get(payload.tool_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Tool '{payload.tool_id}' not found in registry.")

    if spec.requires_ai_enabled and not AI_TOOLS_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="AI tools are disabled. Set ARCHITECT_ENABLE_AI_TOOLS=1 to enable.",
        )

    cmd = _render_cmd(spec)
    safe_args = _validate_args(spec, payload.args or [])
    cmd = list(cmd) + safe_args

    if payload.dry_run:
        return ToolRunResponse(
            success=True,
            command=_safe_join_cmd(cmd),
            output="",
            error="",
            exit_code=0,
            duration_ms=0,
            truncated=False,
        )

    exit_code, stdout, stderr, duration_ms = _run_process(cmd, spec.timeout_sec)

    out_trunc, out_was_trunc = _truncate(stdout)
    err_trunc, err_was_trunc = _truncate(stderr)
    truncated = out_was_trunc or err_was_trunc

    return ToolRunResponse(
        success=exit_code == 0,
        command=_safe_join_cmd(cmd),
        output=out_trunc,
        error=err_trunc,
        exit_code=exit_code,
        duration_ms=duration_ms,
        truncated=truncated,
    )