// architect_frontend/src/app/tools/utils.ts

import type { ToolRunResponse } from "./types";

// Minimal shell-ish parser (whitespace split + quotes + backslash escapes).
// NOTE: This is intentionally simple; backend still validates/allowlists flags.
export function parseCliArgs(input: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inSingle = false;
  let inDouble = false;

  const push = () => {
    if (cur.length) out.push(cur);
    cur = "";
  };

  for (let i = 0; i < input.length; i++) {
    const ch = input[i];

    // Backslash escapes next char (outside single quotes; inside double quotes it's common too)
    if (ch === "\\" && i + 1 < input.length) {
      // In single quotes, treat backslash literally (closer to shell behavior)
      if (inSingle) {
        cur += ch;
        continue;
      }
      cur += input[i + 1];
      i++;
      continue;
    }

    if (!inDouble && ch === "'") {
      inSingle = !inSingle;
      continue;
    }
    if (!inSingle && ch === '"') {
      inDouble = !inDouble;
      continue;
    }

    if (!inSingle && !inDouble && /\s/.test(ch)) {
      push();
      continue;
    }

    cur += ch;
  }

  push();
  return out;
}

/**
 * Best-effort clipboard helper.
 * Returns true if it likely succeeded, false otherwise.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to legacy path
  }

  // Legacy fallback (works in more contexts, but not all)
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export const docsHref = (key: string) => `#${key}`;

export const normalizeBaseUrl = (raw: string) => raw.replace(/\/$/, "");

export const normalizeApiV1 = (rawBase: string) => {
  const base = normalizeBaseUrl(rawBase);
  return base.endsWith("/api/v1") ? base : `${base}/api/v1`;
};

export const normalizeRepoUrl = (raw: string) => raw.replace(/\/$/, "");

// Keep "main" as default branch (consistent with current UI),
// but allow override via NEXT_PUBLIC_REPO_BRANCH.
export const repoFileUrl = (repoUrl: string, path: string) => {
  if (!repoUrl) return "";
  const branch = (process.env.NEXT_PUBLIC_REPO_BRANCH || "main").trim() || "main";
  return `${normalizeRepoUrl(repoUrl)}/blob/${branch}/${path}`;
};

/**
 * Utility: small, safe classnames combiner (no dependency).
 */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// ----------------------------------------------------------------------------
// Rich Response Normalization & Formatting
// ----------------------------------------------------------------------------

/**
 * Ensures any API response (legacy or new) fits the ToolRunResponse shape.
 * Handles missing fields, legacy output/error keys, and defaults.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function normalizeToolResponse(data: any): ToolRunResponse {
  const now = new Date().toISOString();
  
  // 1. Map legacy streams if new ones are missing
  const stdout = data.stdout ?? data.output ?? "";
  const stderr = data.stderr ?? data.error ?? "";

  return {
    trace_id: data.trace_id || `sim-${Date.now()}`,
    success: Boolean(data.success),
    command: data.command || "",
    
    // Streams
    stdout,
    stderr,
    stdout_chars: typeof data.stdout_chars === 'number' ? data.stdout_chars : stdout.length,
    stderr_chars: typeof data.stderr_chars === 'number' ? data.stderr_chars : stderr.length,
    
    // Legacy aliases
    output: stdout,
    error: stderr,

    // Lifecycle
    exit_code: data.exit_code ?? data.return_code ?? (data.success ? 0 : 1),
    duration_ms: data.duration_ms ?? 0,
    started_at: data.started_at || now,
    ended_at: data.ended_at || now,
    
    // Metadata
    cwd: data.cwd || "~",
    repo_root: data.repo_root || "",
    tool: data.tool || { 
      id: "unknown", 
      label: "Unknown Tool", 
      description: "", 
      timeout_sec: 0 
    },

    // Arguments
    args_received: Array.isArray(data.args_received) ? data.args_received : [],
    args_accepted: Array.isArray(data.args_accepted) ? data.args_accepted : [],
    args_rejected: Array.isArray(data.args_rejected) ? data.args_rejected : [],

    // Telemetry
    truncation: data.truncation || { 
      stdout: false, 
      stderr: false, 
      limit_chars: 0 
    },
    events: Array.isArray(data.events) ? data.events : [],
  };
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatTime(isoString: string): string {
  if (!isoString) return "";
  try {
    return new Date(isoString).toLocaleTimeString(undefined, {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3
    });
  } catch {
    return isoString;
  }
}