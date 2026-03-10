// architect_frontend/src/app/tools/types.ts

import type { BackendToolId, Risk, ToolParameter } from "./backendRegistry";
import type { Status, ToolKind, Visibility } from "./classify";

// ----------------------------------------------------------------------------
// Shared primitives
// ----------------------------------------------------------------------------

/** ISO-ish datetime strings from the backend (kept permissive). */
export type ISODateTimeString = string;

/** JSON helper types (handy for stdout_json / stderr_json). */
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [k: string]: JsonValue };
export type JsonObject = { [k: string]: JsonValue };

/**
 * Risk/status/kind re-exports for UI convenience.
 * Keeps UI code decoupled from backendRegistry/classify module paths.
 */
export type ToolRisk = Risk;
export type ToolStatus = Status;
export type ToolKindUI = ToolKind;
export type ToolVisibility = Visibility;

export type ConsoleStatus = "success" | "warning" | "error" | null;

// ----------------------------------------------------------------------------
// Workflow filters / recommended workflows
// ----------------------------------------------------------------------------

export type WorkflowFilterId =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

export type WorkflowFilterOption = {
  id: WorkflowFilterId;
  label: string;
  description?: string;
};

export type WorkflowStep = {
  id: string;
  title: string;
  description?: string;
  toolIds?: string[];
  argsHint?: string;
  optional?: boolean;
};

export type WorkflowDefinition = {
  id: WorkflowFilterId;
  label: string;
  description: string;
  toolIds: string[];
  powerUserToolIds?: string[];
  steps: WorkflowStep[];
  emptyStateTitle?: string;
  emptyStateBody?: string;
};

export type WorkflowSelection = {
  id: WorkflowFilterId;
  powerUser: boolean;
};

// ----------------------------------------------------------------------------
// Inventory (frontend-local)
// ----------------------------------------------------------------------------

export type Tool = {
  id: string;
  name: string;
  description: string;
  category: string;
  defaultArgs?: string;
  workflowIds?: WorkflowFilterId[];
  recommended?: boolean;
};

// ----------------------------------------------------------------------------
// Canonical UI ToolItem
// ----------------------------------------------------------------------------

export type ToolItem = {
  /** Stable UI key (often derived from path). */
  key: string;

  /** Display title. */
  title: string;

  /** Repo-relative path (e.g. tools/foo.py). */
  path: string;

  /** Short human description. */
  desc?: string;

  /** CLI hint / example invocation. */
  cli: readonly string[];

  /** Grouping metadata for panels and filters. */
  category: string;
  group: string;

  /** Classification */
  kind: ToolKindUI;
  status: ToolStatus;
  risk: ToolRisk;

  /** Visibility controls */
  visibility?: ToolVisibility;
  hidden?: boolean;
  hiddenInNormalMode?: boolean;

  /** Optional richer help */
  notes: string[];
  uiSteps: string[];

  /** Dynamic parameter definitions for UI checkboxes/inputs */
  parameterDocs?: ToolParameter[];

  /** Wiring helpers */
  commandPreview?: string;
  toolIdGuess: string;
  wiredToolId?: BackendToolId | null;

  /** Workflow metadata */
  workflowIds?: WorkflowFilterId[];
  recommended?: boolean;
};

// ----------------------------------------------------------------------------
// /health/ready
// ----------------------------------------------------------------------------

/**
 * /health/ready payload
 * Keep permissive because this endpoint often grows over time.
 */
export type HealthReady = {
  broker?: string;
  storage?: string;
  engine?: string;

  ok?: boolean;
  version?: string;
  commit?: string;
  checks?: Record<string, unknown>;

  // allow backend extensions without breaking the client
  [k: string]: unknown;
};

// ----------------------------------------------------------------------------
// /tools/run request
// ----------------------------------------------------------------------------

/**
 * /tools/run request (matches backend ToolRunRequest)
 */
export type ToolRunRequest = {
  tool_id: string;
  args?: string[];
  dry_run?: boolean;
};

// ----------------------------------------------------------------------------
// /tools/run response (wire + normalized)
// ----------------------------------------------------------------------------

/**
 * Keep literal union benefits while still allowing arbitrary string levels.
 */
export type ToolRunLevel = "INFO" | "WARN" | "ERROR" | (string & {});

export type ToolRunEvent = {
  ts: ISODateTimeString;
  level: ToolRunLevel;
  step: string;
  message: string;
  data?: Record<string, unknown>;
};

export type ToolRunTruncation = {
  stdout: boolean;
  stderr: boolean;
  limit_chars: number;
};

export type ToolRunArgsRejected = {
  arg: string;
  reason: string;
};

export type ToolSummary = {
  id: string;
  label: string;
  description: string;
  timeout_sec: number;
};

export type ToolRunArtifactKind = "file" | "dir" | "report" | "log" | "other";

export type ToolRunArtifact = {
  path: string; // usually repo-relative
  kind?: ToolRunArtifactKind;
  label?: string;
  mime?: string;
};

export type ToolRunProcessInfo = {
  pid?: number;
  host?: string;
  signal?: string | null;
  timed_out?: boolean;
  killed?: boolean;
};

/**
 * /tools/run response shape "as received" from the backend.
 * Tolerates older backends and partial failures.
 *
 * Only `success` is required; everything else may be missing on legacy or error paths.
 */
export type ToolRunResponseWire = {
  success: boolean;

  // Identity & Lifecycle
  trace_id?: string;
  run_id?: string;

  exit_code?: number;
  return_code?: number; // legacy alias

  duration_ms?: number;
  started_at?: ISODateTimeString;
  ended_at?: ISODateTimeString;

  // Command Context
  command?: string;
  argv?: string[];
  cwd?: string;
  repo_root?: string;

  tool?: ToolSummary;
  tool_id?: string;

  // Streams (Rich)
  stdout?: string;
  stderr?: string;
  stdout_chars?: number;
  stderr_chars?: number;
  truncation?: ToolRunTruncation;

  // Streams (Legacy/Fallback aliases)
  output?: string;
  error?: string;

  // Argument Validation
  args_received?: string[];
  args_accepted?: string[];
  args_rejected?: ToolRunArgsRejected[];

  // Telemetry
  events?: ToolRunEvent[];

  // Optional machine-parsed outputs
  stdout_json?: unknown;
  stderr_json?: unknown;

  // Artifacts produced by tool run
  artifacts?: ToolRunArtifact[];

  // Process/termination details
  process?: ToolRunProcessInfo;

  // allow backend extensions
  [k: string]: unknown;
};

/**
 * Normalized response shape after client-side normalization.
 * Keep core fields required so UI code can be simple.
 */
export type ToolRunResponseCore = {
  trace_id: string;
  success: boolean;

  command: string;

  stdout: string;
  stderr: string;
  stdout_chars: number;
  stderr_chars: number;

  exit_code: number;
  duration_ms: number;
  started_at: ISODateTimeString;
  ended_at: ISODateTimeString;

  cwd: string;
  repo_root: string;

  tool: ToolSummary;

  args_received: string[];
  args_accepted: string[];
  args_rejected: ToolRunArgsRejected[];

  truncation: ToolRunTruncation;
  events: ToolRunEvent[];
};

export type ToolRunResponseExtras = {
  run_id?: string;
  argv?: string[];
  tool_id?: string;

  // preserved legacy aliases / server detail fields
  output?: string;
  error?: string;

  // preserved structured outputs
  stdout_json?: unknown;
  stderr_json?: unknown;

  // preserved tool artifacts / process info
  artifacts?: ToolRunArtifact[];
  process?: ToolRunProcessInfo;
};

export type ToolRunResponse = ToolRunResponseCore & ToolRunResponseExtras;

// ----------------------------------------------------------------------------
// HTTP / Runner types (shared)
// ----------------------------------------------------------------------------

export type HttpMeta = {
  ok: boolean;
  status: number;
  statusText: string;
};

export type RunToolOptions = {
  apiV1: string;
  toolId: string;
  args: string[];

  /**
   * Convenience flag for callers; request payload still uses `dry_run`.
   * (Used by useToolRunner.)
   */
  dryRun?: boolean;

  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
};

export type RunToolResult = {
  http: HttpMeta;
  rawText: string;
  normalized: ToolRunResponse;
  clientDurationMs: number;
};