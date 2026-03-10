from __future__ import annotations

import ast
import json
import re
import shlex
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.adapters.api.dependencies import verify_api_key
from app.adapters.api.tools.config import (
    AI_TOOLS_ENABLED,
    MAX_OUTPUT_CHARS,
    REPO_ROOT,
    TOOL_ID_RE,
    ensure_exists,
    iso_now,
    resolve_repo_path,
    safe_join_cmd,
    truncate,
)
from app.adapters.api.tools.models import (
    ToolMeta,
    ToolRunArgsRejected,
    ToolRunEvent,
    ToolRunRequest,
    ToolRunResponse,
    ToolRunTruncation,
    ToolSpec,
    ToolSummary,
)
from app.adapters.api.tools.registry import TOOL_REGISTRY
from app.adapters.api.tools.runner import run_process_extended

router = APIRouter(dependencies=[Depends(verify_api_key)])


# -----------------------------------------------------------------------------
# WORKFLOW TAXONOMY (backend source of truth for registry consumers)
# -----------------------------------------------------------------------------
WORKFLOW_FILTERS = (
    "recommended",
    "language_integration",
    "lexicon_work",
    "build_matrix",
    "qa_validation",
    "debug_recovery",
    "ai_assist",
    "all",
)
WORKFLOW_FILTER_SET = set(WORKFLOW_FILTERS)
DEFAULT_WORKFLOW = "recommended"

_DEFAULT_WORKFLOW_STEPS: Dict[str, List[str]] = {
    "recommended": [
        "Build Index",
        "Compile PGF",
        "Language Health",
        "Generate sentence",
        "Run Judge",
    ],
    "language_integration": [
        "Add or update language files",
        "Build Index",
        "Validate lexicon",
        "Compile PGF",
        "Language Health",
        "Generate sentence",
        "Run Judge",
    ],
    "lexicon_work": [
        "Harvest or seed data",
        "Fill gaps",
        "Validate lexicon coverage",
        "Refresh indices",
        "Re-run health checks",
    ],
    "build_matrix": [
        "Refresh Everything Matrix",
        "Compile PGF",
        "Validate health",
    ],
    "qa_validation": [
        "Language Health",
        "Generate sentence",
        "Run Judge",
        "Profile if needed",
    ],
    "debug_recovery": [
        "Run diagnostics",
        "Use targeted scanner or test",
        "Fix",
        "Rebuild",
        "Re-validate",
    ],
    "ai_assist": [
        "Use deterministic tools first",
        "Invoke AI assist only for the gap",
        "Rebuild",
        "Re-validate",
    ],
    "all": [],
}

_TOOL_ID_WORKFLOWS: Dict[str, Tuple[str, ...]] = {
    "build_index": ("recommended", "language_integration", "build_matrix"),
    "compile_pgf": ("recommended", "language_integration", "build_matrix"),
    "language_health": ("recommended", "language_integration", "qa_validation"),
    "run_judge": ("recommended", "language_integration", "qa_validation"),
    "lexicon_coverage": ("language_integration", "lexicon_work"),
    "harvest_lexicon": ("language_integration", "lexicon_work"),
    "gap_filler": ("language_integration", "lexicon_work"),
    "bootstrap_tier1": ("language_integration", "build_matrix", "debug_recovery"),
    "diagnostic_audit": ("debug_recovery",),
    "profiler": ("qa_validation",),
    "ai_refiner": ("ai_assist", "debug_recovery"),
    "rgl_scanner": ("build_matrix", "debug_recovery"),
    "lexicon_scanner": ("build_matrix", "debug_recovery"),
    "app_scanner": ("build_matrix", "debug_recovery"),
    "qa_scanner": ("build_matrix", "debug_recovery"),
    "refresh_lexicon_index": ("lexicon_work",),
    "migrate_lexicon_schema": ("lexicon_work",),
    "dump_lexicon_stats": ("lexicon_work",),
    "seed_lexicon_ai": ("lexicon_work", "ai_assist"),
    "build_lexicon_from_wikidata": ("lexicon_work",),
    "ambiguity_detector": ("qa_validation",),
    "batch_test_generator": ("qa_validation",),
    "generate_lexicon_regression_tests": ("qa_validation",),
    "test_api_smoke": ("qa_validation", "debug_recovery"),
    "test_gf_dynamic": ("qa_validation", "debug_recovery"),
    "test_multilingual_generation": ("qa_validation", "debug_recovery"),
    "run_smoke_tests": ("qa_validation", "debug_recovery"),
}


# -----------------------------------------------------------------------------
# REDACTION (avoid leaking secrets via events/response/command strings)
# -----------------------------------------------------------------------------
_SENSITIVE_FLAG_EXACT = {
    "--api-key",
    "--apikey",
    "--api_token",
    "--api-token",
    "--token",
    "--access-token",
    "--refresh-token",
    "--secret",
    "--password",
    "--passwd",
    "--bearer",
    "--authorization",
    "--auth",
}
_SENSITIVE_FLAG_RE = re.compile(
    r"^--?[A-Za-z0-9._-]*(key|token|secret|pass(word|wd)?|bearer|auth)[A-Za-z0-9._-]*$"
)


def _is_sensitive_flag(flag: str) -> bool:
    f = (flag or "").strip()
    if not f.startswith("-"):
        return False
    f0 = f.split("=", 1)[0].lower()
    return f0 in _SENSITIVE_FLAG_EXACT or bool(_SENSITIVE_FLAG_RE.match(f0))


def redact_argv(args: Sequence[str]) -> List[str]:
    """
    Redacts values for sensitive flags in argv-like tokens.

    Handles both:
      --api-key VALUE
      --api-key=VALUE
    """
    out: List[str] = []
    expecting_value_for_sensitive = False

    for tok in list(args or []):
        t = str(tok)

        if expecting_value_for_sensitive:
            if t.startswith("-"):
                out.append(t)
            else:
                out.append("***redacted***")
            expecting_value_for_sensitive = False
            continue

        if t.startswith("-") and "=" in t:
            flag, _val = t.split("=", 1)
            if _is_sensitive_flag(flag):
                out.append(f"{flag}=***redacted***")
            else:
                out.append(t)
            continue

        if t.startswith("-"):
            out.append(t)
            if _is_sensitive_flag(t):
                expecting_value_for_sensitive = True
            continue

        out.append(t)

    return out


def _redact_rejected(rejected: Sequence[ToolRunArgsRejected]) -> List[ToolRunArgsRejected]:
    """
    Redacts rejected arg tokens too (covers --api-key=... style).
    """
    out: List[ToolRunArgsRejected] = []
    for r in list(rejected or []):
        arg = getattr(r, "arg", "")
        if isinstance(arg, str) and arg.startswith("-") and "=" in arg:
            flag, _val = arg.split("=", 1)
            if _is_sensitive_flag(flag):
                arg = f"{flag}=***redacted***"
        out.append(ToolRunArgsRejected(arg=arg, reason=getattr(r, "reason", "")))
    return out


def _has_redactions(original: Sequence[str], redacted: Sequence[str]) -> bool:
    if len(original) != len(redacted):
        return True
    return any(a != b for a, b in zip(original, redacted))


# -----------------------------------------------------------------------------
# EVENTS / UTIL
# -----------------------------------------------------------------------------
def emit_event(
    events: List[ToolRunEvent],
    level: str,
    step: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    events.append(ToolRunEvent(ts=iso_now(), level=level, step=step, message=message, data=data))


def validate_tool_id(tool_id: str) -> None:
    if not TOOL_ID_RE.match(tool_id):
        raise HTTPException(status_code=400, detail="Invalid tool_id format.")


def model_dump(m) -> Dict[str, Any]:
    if hasattr(m, "model_dump"):
        return m.model_dump()
    return m.dict()


def _model_field_names(model_cls: Any) -> set[str]:
    fields = getattr(model_cls, "model_fields", None)
    if fields is not None:
        return set(fields.keys())
    fields = getattr(model_cls, "__fields__", None)
    if fields is not None:
        return set(fields.keys())
    return set()


_TOOLMETA_FIELDS = _model_field_names(ToolMeta)
_TOOLSUMMARY_FIELDS = _model_field_names(ToolSummary)


def _coerce_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for x in value:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []


def _dedupe_strs(values: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _workflow_steps_for(workflow: str) -> List[str]:
    return list(_DEFAULT_WORKFLOW_STEPS.get(workflow, []))


def _workflow_tags_from_path(path: str) -> List[str]:
    p = path.lower()
    tags: List[str] = []

    if "build_index" in p:
        tags.extend(["recommended", "language_integration", "build_matrix"])

    if "compile_pgf" in p or "build_orchestrator" in p or p.startswith("gf/"):
        tags.extend(["recommended", "language_integration", "build_matrix"])

    if "language_health" in p:
        tags.extend(["recommended", "language_integration", "qa_validation"])

    if "run_judge" in p:
        tags.extend(["recommended", "language_integration", "qa_validation"])

    if any(k in p for k in ("lexicon_coverage", "harvest_lexicon", "gap_filler", "refresh_lexicon_index",
                            "migrate_lexicon_schema", "dump_lexicon_stats", "build_lexicon_from_wikidata")):
        tags.append("lexicon_work")

    if any(k in p for k in ("lexicon_coverage", "harvest_lexicon", "gap_filler", "bootstrap_tier1")):
        tags.append("language_integration")

    if p.startswith("tools/everything_matrix/"):
        tags.extend(["build_matrix", "debug_recovery"])

    if p.startswith("tools/qa/") or p.startswith("tests/") or any(
        k in p for k in ("run_judge", "profiler", "ambiguity_detector", "batch_test_generator")
    ):
        tags.append("qa_validation")

    if any(
        k in p
        for k in (
            "diagnostic_audit",
            "cleanup_root",
            "smoke",
            "test_api",
            "test_gf",
            "test_multilingual",
            "rgl_scanner",
            "lexicon_scanner",
            "app_scanner",
            "qa_scanner",
        )
    ):
        tags.append("debug_recovery")

    if any(k in p for k in ("ai_refiner", "seed_lexicon_ai")) or p.startswith("ai_services/"):
        tags.append("ai_assist")

    return _dedupe_strs([t for t in tags if t in WORKFLOW_FILTER_SET and t != "all"])


def _workflows_for_spec(spec: ToolSpec) -> List[str]:
    explicit = []
    for attr in ("workflows", "workflow_tags"):
        explicit.extend(_coerce_str_list(getattr(spec, attr, None)))
    explicit = [w for w in explicit if w in WORKFLOW_FILTER_SET and w != "all"]

    if explicit:
        return _dedupe_strs(explicit)

    mapped = list(_TOOL_ID_WORKFLOWS.get(spec.tool_id, ()))
    if mapped:
        return _dedupe_strs(mapped)

    derived = _workflow_tags_from_path(spec.rel_target)
    if derived:
        return derived

    return [DEFAULT_WORKFLOW]


def _workflow_primary_for_spec(spec: ToolSpec, workflows: Sequence[str]) -> str:
    explicit = str(getattr(spec, "workflow_primary", "") or "").strip()
    if explicit in WORKFLOW_FILTER_SET and explicit != "all":
        return explicit
    return workflows[0] if workflows else DEFAULT_WORKFLOW


def _workflow_steps_map_for_spec(spec: ToolSpec, workflows: Sequence[str]) -> Dict[str, List[str]]:
    explicit = getattr(spec, "workflow_steps", None)
    if isinstance(explicit, dict):
        out: Dict[str, List[str]] = {}
        for key, value in explicit.items():
            k = str(key).strip()
            if k not in WORKFLOW_FILTER_SET:
                continue
            out[k] = _coerce_str_list(value)
        if out:
            return out

    return {wf: _workflow_steps_for(wf) for wf in workflows}


def _tool_meta_payload(spec: ToolSpec, available: bool) -> Dict[str, Any]:
    workflows = _workflows_for_spec(spec)
    workflow_primary = _workflow_primary_for_spec(spec, workflows)
    workflow_steps = _workflow_steps_map_for_spec(spec, workflows)

    payload: Dict[str, Any] = {
        "tool_id": spec.tool_id,
        "description": spec.description,
        "timeout_sec": spec.timeout_sec,
        "allow_args": spec.allow_args,
        "requires_ai_enabled": spec.requires_ai_enabled,
        "available": available,
    }

    optional_values: Dict[str, Any] = {
        "label": getattr(spec, "label", spec.tool_id),
        "hidden": bool(getattr(spec, "hidden", False)),
        "power_user": bool(getattr(spec, "hidden", False)),
        "risk": getattr(spec, "risk", None),
        "category": getattr(spec, "category", None),
        "group": getattr(spec, "group", None),
        "notes": _coerce_str_list(getattr(spec, "notes", None)),
        "ui_steps": _coerce_str_list(getattr(spec, "ui_steps", None)),
        "workflows": workflows,
        "workflow_primary": workflow_primary,
        "workflow_steps": workflow_steps,
    }

    for key, value in optional_values.items():
        if key in _TOOLMETA_FIELDS:
            payload[key] = value

    return payload


def tool_summary_from_spec(spec: Optional[ToolSpec], tool_id: str) -> ToolSummary:
    if spec is None:
        label = tool_id
        payload = {"id": tool_id, "label": label, "description": "", "timeout_sec": 0}
        if "workflows" in _TOOLSUMMARY_FIELDS:
            payload["workflows"] = [DEFAULT_WORKFLOW]
        if "workflow_primary" in _TOOLSUMMARY_FIELDS:
            payload["workflow_primary"] = DEFAULT_WORKFLOW
        return ToolSummary(**payload)

    label = getattr(spec, "label", spec.tool_id)
    payload = {
        "id": spec.tool_id,
        "label": label,
        "description": spec.description,
        "timeout_sec": spec.timeout_sec,
    }
    workflows = _workflows_for_spec(spec)
    workflow_primary = _workflow_primary_for_spec(spec, workflows)

    if "workflows" in _TOOLSUMMARY_FIELDS:
        payload["workflows"] = workflows
    if "workflow_primary" in _TOOLSUMMARY_FIELDS:
        payload["workflow_primary"] = workflow_primary

    return ToolSummary(**payload)


def error_envelope(
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
    args_received_r = redact_argv(args_received or [])
    args_accepted_r = redact_argv(args_accepted or [])
    args_rejected_r = _redact_rejected(args_rejected or [])

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
        tool=tool_summary_from_spec(spec, tool_id),
        args_received=args_received_r,
        args_accepted=args_accepted_r,
        args_rejected=args_rejected_r,
        truncation=ToolRunTruncation(stdout=False, stderr=False, limit_chars=MAX_OUTPUT_CHARS),
        events=events,
    )
    return JSONResponse(status_code=http_status, content=model_dump(res))


def render_cmd(spec: ToolSpec) -> List[str]:
    target_path = resolve_repo_path(spec.rel_target)
    ensure_exists(target_path, spec.rel_target)
    return [part.format(target=str(target_path)) for part in spec.cmd]


# -----------------------------------------------------------------------------
# ARGS NORMALIZATION
# -----------------------------------------------------------------------------
def _safe_str_list(x: Any) -> Optional[List[str]]:
    if isinstance(x, (list, tuple)) and all(isinstance(i, str) for i in x):
        return list(x)
    return None


def _parse_listish_string(s: str) -> Optional[List[str]]:
    """
    Parses:
      - JSON list: ["--mode","compile"]
      - Python literal list/tuple: ['--mode','compile'] / ('--mode','compile')
      - Bracket+comma form: [--mode,compile,--fast]
    """
    ss = s.strip()
    if not ss:
        return []
    if not ((ss.startswith("[") and ss.endswith("]")) or (ss.startswith("(") and ss.endswith(")"))):
        return None

    try:
        lit = json.loads(ss)
        as_list = _safe_str_list(lit)
        if as_list is not None:
            return as_list
    except Exception:
        pass

    try:
        lit = ast.literal_eval(ss)
        as_list = _safe_str_list(lit)
        if as_list is not None:
            return as_list
    except Exception:
        pass

    inner = ss[1:-1].strip()
    if not inner:
        return []
    if "," in inner:
        return [p.strip() for p in inner.split(",") if p.strip()]
    return shlex.split(inner)


def normalize_args(raw: Optional[Union[Sequence[str], str]]) -> List[str]:
    """
    Normalizes args into list[str].

    Supports:
      - None -> []
      - ["--mode","compile"] -> as-is
      - "--mode compile --fast" -> shlex split
      - "[--mode,compile,--fast]" -> bracket+comma split
      - "['--mode','compile']" / '["--mode","compile"]' -> list parse
      - ["[--mode,compile,--fast]"] -> unwrap + parse
      - ["--mode compile --fast"] -> unwrap + shlex split
      - ["--mode,compile,--fast"] -> comma split
    """
    if raw is None:
        return []

    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        parsed = _parse_listish_string(s)
        if parsed is not None:
            return parsed
        return shlex.split(s)

    if isinstance(raw, (list, tuple)):
        if len(raw) == 1 and isinstance(raw[0], str):
            one = raw[0].strip()
            if not one:
                return []
            parsed = _parse_listish_string(one)
            if parsed is not None:
                return parsed
            if " " in one and any(tok.startswith("-") for tok in one.split()):
                return shlex.split(one)

        out: List[str] = []
        for a in raw:
            if not isinstance(a, str):
                raise HTTPException(status_code=400, detail="All args must be strings.")
            t = a.strip()
            if not t:
                continue

            parsed = _parse_listish_string(t)
            if parsed is not None:
                out.extend(parsed)
                continue

            if " " in t and any(tok.startswith("-") for tok in t.split()):
                out.extend(shlex.split(t))
                continue

            if "," in t and " " not in t and t.lstrip().startswith("-"):
                out.extend([p.strip() for p in t.split(",") if p.strip()])
                continue

            out.append(t)

        return out

    raise HTTPException(status_code=400, detail="Invalid args format; expected list of strings or string.")


def _expand_equals_multi_flags(args: List[str], spec: ToolSpec) -> List[str]:
    """
    Expand multi-value flags like:
      --langs=en,fr,de -> --langs en fr de
    """
    multi = set(spec.flags_with_multi_value or ())
    if not multi:
        return args

    out: List[str] = []
    for a in args:
        if a.startswith("-") and "=" in a:
            flag, val = a.split("=", 1)
            if flag in multi and "," in val and val.strip():
                out.append(flag)
                out.extend([v for v in (p.strip() for p in val.split(",")) if v])
                continue
        out.append(a)
    return out


# -----------------------------------------------------------------------------
# ARG VALIDATION
# -----------------------------------------------------------------------------
def validate_args(spec: ToolSpec, args: Sequence[str]) -> Tuple[List[str], List[ToolRunArgsRejected]]:
    if not args:
        return [], []

    accepted: List[str] = []
    rejected: List[ToolRunArgsRejected] = []

    for a in args:
        if not isinstance(a, str):
            raise HTTPException(status_code=400, detail="All args must be strings.")
        if "\x00" in a or "\n" in a or "\r" in a:
            raise HTTPException(status_code=400, detail="Invalid characters in args.")
        if len(a) > 512:
            raise HTTPException(status_code=400, detail="Arg too long.")

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

            if "=" in a:
                i += 1
                continue

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

            if flag in flags_with_value:
                if i + 1 < n and not args[i + 1].startswith("-"):
                    accepted.append(args[i + 1])
                    i += 2
                else:
                    rejected.append(ToolRunArgsRejected(arg=flag, reason="Flag requires a value."))
                    i += 1
                continue

            i += 1
            continue

        if not spec.allow_positionals:
            rejected.append(ToolRunArgsRejected(arg=a, reason="Positional arguments not allowed."))
        else:
            accepted.append(a)
        i += 1

    return accepted, rejected


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@router.get("/registry", response_model=List[ToolMeta])
async def list_tools() -> List[ToolMeta]:
    metas: List[ToolMeta] = []
    for spec in sorted(TOOL_REGISTRY.values(), key=lambda s: s.tool_id):
        try:
            available = resolve_repo_path(spec.rel_target).exists()
        except Exception:
            available = False

        metas.append(ToolMeta(**_tool_meta_payload(spec, available)))
    return metas


@router.post("/run", response_model=ToolRunResponse)
async def run_tool(payload: ToolRunRequest) -> ToolRunResponse:
    trace_id = str(uuid.uuid4())
    started_at = iso_now()
    events: List[ToolRunEvent] = []

    emit_event(events, "INFO", "request_received", "Tool run request received", {"tool_id": payload.tool_id})

    try:
        normalized_args = normalize_args(payload.args)  # type: ignore[arg-type]
    except HTTPException as e:
        emit_event(events, "ERROR", "args_normalized", f"Argument normalization error: {e.detail}")
        return error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=None,
            command="",
            message=str(e.detail),
            events=events,
            args_received=[],
            args_accepted=[],
            args_rejected=[],
        )

    normalized_args_log = redact_argv(normalized_args)

    if normalized_args != (payload.args or []):
        emit_event(
            events,
            "INFO",
            "args_normalized",
            "Args normalized.",
            {"normalized_count": len(normalized_args_log), "normalized": normalized_args_log},
        )

    try:
        validate_tool_id(payload.tool_id)
    except HTTPException as e:
        emit_event(events, "ERROR", "tool_validated", f"Invalid tool ID: {e.detail}")
        return error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=None,
            command="",
            message=str(e.detail),
            events=events,
            args_received=normalized_args_log,
            args_accepted=[],
            args_rejected=[],
        )

    spec = TOOL_REGISTRY.get(payload.tool_id)
    if not spec:
        emit_event(events, "ERROR", "tool_validated", f"Tool '{payload.tool_id}' not found in registry.")
        return error_envelope(
            http_status=404,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=None,
            command="",
            message=f"Tool '{payload.tool_id}' not found in registry.",
            events=events,
            args_received=normalized_args_log,
            args_accepted=[],
            args_rejected=[],
        )

    emit_event(events, "INFO", "tool_validated", "Tool found in registry", {"description": spec.description})

    if spec.requires_ai_enabled and not AI_TOOLS_ENABLED:
        msg = "AI tools are disabled. Set ARCHITECT_ENABLE_AI_TOOLS=1 to enable."
        emit_event(events, "ERROR", "tool_check", msg)
        return error_envelope(
            http_status=403,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=msg,
            events=events,
            args_received=normalized_args_log,
            args_accepted=[],
            args_rejected=[],
        )

    normalized_args = _expand_equals_multi_flags(normalized_args, spec)
    normalized_args_log = redact_argv(normalized_args)

    try:
        args_accepted, args_rejected = validate_args(spec, normalized_args)
    except HTTPException as e:
        emit_event(events, "ERROR", "args_validated", f"Argument validation error: {e.detail}")
        return error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=str(e.detail),
            events=events,
            args_received=normalized_args_log,
            args_accepted=[],
            args_rejected=[],
        )

    args_accepted_log = redact_argv(args_accepted)
    args_rejected_log = _redact_rejected(args_rejected)

    if args_rejected:
        emit_event(
            events,
            "WARN",
            "args_validated",
            "Some arguments were rejected.",
            {"accepted_count": len(args_accepted), "rejected_count": len(args_rejected)},
        )

        if normalized_args and not args_accepted:
            msg = "All provided arguments were rejected; refusing to execute tool with defaults."
            emit_event(events, "ERROR", "args_rejected_abort", msg)
            return error_envelope(
                http_status=400,
                trace_id=trace_id,
                started_at=started_at,
                ended_at=iso_now(),
                tool_id=payload.tool_id,
                spec=spec,
                command="",
                message=msg,
                events=events,
                args_received=normalized_args_log,
                args_accepted=args_accepted_log,
                args_rejected=args_rejected_log,
            )
    else:
        emit_event(events, "INFO", "args_validated", f"All {len(args_accepted)} arguments accepted.")

    try:
        base_cmd = render_cmd(spec)
    except HTTPException as e:
        emit_event(events, "ERROR", "cmd_prepared", f"Command preparation failed: {e.detail}")
        return error_envelope(
            http_status=e.status_code,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=iso_now(),
            tool_id=payload.tool_id,
            spec=spec,
            command="",
            message=str(e.detail),
            events=events,
            args_received=normalized_args_log,
            args_accepted=args_accepted_log,
            args_rejected=args_rejected_log,
        )

    final_cmd_list = list(base_cmd) + args_accepted
    final_cmd_str = safe_join_cmd(final_cmd_list)

    redacted_cmd_list = redact_argv(final_cmd_list)
    redacted_cmd_str = safe_join_cmd(redacted_cmd_list)
    cmd_for_response = redacted_cmd_str if _has_redactions(final_cmd_list, redacted_cmd_list) else final_cmd_str

    if payload.dry_run:
        emit_event(events, "INFO", "dry_run", "Returning dry-run response.")
        return ToolRunResponse(
            trace_id=trace_id,
            success=True,
            command=cmd_for_response,
            output="",
            error="",
            stdout="",
            stderr="",
            stdout_chars=0,
            stderr_chars=0,
            exit_code=0,
            duration_ms=0,
            started_at=started_at,
            ended_at=iso_now(),
            cwd=str(REPO_ROOT),
            repo_root=str(REPO_ROOT),
            tool=tool_summary_from_spec(spec, payload.tool_id),
            args_received=normalized_args_log,
            args_accepted=args_accepted_log,
            args_rejected=args_rejected_log,
            truncation=ToolRunTruncation(stdout=False, stderr=False, limit_chars=MAX_OUTPUT_CHARS),
            events=events,
        )

    emit_event(events, "INFO", "process_spawned", f"Executing command with timeout {spec.timeout_sec}s")

    env_vars = {"TOOL_TRACE_ID": trace_id}
    try:
        exit_code, stdout, stderr, duration_ms = await run_in_threadpool(
            run_process_extended,
            final_cmd_list,
            spec.timeout_sec,
            env_vars,
        )
    except Exception as e:
        ended_at = iso_now()
        msg = f"Tool runner crashed while executing subprocess: {type(e).__name__}: {e}"
        emit_event(events, "ERROR", "process_failed", msg)
        return error_envelope(
            http_status=500,
            trace_id=trace_id,
            started_at=started_at,
            ended_at=ended_at,
            tool_id=payload.tool_id,
            spec=spec,
            command=cmd_for_response,
            message=msg,
            events=events,
            args_received=normalized_args_log,
            args_accepted=args_accepted_log,
            args_rejected=args_rejected_log,
        )

    ended_at = iso_now()
    emit_event(events, "INFO", "process_exited", f"Process exited with code {exit_code}", {"duration_ms": duration_ms})

    out_trunc, out_was_trunc = truncate(stdout)
    err_trunc, err_was_trunc = truncate(stderr)

    if out_was_trunc:
        emit_event(events, "WARN", "output_truncated", "Stdout exceeded limit and was truncated.")
    if err_was_trunc:
        emit_event(events, "WARN", "output_truncated", "Stderr exceeded limit and was truncated.")

    return ToolRunResponse(
        trace_id=trace_id,
        success=(exit_code == 0),
        command=cmd_for_response,
        output=out_trunc,
        error=err_trunc,
        stdout=out_trunc,
        stderr=err_trunc,
        stdout_chars=len(stdout),
        stderr_chars=len(stderr),
        exit_code=exit_code,
        duration_ms=duration_ms,
        started_at=started_at,
        ended_at=ended_at,
        cwd=str(REPO_ROOT),
        repo_root=str(REPO_ROOT),
        tool=tool_summary_from_spec(spec, payload.tool_id),
        args_received=normalized_args_log,
        args_accepted=args_accepted_log,
        args_rejected=args_rejected_log,
        truncation=ToolRunTruncation(stdout=out_was_trunc, stderr=err_was_trunc, limit_chars=MAX_OUTPUT_CHARS),
        events=events,
    )

