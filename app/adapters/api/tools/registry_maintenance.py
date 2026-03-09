from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from .config import DEFAULT_TIMEOUT_SEC, PYTHON_EXE
from .models import ToolSpec

ParameterDoc = Mapping[str, Any]


def py_script(
    tool_id: str,
    rel_script: str,
    description: str,
    *,
    title: str,
    category: str,
    group: str,
    risk: str = "safe",
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
    allow_positionals: bool = False,
    requires_ai_enabled: bool = False,
    flags_with_value: Sequence[str] = (),
    flags_with_multi_value: Sequence[str] = (),
    hidden: bool = False,
    recommended: bool = False,
    workflow_ids: Sequence[str] = (),
    long_description: str | None = None,
    parameter_docs: Sequence[ParameterDoc] = (),
    common_failure_modes: Sequence[str] = (),
    supports_verbose: bool = False,
    supports_json: bool = False,
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        title=title,
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
        category=category,
        group=group,
        risk=risk,
        hidden=hidden,
        recommended=recommended,
        workflow_ids=tuple(workflow_ids),
        long_description=long_description,
        parameter_docs=tuple(parameter_docs),
        common_failure_modes=tuple(common_failure_modes),
        supports_verbose=supports_verbose,
        supports_json=supports_json,
    )


def maintenance_registry() -> Dict[str, ToolSpec]:
    language_health_timeout = max(DEFAULT_TIMEOUT_SEC, 1800)

    return {
        # --- MAINTENANCE / HEALTH ---
        "language_health": py_script(
            "language_health",
            "tools/language_health.py",
            "Language health/diagnostics utility (status checks and reporting).",
            title="Language Health",
            category="Operations & Health",
            group="Health Checks",
            risk="safe",
            timeout_sec=language_health_timeout,
            allow_args=True,
            allowed_flags=(
                "--mode",
                "--fast",
                "--parallel",
                "--api-url",
                "--timeout",
                "--limit",
                "--langs",
                "--no-disable-script",
                "--verbose",
                "--json",
            ),
            allow_positionals=False,
            flags_with_value=(
                "--mode",
                "--parallel",
                "--api-url",
                "--timeout",
                "--limit",
            ),
            flags_with_multi_value=("--langs",),
            recommended=True,
            workflow_ids=(
                "recommended",
                "language_integration",
                "build_matrix",
                "qa_validation",
                "all",
            ),
            long_description=(
                "Deep scan of compilation status and API runtime health. "
                "Use this after compiling, or as the main proof-of-life check for a language."
            ),
            parameter_docs=(
                {"flag": "--mode", "description": "Audit mode", "example": "--mode both"},
                {"flag": "--fast", "description": "Skip unchanged VALID files in compile mode"},
                {"flag": "--parallel", "description": "Worker count", "example": "--parallel 8"},
                {"flag": "--api-url", "description": "Override API base URL", "example": "--api-url http://localhost:8000"},
                {"flag": "--timeout", "description": "Per-request timeout in seconds", "example": "--timeout 120"},
                {"flag": "--limit", "description": "Limit languages checked", "example": "--limit 10"},
                {"flag": "--langs", "description": "Languages to check", "example": "--langs en fr"},
                {"flag": "--no-disable-script", "description": "Do not ignore *.disabled grammar files"},
                {"flag": "--verbose", "description": "Enable detailed step-by-step logs"},
                {"flag": "--json", "description": "Emit machine-readable JSON summary"},
            ),
            common_failure_modes=(
                "API is not reachable at the configured URL.",
                "PGF binary is stale or missing.",
                "Per-language compile artifacts are out of date.",
            ),
            supports_verbose=True,
            supports_json=True,
        ),
        "diagnostic_audit": py_script(
            "diagnostic_audit",
            "tools/diagnostic_audit.py",
            "Forensics audit for stale artifacts / zombie outputs.",
            title="Diagnostic Audit",
            category="Debug & Recovery",
            group="Diagnostics",
            risk="safe",
            timeout_sec=DEFAULT_TIMEOUT_SEC,
            allow_args=True,
            allowed_flags=("--verbose", "--json"),
            workflow_ids=("debug_recovery", "all"),
            long_description=(
                "Filesystem forensics pass for stale artifacts, zombie outputs, and broken grammar links. "
                "Use when the repo/build state looks inconsistent."
            ),
            parameter_docs=(
                {"flag": "--verbose", "description": "Enable detailed step-by-step logs"},
                {"flag": "--json", "description": "Emit machine-readable JSON summary"},
            ),
            common_failure_modes=(
                "Everything Matrix is stale or missing.",
                "Generated artifacts do not match current source layout.",
            ),
            supports_verbose=True,
            supports_json=True,
        ),
        "cleanup_root": py_script(
            "cleanup_root",
            "tools/cleanup_root.py",
            "Cleans root artifacts and moves loose GF files into expected folders.",
            title="Cleanup Root",
            category="Debug & Recovery",
            group="Repair & Cleanup",
            risk="moderate",
            timeout_sec=DEFAULT_TIMEOUT_SEC,
            allow_args=True,
            allowed_flags=("--dry-run", "--verbose", "--json"),
            workflow_ids=("debug_recovery", "all"),
            long_description=(
                "Repairs root-level drift by cleaning loose artifacts and moving misplaced GF files "
                "into the expected repository structure."
            ),
            parameter_docs=(
                {"flag": "--dry-run", "description": "Show planned changes without writing files"},
                {"flag": "--verbose", "description": "Enable detailed step-by-step logs"},
                {"flag": "--json", "description": "Emit machine-readable JSON summary"},
            ),
            common_failure_modes=(
                "Repository contains unexpected loose artifacts.",
                "Files are already in conflict with expected destination paths.",
            ),
            supports_verbose=True,
            supports_json=True,
        ),
        # --- HEALTH & DEBUGGING ---
        "profiler": py_script(
            "profiler",
            "tools/health/profiler.py",
            "Benchmarks Grammar Engine performance (TPS, Latency, Memory).",
            title="Performance Profiler",
            category="QA & Validation",
            group="Performance",
            risk="moderate",
            timeout_sec=300,
            allow_args=True,
            allowed_flags=("--lang", "--iterations", "--update-baseline", "--threshold", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--lang", "--iterations", "--threshold"),
            workflow_ids=("qa_validation", "all"),
            long_description=(
                "Benchmarks runtime performance for a selected language. "
                "Use after functionality is confirmed and before locking a language in."
            ),
            parameter_docs=(
                {"flag": "--lang", "description": "Language to benchmark", "example": "--lang fr"},
                {"flag": "--iterations", "description": "Number of benchmark iterations", "example": "--iterations 200"},
                {"flag": "--update-baseline", "description": "Persist the new baseline after a successful run"},
                {"flag": "--threshold", "description": "Failure threshold", "example": "--threshold 1.25"},
                {"flag": "--verbose", "description": "Enable detailed step-by-step logs"},
            ),
            common_failure_modes=(
                "Baseline data is missing or incompatible.",
                "API/runtime is too unstable for meaningful measurements.",
            ),
            supports_verbose=True,
            supports_json=False,
        ),
        "visualize_ast": py_script(
            "visualize_ast",
            "tools/debug/visualize_ast.py",
            "Generates JSON Abstract Syntax Tree from sentence or intent.",
            title="Visualize AST",
            category="Debug & Recovery",
            group="AST & Parsing",
            risk="safe",
            timeout_sec=60,
            allow_args=True,
            allowed_flags=("--lang", "--sentence", "--ast", "--pgf"),
            allow_positionals=False,
            flags_with_value=("--lang", "--sentence", "--ast", "--pgf"),
            hidden=True,
            workflow_ids=("debug_recovery", "all"),
            long_description=(
                "Low-level parser/debugging utility to inspect GF abstract syntax trees from input text or AST input."
            ),
            parameter_docs=(
                {"flag": "--lang", "description": "Language code", "example": "--lang en"},
                {"flag": "--sentence", "description": "Sentence to parse", "example": '--sentence "Marie Curie was a physicist."' },
                {"flag": "--ast", "description": "Explicit AST input"},
                {"flag": "--pgf", "description": "Override PGF path", "example": "--pgf gf/semantik_architect.pgf"},
            ),
            common_failure_modes=(
                "Sentence is outside the grammar coverage.",
                "PGF path is wrong or the binary is stale.",
            ),
            supports_verbose=False,
            supports_json=True,
        ),
    }

