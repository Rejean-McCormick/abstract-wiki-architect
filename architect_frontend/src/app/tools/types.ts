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

/**
 * /tools/run response
 * (matches backend ToolRunResponse, with legacy fields tolerated)
 */
export type ToolRunResponse = {
  success: boolean;
  command?: string;
  output?: string;
  error?: string;

  // backend (current)
  exit_code?: number;
  duration_ms?: number;
  truncated?: boolean;

  // legacy tolerance
  return_code?: number;
  tool_id?: string;
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
};
