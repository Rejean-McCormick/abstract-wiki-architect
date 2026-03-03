// architect_frontend/src/app/tools/lib/toolRun.ts

import type {
  HttpMeta,
  RunToolOptions,
  RunToolResult,
  ToolRunArgsRejected,
  ToolRunEvent,
  ToolRunResponse,
  ToolRunResponseWire,
  ToolRunTruncation,
  ToolSummary,
} from "../types";

type Ok<T> = { ok: true; value: T };
type Err = { ok: false; error: unknown };

// Back-compat: allow callers to pass dryRun even if types drift.
// (If your RunToolOptions already includes dryRun, this is harmless.)
type RunToolOnceOptions = RunToolOptions & { dryRun?: boolean };

export function safeJsonParse<T>(s: string): Ok<T> | Err {
  try {
    return { ok: true, value: JSON.parse(s) as T };
  } catch (e) {
    return { ok: false, error: e };
  }
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function bool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function strArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  const out: string[] = [];
  for (const x of v) if (typeof x === "string") out.push(x);
  return out;
}

function toEvents(v: unknown): ToolRunEvent[] {
  if (!Array.isArray(v)) return [];
  const out: ToolRunEvent[] = [];
  for (const raw of v) {
    if (!isPlainObject(raw)) continue;
    out.push({
      ts: str(raw.ts),
      level: str(raw.level) as any,
      step: str(raw.step),
      message: str(raw.message),
      data: isPlainObject(raw.data) ? (raw.data as Record<string, unknown>) : undefined,
    });
  }
  return out;
}

function toRejectedArgs(v: unknown): ToolRunArgsRejected[] {
  if (!Array.isArray(v)) return [];
  const out: ToolRunArgsRejected[] = [];
  for (const raw of v) {
    if (!isPlainObject(raw)) continue;
    const arg = str(raw.arg);
    const reason = str(raw.reason);
    if (arg || reason) out.push({ arg, reason });
  }
  return out;
}

function toTruncation(v: unknown): ToolRunTruncation {
  if (!isPlainObject(v)) return { stdout: false, stderr: false, limit_chars: 0 };
  return {
    stdout: bool(v.stdout, false),
    stderr: bool(v.stderr, false),
    limit_chars: num(v.limit_chars, 0),
  };
}

function toToolSummary(toolId: string, v: unknown): ToolSummary {
  if (!isPlainObject(v)) return { id: toolId, label: "", description: "", timeout_sec: 0 };
  return {
    id: str(v.id, toolId),
    label: str(v.label),
    description: str(v.description),
    timeout_sec: num(v.timeout_sec, 0),
  };
}

function httpLine(http?: HttpMeta) {
  if (!http) return "HTTP (unknown)";
  return `HTTP ${http.status} ${http.statusText}${http.ok ? "" : " (non-2xx)"}`;
}

/**
 * Treat `--dry` as an alias for `--dry-run` and also infer dry-run intent
 * from args when the UI doesn't pass opts.dryRun.
 *
 * - Converts `--dry` -> `--dry-run`
 * - Dedupe if both appear
 * - Returns whether args imply dry-run
 */
function normalizeDryArgs(args: string[]) {
  let sawDry = false;
  let sawDryRun = false;

  const out: string[] = [];
  for (const a of args) {
    if (a === "--dry") {
      sawDry = true;
      if (!sawDryRun) out.push("--dry-run");
      sawDryRun = true;
      continue;
    }
    if (a === "--dry-run") {
      sawDryRun = true;
      if (!out.includes("--dry-run")) out.push(a);
      continue;
    }

    if (a.startsWith("--dry=") || a.startsWith("--dry-run=")) {
      const [, rawVal = ""] = a.split("=", 2);
      const v = rawVal.trim().toLowerCase();
      const truthy = v === "" || v === "1" || v === "true" || v === "yes" || v === "y" || v === "on";
      const falsy = v === "0" || v === "false" || v === "no" || v === "n" || v === "off";

      if (truthy) {
        sawDry = sawDry || a.startsWith("--dry=");
        sawDryRun = true;
        if (!out.includes("--dry-run")) out.push("--dry-run");
      } else if (falsy) {
        // drop explicit false
      } else {
        out.push(a);
      }
      continue;
    }

    out.push(a);
  }

  return { args: out, dryFromArgs: sawDry || sawDryRun };
}

/**
 * Normalize possibly-partial server payload into a stable ToolRunResponse shape.
 * If parsing failed, returns a structured error response.
 */
export function normalizeToolRunResponse(
  toolId: string,
  rawText: string,
  parsed: unknown,
  http?: HttpMeta
): ToolRunResponse {
  if (!isPlainObject(parsed)) {
    return {
      trace_id: "",
      success: false,
      command: "",

      stdout: "",
      stderr: rawText || "",
      stdout_chars: 0,
      stderr_chars: rawText?.length ?? 0,

      exit_code: -1,
      duration_ms: 0,
      started_at: "",
      ended_at: "",

      cwd: "",
      repo_root: "",
      tool: { id: toolId, label: "", description: "", timeout_sec: 0 },

      args_received: [],
      args_accepted: [],
      args_rejected: [],

      truncation: { stdout: false, stderr: false, limit_chars: 0 },
      events: [],

      output: "",
      error: `${httpLine(http)}\n\n${rawText || "(empty response)"}`,
    };
  }

  const p = parsed as unknown as ToolRunResponseWire;

  const stdout = str(p.stdout);
  const stderr = str(p.stderr);
  const success = bool(p.success, false);

  const exitCodeFallback = success ? 0 : -1;
  const exitCode = num(p.exit_code ?? (p as any).return_code, exitCodeFallback);

  const normalized: ToolRunResponse = {
    trace_id: str(p.trace_id),
    success,

    command: str(p.command),

    stdout,
    stderr,
    stdout_chars: num(p.stdout_chars, stdout.length),
    stderr_chars: num(p.stderr_chars, stderr.length),

    exit_code: exitCode,
    duration_ms: num(p.duration_ms, 0),
    started_at: str(p.started_at),
    ended_at: str(p.ended_at),

    cwd: str(p.cwd),
    repo_root: str(p.repo_root),

    tool: toToolSummary(toolId, p.tool),

    args_received: strArray(p.args_received),
    args_accepted: strArray(p.args_accepted),
    args_rejected: toRejectedArgs(p.args_rejected),

    truncation: toTruncation(p.truncation),
    events: toEvents(p.events),
  };

  if (typeof p.run_id === "string") normalized.run_id = p.run_id;
  if (Array.isArray(p.argv)) normalized.argv = strArray(p.argv);
  if (typeof p.tool_id === "string") normalized.tool_id = p.tool_id;
  if (typeof p.output === "string") normalized.output = p.output;
  if (typeof p.error === "string") normalized.error = p.error;

  if ("stdout_json" in (p as any)) normalized.stdout_json = (p as any).stdout_json;
  if ("stderr_json" in (p as any)) normalized.stderr_json = (p as any).stderr_json;
  if (Array.isArray((p as any).artifacts)) normalized.artifacts = (p as any).artifacts;
  if (isPlainObject((p as any).process)) normalized.process = (p as any).process;

  return normalized;
}

/** Minimal, stable event time formatter for console logs. */
export function formatEventTime(ts: string) {
  const t = ts.split("T")[1] || ts;
  return t.replace("Z", "");
}

export function formatRunForConsole(normalized: ToolRunResponse, clientDurationMs: number): string[] {
  const lines: string[] = [];
  const trace = normalized.trace_id || "(none)";

  lines.push(`[TRACE] ${trace}`);
  lines.push(
    `[TIME]  Started: ${normalized.started_at || "(server)"} | Client duration: ${clientDurationMs}ms | Server: ${normalized.duration_ms}ms`
  );

  if (normalized.events?.length) {
    lines.push(`\n[LIFECYCLE]`);
    for (const e of normalized.events) {
      lines.push(`  ${formatEventTime(e.ts)} [${e.level}] ${e.step}: ${e.message}`);
    }
  }

  if (normalized.args_rejected?.length) {
    lines.push(`\n[WARN] Rejected Arguments:`);
    for (const r of normalized.args_rejected) lines.push(`  - ${r.arg}: ${r.reason}`);
  }

  if (normalized.stdout) {
    lines.push(`\n[STDOUT] (${normalized.stdout_chars} chars)`);
    lines.push(normalized.stdout);
    if (normalized.truncation?.stdout) lines.push("... [TRUNCATED]");
  }

  if (normalized.stderr) {
    lines.push(`\n[STDERR] (${normalized.stderr_chars} chars)`);
    lines.push(normalized.stderr);
    if (normalized.truncation?.stderr) lines.push("... [TRUNCATED]");
  }

  lines.push(normalized.success ? `\n[SUCCESS] exit_code=${normalized.exit_code}` : `\n[FAILED] exit_code=${normalized.exit_code}`);

  if (!normalized.success && !normalized.stderr && normalized.error) {
    lines.push(`\n[ERROR]`);
    lines.push(normalized.error);
  }

  return lines;
}

function toNetworkErrorDetail(err: unknown, url: string): string {
  if (err instanceof DOMException && err.name === "AbortError") return `Request aborted: ${url}`;
  if (err instanceof Error) return `${err.name}: ${err.message}\nURL: ${url}`;
  return `Unknown network error\nURL: ${url}`;
}

function getPublicApiKey(): string {
  return process.env.NEXT_PUBLIC_ARCHITECT_API_KEY || process.env.NEXT_PUBLIC_API_KEY || "";
}

/**
 * Runs a backend-wired tool via POST {apiV1}/tools/run.
 * Returns normalized response + raw text + http meta + client duration.
 */
export async function runToolOnce(opts: RunToolOnceOptions): Promise<RunToolResult> {
  const fetchImpl = opts.fetchImpl ?? fetch;

  const controller = opts.timeoutMs ? new AbortController() : null;
  const timeout = opts.timeoutMs ? setTimeout(() => controller?.abort(), opts.timeoutMs) : null;

  const signal = controller ? mergeAbortSignals(opts.signal, controller.signal) : opts.signal;

  const inArgs = normalizeDryArgs(Array.isArray(opts.args) ? opts.args : []);
  const effectiveDryRun = Boolean(opts.dryRun ?? inArgs.dryFromArgs);

  const startedAt = performance.now();
  const url = `${opts.apiV1}/tools/run`;

  try {
    const apiKey = getPublicApiKey();

    const res = await fetchImpl(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify({
        tool_id: opts.toolId,
        args: inArgs.args,
        dry_run: effectiveDryRun,
      }),
      cache: "no-store",
      signal,
    });

    const http: HttpMeta = { ok: res.ok, status: res.status, statusText: res.statusText };
    const rawText = await res.text();

    const parsedTry = safeJsonParse<unknown>(rawText);
    const normalized = normalizeToolRunResponse(opts.toolId, rawText, parsedTry.ok ? parsedTry.value : null, http);

    const clientDurationMs = Math.max(0, Math.round(performance.now() - startedAt));
    return { http, rawText, normalized, clientDurationMs };
  } catch (e) {
    const clientDurationMs = Math.max(0, Math.round(performance.now() - startedAt));
    const http: HttpMeta = { ok: false, status: 0, statusText: "NETWORK_ERROR" };
    const rawText = toNetworkErrorDetail(e, url);
    const normalized = normalizeToolRunResponse(opts.toolId, rawText, null, http);
    return { http, rawText, normalized, clientDurationMs };
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

function mergeAbortSignals(a?: AbortSignal, b?: AbortSignal): AbortSignal | undefined {
  if (!a) return b;
  if (!b) return a;
  if (a.aborted) return a;
  if (b.aborted) return b;

  const c = new AbortController();
  const onAbort = () => c.abort();

  const cleanup = () => {
    a.removeEventListener("abort", onAbort);
    b.removeEventListener("abort", onAbort);
  };

  a.addEventListener("abort", onAbort, { once: true });
  b.addEventListener("abort", onAbort, { once: true });

  c.signal.addEventListener("abort", cleanup, { once: true });
  return c.signal;
}

/** Prefers stdout; falls back to legacy output. */
export function extractJsonFromRun(normalized: ToolRunResponse): string | null {
  const s = normalized.stdout || normalized.output || "";
  const t = s.trim();
  return t.length ? t : null;
}

export function tryParseVisualizerTree(outputJson: string): { ok: true; tree: unknown } | { ok: false } {
  const t = safeJsonParse<any>(outputJson);
  if (!t.ok || !t.value) return { ok: false };
  const tree = t.value.tree ?? t.value.ast ?? null;
  if (!tree) return { ok: false };
  return { ok: true, tree };
}