from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


WorkflowId = Literal[
    "recommended",
    "language_integration",
    "lexicon_work",
    "build_matrix",
    "qa_validation",
    "debug_recovery",
    "ai_assist",
    "all",
]


@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    description: str
    rel_target: str
    cmd: Tuple[str, ...]  # supports "{target}" placeholder
    timeout_sec: int

    allow_args: bool = False
    allowed_flags: Tuple[str, ...] = ()
    allow_positionals: bool = False
    requires_ai_enabled: bool = False

    flags_with_value: Tuple[str, ...] = ()        # consumes exactly 1 value token
    flags_with_multi_value: Tuple[str, ...] = ()  # consumes 1+ value tokens until next flag

    # UI / registry metadata
    label: Optional[str] = None
    category: str = "maintenance"
    hidden: bool = False
    legacy: bool = False
    internal: bool = False
    heavy: bool = False
    is_test: bool = False

    # Workflow metadata
    workflow_tags: Tuple[WorkflowId, ...] = ()
    workflow_order: int = 1000


# ---- Pydantic models (request/response) ----
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
    label: str
    description: str
    timeout_sec: int
    category: Optional[str] = None
    workflow_tags: List[WorkflowId] = Field(default_factory=list)


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

    output: str
    error: str
    stdout: str
    stderr: str
    stdout_chars: int
    stderr_chars: int

    exit_code: int
    duration_ms: int
    started_at: str
    ended_at: str

    cwd: str
    repo_root: str
    tool: ToolSummary

    args_received: List[str]
    args_accepted: List[str]
    args_rejected: List[ToolRunArgsRejected]

    truncation: ToolRunTruncation
    events: List[ToolRunEvent]


class ToolWorkflowGuide(BaseModel):
    workflow_id: WorkflowId
    label: str
    summary: Optional[str] = None
    steps: List[str] = Field(default_factory=list)
    tool_ids: List[str] = Field(default_factory=list)
    power_user_addons: List[str] = Field(default_factory=list)


class ToolMeta(BaseModel):
    tool_id: str
    label: Optional[str] = None
    description: str
    timeout_sec: int

    allow_args: bool
    requires_ai_enabled: bool
    available: bool

    category: str = "maintenance"
    hidden: bool = False
    legacy: bool = False
    internal: bool = False
    heavy: bool = False
    is_test: bool = False

    allowed_flags: List[str] = Field(default_factory=list)
    allow_positionals: bool = False
    flags_with_value: List[str] = Field(default_factory=list)
    flags_with_multi_value: List[str] = Field(default_factory=list)

    workflow_tags: List[WorkflowId] = Field(default_factory=list)
    workflow_order: int = 1000


class ToolRegistryResponse(BaseModel):
    tools: List[ToolMeta] = Field(default_factory=list)
    workflows: List[ToolWorkflowGuide] = Field(default_factory=list)