// architect_frontend/src/services/api.ts

/**
 * ⛔ DEPRECATED: This module is being replaced by the canonical client in `src/lib/api.ts`.
 * This file remains as a **Compatibility Adapter** for legacy dashboards/components.
 *
 * Guarantees:
 * - Single source of truth for base URL (re-uses `API_BASE_URL` from `@/lib/api`)
 * - Correct `/api/v1/*` routing (no split-brain)
 * - Preserves legacy function signatures (with safer args handling)
 *
 * @deprecated Import `architectApi` from '@/lib/api' instead.
 */

import { architectApi, API_BASE_URL } from "@/lib/api";
import type { Language } from "@/lib/api";

// Re-export shared types to prevent breakage in components importing from here
export type { Language };

// Optional re-export for legacy imports
export { architectApi, API_BASE_URL };

// ============================================================================
// Internal helpers
// ============================================================================

const DEFAULT_TIMEOUT_MS = 60_000;

// Ensure we always target the v1 API (some environments may provide host-only base)
const API_V1_BASE_URL = API_BASE_URL.includes("/api/v1")
  ? API_BASE_URL.replace(/\/$/, "")
  : `${API_BASE_URL.replace(/\/$/, "")}/api/v1`;

function joinUrl(base: string, endpoint: string) {
  if (/^https?:\/\//i.test(endpoint)) return endpoint;
  const b = base.replace(/\/$/, "");
  const e = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${b}${e}`;
}

async function parseBody(res: Response): Promise<any> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractErrorMessage(body: any, fallback: string) {
  if (!body) return fallback;
  if (typeof body === "string") return body;
  if (typeof body?.detail === "string") return body.detail;
  if (body?.detail !== undefined) {
    try {
      return JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
  }
  if (typeof body?.message === "string") return body.message;
  try {
    return JSON.stringify(body);
  } catch {
    return fallback;
  }
}

type LegacyRequestOptions = RequestInit & { timeoutMs?: number };

/**
 * Legacy request helper (Internal Use Only)
 * Uses the Canonical API_BASE_URL to ensure no "Split-Brain" config.
 */
async function legacyRequest<T>(
  endpoint: string,
  options: LegacyRequestOptions = {}
): Promise<T> {
  const url = joinUrl(API_V1_BASE_URL, endpoint);

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = options.signal ? null : new AbortController();
  const signal = options.signal ?? controller?.signal;

  const timeout = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;

  try {
    const response = await fetch(url, { ...options, headers, signal });

    const body = await parseBody(response);

    if (!response.ok) {
      const msg = extractErrorMessage(
        body,
        `API Error ${response.status}: ${response.statusText}`
      );
      throw new Error(msg);
    }

    return body as T;
  } catch (error) {
    // Keep noisy logging localized to legacy adapter (canonical client should own its logging)
    // eslint-disable-next-line no-console
    console.error(`Legacy API Request Failed: ${endpoint}`, error);
    throw error;
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

// ============================================================================
// 1. LANGUAGE SERVICES
// ============================================================================

/**
 * @deprecated Use `architectApi.listLanguages()`
 */
export async function getLanguages(): Promise<Language[]> {
  // Prefer canonical client if present
  if (typeof (architectApi as any)?.listLanguages === "function") {
    return (architectApi as any).listLanguages();
  }
  // Fallback to direct v1 call
  return legacyRequest<Language[]>("/languages");
}

// ============================================================================
// 2. TOOLING & MAINTENANCE SERVICES
// ============================================================================

export interface ToolResponse {
  success: boolean;
  command?: string;
  output: string;
  error: string;
}

type ToolArgs = string[] | Record<string, unknown> | undefined;

function normalizeToolArgs(args: ToolArgs): string[] {
  if (!args) return [];
  if (Array.isArray(args)) return args.map(String);

  // Object -> argv (best-effort)
  const out: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    const key = k.startsWith("-") ? k : `--${k}`;
    if (v === undefined || v === null || v === false) continue;
    if (v === true) {
      out.push(key);
      continue;
    }
    if (Array.isArray(v)) {
      for (const item of v) out.push(`${key}=${String(item)}`);
      continue;
    }
    out.push(`${key}=${String(v)}`);
  }
  return out;
}

/**
 * Triggers a backend maintenance script.
 * Maintained for legacy dashboards/tools UI.
 *
 * Backend expects: { tool_id: string, args?: string[] }
 */
export async function runTool(
  toolId: string,
  args?: ToolArgs
): Promise<ToolResponse> {
  return legacyRequest<ToolResponse>("/tools/run", {
    method: "POST",
    body: JSON.stringify({
      tool_id: toolId,
      args: normalizeToolArgs(args),
    }),
    // Tools can be long-running; backend itself enforces 300s timeout.
    timeoutMs: 310_000,
  });
}

// ============================================================================
// 3. SYSTEM HEALTH SERVICES
// ============================================================================

export interface SystemHealth {
  broker: "up" | "down";
  storage: "up" | "down";
  engine: "up" | "down";
}

/**
 * Basic liveness check.
 * @deprecated Use `architectApi.health()` (canonical)
 */
export async function getHealth(): Promise<{ status: string }> {
  try {
    const fn = (architectApi as any)?.health;
    if (typeof fn === "function") {
      const res = await fn.call(architectApi);
      if (typeof res === "boolean") return { status: res ? "ok" : "error" };
      if (typeof res?.status === "string") return { status: res.status };
      return { status: "ok" };
    }
    const res = await legacyRequest<{ status?: string }>("/health");
    return { status: res?.status ?? "ok" };
  } catch {
    return { status: "error" };
  }
}

/**
 * Deep diagnostic check for legacy dashboards.
 */
export async function getDetailedHealth(): Promise<SystemHealth> {
  return legacyRequest<SystemHealth>("/health/ready");
}

// ============================================================================
// 4. GENERATION SERVICES
// ============================================================================

export interface GenerationRequest {
  frame_slug: string;
  language: string;
  parameters: Record<string, any>;
}

export interface GenerationResponse {
  id: string;
  text: string;
}

/**
 * Sends a generation request.
 * Adapts the old payload to the canonical generation contract when available.
 */
export async function generateText(
  payload: GenerationRequest
): Promise<GenerationResponse> {
  const gen = (architectApi as any)?.generate;
  if (typeof gen === "function") {
    const result = await gen.call(architectApi, {
      lang: payload.language,
      frame_type: payload.frame_slug,
      frame_payload: payload.parameters,
    });

    return {
      id: String(result?.id ?? `gen_${Date.now()}`),
      text: String(result?.text ?? ""),
    };
  }

  // Fallback: try direct v1 generate route if canonical client is unavailable
  const result = await legacyRequest<any>(`/generate/${payload.language}`, {
    method: "POST",
    body: JSON.stringify({
      frame_type: payload.frame_slug,
      frame_payload: payload.parameters,
    }),
  });

  return {
    id: String(result?.id ?? `gen_${Date.now()}`),
    text: String(result?.text ?? ""),
  };
}
