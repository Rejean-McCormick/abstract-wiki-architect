// architect_frontend/src/app/tools/types.ts

import type { Risk } from "./backendRegistry";
import type { Status, ToolKind, Visibility } from "./classify";

/**
 * /health/ready payload
 */
export type HealthReady = {
  broker?: string;
  storage?: string;
  engine?: string;
};

/**
 * /tools/run request
 * (matches backend ToolRunRequest)
 */
export type ToolRunRequest = {
  tool_id: string;
  args?: string[];
  dry_run?: boolean;
};

// --- Rich Telemetry Types ---

export type ToolRunEvent = {
  ts: string;
  level: string; // 'INFO' | 'WARN' | 'ERROR'
  step: string;
  message: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: Record<string, any>;
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

/**
 * /tools/run response
 * (matches backend ToolRunResponse, with legacy fields tolerated)
 */
export type ToolRunResponse = {
  // Identity & Lifecycle
  trace_id: string;
  success: boolean;
  exit_code: number;
  duration_ms: number;
  started_at: string;
  ended_at: string;

  // Command Context
  command: string;
  cwd: string;
  repo_root: string;
  tool: ToolSummary;

  // Streams (Rich)
  stdout: string;
  stderr: string;
  stdout_chars: number;
  stderr_chars: number;
  truncation: ToolRunTruncation;

  // Streams (Legacy/Fallback aliases)
  output?: string;
  error?: string;
  return_code?: number; // legacy alias for exit_code

  // Argument Validation
  args_received: string[];
  args_accepted: string[];
  args_rejected: ToolRunArgsRejected[];

  // Telemetry
  events: ToolRunEvent[];
};

export type ConsoleStatus = "success" | "error" | null;

/**
 * Unified UI item model (built from inventory + backend wiring)
 */
export type ToolItem = {
  key: string;
  title: string;
  path: string;

  category: string;
  group: string;

  kind: ToolKind;
  risk: Risk;
  status: Status;

  // optional: if you choose to surface these in UI later
  visibility?: Visibility;
  hideByDefault?: boolean;
  excludeFromUI?: boolean;

  desc?: string;

  cli: string[];
  notes: string[];
  uiSteps: string[];

  // wiring
  wiredToolId?: string; // exact backend allowlisted tool_id
  toolIdGuess: string; // best-effort guess for display/search
  commandPreview?: string; // backend registry command preview (if wired)
  hiddenInNormalMode?: boolean; // derived (debug-only)
};