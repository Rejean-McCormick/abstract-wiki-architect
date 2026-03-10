from __future__ import annotations

from dataclasses import dataclass, field
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
    title: Optional[str] = None
    label: Optional[str] = None
    category: str = "maintenance"
    group: Optional[str] = None
    risk: str = "safe"

    hidden: bool = False
    legacy: bool = False
    internal: bool = False
    heavy: bool = False
    is_test: bool = False
    test_tool: bool = False
    recommended: bool = False

    # Rich metadata
    long_description: Optional[str] = None
    parameter_docs: Tuple[Dict[str, Any], ...] = ()
    common_failure_modes: Tuple[str, ...] = ()
    supports_verbose: bool = False
    supports_json: bool = False
    notes: Tuple[str, ...] = ()
    ui_steps: Tuple[str, ...] = ()

    # Workflow metadata
    workflow_tags: Tuple[WorkflowId, ...] = ()
    workflow_ids: Tuple[WorkflowId, ...] = ()
    workflows: Tuple[WorkflowId, ...] = ()
    workflow_primary: Optional[WorkflowId] = None
    workflow_steps: Dict[str, List[str]] = field(default_factory=dict)
    workflow_order: int = 1000
    recommended_order: Optional[int] = None
    power_user_only: bool = False
    normal_path: bool = True

    def __post_init__(self) -> None:
        if self.label is None and self.title is not None:
            object.__setattr__(self, "label", self.title)
        if self.title is None and self.label is not None:
            object.__setattr__(self, "title", self.label)

        if self.test_tool and not self.is_test:
            object.__setattr__(self, "is_test", True)
        if self.is_test and not self.test_tool:
            object.__setattr__(self, "test_tool", True)

        if self.risk == "heavy" and not self.heavy:
            object.__setattr__(self, "heavy", True)

        if not self.workflow_tags:
            if self.workflow_ids:
                object.__setattr__(self, "workflow_tags", tuple(self.workflow_ids))
            elif self.workflows:
                object.__setattr__(self, "workflow_tags", tuple(self.workflows))

        if not self.workflow_ids and self.workflow_tags:
            object.__setattr__(self, "workflow_ids", tuple(self.workflow_tags))
        if not self.workflows and self.workflow_tags:
            object.__setattr__(self, "workflows", tuple(self.workflow_tags))

        if self.recommended_order is None and self.workflow_order != 1000:
            object.__setattr__(self, "recommended_order", self.workflow_order)
        if self.recommended_order is not None and self.workflow_order == 1000:
            object.__setattr__(self, "workflow_order", self.recommended_order)

        if self.power_user_only and not self.hidden:
            object.__setattr__(self, "hidden", True)


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
    title: Optional[str] = None
    label: str
    description: str
    timeout_sec: int
    category: Optional[str] = None
    group: Optional[str] = None
    risk: Optional[str] = None

    workflow_tags: List[WorkflowId] = Field(default_factory=list)
    workflows: List[WorkflowId] = Field(default_factory=list)
    workflow_primary: Optional[WorkflowId] = None


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
    title: Optional[str] = None
    label: Optional[str] = None
    description: str
    timeout_sec: int

    allow_args: bool
    requires_ai_enabled: bool
    available: bool

    category: str = "maintenance"
    group: Optional[str] = None
    risk: str = "safe"

    hidden: bool = False
    power_user: bool = False
    legacy: bool = False
    internal: bool = False
    heavy: bool = False
    is_test: bool = False
    test_tool: bool = False
    recommended: bool = False
    normal_path: bool = True
    power_user_only: bool = False

    allowed_flags: List[str] = Field(default_factory=list)
    allow_positionals: bool = False
    flags_with_value: List[str] = Field(default_factory=list)
    flags_with_multi_value: List[str] = Field(default_factory=list)

    workflow_tags: List[WorkflowId] = Field(default_factory=list)
    workflows: List[WorkflowId] = Field(default_factory=list)
    workflow_primary: Optional[WorkflowId] = None
    workflow_steps: Dict[str, List[str]] = Field(default_factory=dict)
    workflow_order: int = 1000
    recommended_order: Optional[int] = None

    notes: List[str] = Field(default_factory=list)
    ui_steps: List[str] = Field(default_factory=list)

    long_description: Optional[str] = None
    parameter_docs: List[Dict[str, Any]] = Field(default_factory=list)
    common_failure_modes: List[str] = Field(default_factory=list)
    supports_verbose: bool = False
    supports_json: bool = False


class ToolRegistryResponse(BaseModel):
    tools: List[ToolMeta] = Field(default_factory=list)
    workflows: List[ToolWorkflowGuide] = Field(default_factory=list)