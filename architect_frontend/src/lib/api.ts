// architect_frontend/src/lib/api.ts

/**
 * Typed wrapper around the Architect HTTP API.
 *
 * Goals:
 * - Default base URL targets /api/v1
 * - Robust against common backend variants during migration:
 * - health: /health, /health/live
 * - schemas: /schemas/frames/:type, /frames/schemas/:type
 * - generate: /generate/:lang (new), /generate (legacy)
 * - languages: strings (legacy) vs objects (v2.1)
 */

const DEFAULT_API_BASE_URL =
  process.env.NODE_ENV === "production"
    ? "/abstract_wiki_architect/api/v1"
    : "http://127.0.0.1:8000/api/v1";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

const DEV_API_KEY = process.env.NEXT_PUBLIC_ARCHITECT_API_KEY;

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function joinUrl(base: string, path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

function extractErrorMessage(parsed: unknown, status: number): string {
  if (typeof parsed === "string" && parsed.trim()) return parsed;
  if (parsed && typeof parsed === "object") {
    const obj = parsed as any;
    if (typeof obj.detail === "string" && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === "string" && obj.message.trim()) return obj.message;
    if (typeof obj.error === "string" && obj.error.trim()) return obj.error;
  }
  return `API request failed with status ${status}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = joinUrl(API_BASE_URL, path);

  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  // Dev-only header injection (do not rely on this for production security).
  if (DEV_API_KEY && !headers.has("x-api-key")) headers.set("x-api-key", DEV_API_KEY);

  if (
    init.body != null &&
    typeof init.body !== "string" &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, { ...init, headers });

  let parsed: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
  } else {
    try {
      parsed = await response.text();
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    console.error("API Request Failed:", url, response.status, parsed);
    throw new ApiError(extractErrorMessage(parsed, response.status), response.status, parsed);
  }

  return parsed as T;
}

async function requestWithFallback<T>(paths: string[], init?: RequestInit): Promise<T> {
  let lastErr: unknown = null;
  for (const p of paths) {
    try {
      return await request<T>(p, init);
    } catch (e) {
      lastErr = e;
      if (e instanceof ApiError && e.status !== 404) break;
    }
  }
  throw lastErr;
}

/* -------------------------------------------------------------------------- */
/* Frame Registry Types                                                       */
/* -------------------------------------------------------------------------- */

export interface LocalizedLabel {
  text: string;
  translations?: Record<string, string>;
}

export interface FrameTypeMeta {
  frame_type: string; // e.g. "bio", "event.generic"
  family: string; // e.g. "entity", "event"
  title?: string | LocalizedLabel;
  description?: string | LocalizedLabel;
  status?: "implemented" | "experimental" | "planned";
}

/**
 * Helper to safely extract text from a label that might be a string or object.
 */
export function getLabelText(
  val: string | LocalizedLabel | undefined | null,
): string {
  if (!val) return "";
  if (typeof val === "string") return val;
  return val.text || "";
}

/* -------------------------------------------------------------------------- */
/* Language Types                                                             */
/* -------------------------------------------------------------------------- */

export interface Language {
  code: string; // e.g. "zul" (ISO 639-3) or "en" depending on backend
  name: string; // e.g. "Zulu"
  z_id: string; // e.g. "Z1032"
}

/* -------------------------------------------------------------------------- */
/* Domain Types (Entities)                                                    */
/* -------------------------------------------------------------------------- */

export interface Entity {
  id: number;
  name: string;
  slug?: string;
  lang: string;

  frame_type?: string;
  frame_payload?: Record<string, unknown>;

  short_description?: string;
  notes?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;

  created_at: string;
  updated_at: string;
}

export interface EntityCreatePayload {
  name: string;
  slug?: string;
  lang?: string;
  frame_type?: string;
  frame_payload?: Record<string, unknown>;
  short_description?: string;
  tags?: string[];
}

export interface EntityUpdatePayload {
  name?: string;
  slug?: string;
  lang?: string;
  frame_type?: string;
  frame_payload?: Record<string, unknown>;
  short_description?: string;
  notes?: string;
  tags?: string[];
}

/* -------------------------------------------------------------------------- */
/* AI / Intelligence Types                                                    */
/* -------------------------------------------------------------------------- */

export interface AIMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface AIFramePatch {
  path: string;
  value: unknown;
  op?: "replace" | "add" | "remove";
}

export interface IntentRequest {
  message: string;
  lang?: string;
  workspace_slug?: string;

  context_frame?: {
    frame_type: string;
    payload: Record<string, unknown>;
  };

  debug?: boolean;
}

export interface IntentResponse {
  intent_label: string;
  assistant_messages: AIMessage[];
  patches: AIFramePatch[];
  debug?: Record<string, unknown>;
}

export interface SuggestionRequest {
  frame_type: string;
  current_payload?: Record<string, unknown>;
  field_name?: string;
  partial_input?: string;
}

export interface SuggestionResponse {
  suggestions: Array<{
    id: string;
    title: string;
    description: string;
    value?: unknown;
    score?: number;
  }>;
}

/* -------------------------------------------------------------------------- */
/* Generation Types (NLG)                                                     */
/* -------------------------------------------------------------------------- */

export interface GenerateRequest {
  lang: string;
  frame_type: string;
  frame_payload: Record<string, unknown>;
  options?: Record<string, unknown>;
}

export interface GenerationResult {
  text: string;
  sentences?: string[];
  lang?: string;
  frame?: Record<string, unknown>;
  debug_info?: Record<string, unknown>;
  surface_text?: string;
}

/* -------------------------------------------------------------------------- */
/* Public API surface                                                         */
/* -------------------------------------------------------------------------- */

export interface ArchitectApi {
  health(): Promise<boolean>;

  listFrameTypes(): Promise<FrameTypeMeta[]>;
  getFrameSchema(frameType: string): Promise<Record<string, any>>;

  listLanguages(): Promise<Language[]>;

  listEntities(params?: { search?: string; frame_type?: string }): Promise<Entity[]>;
  getEntity(id: number | string): Promise<Entity>;
  createEntity(data: EntityCreatePayload): Promise<Entity>;
  updateEntity(id: number | string, data: EntityUpdatePayload): Promise<Entity>;
  deleteEntity(id: number | string): Promise<void>;

  processIntent(req: IntentRequest): Promise<IntentResponse>;
  getSuggestions(req: SuggestionRequest): Promise<SuggestionResponse>;

  generate(req: GenerateRequest): Promise<GenerationResult>;
}

/* -------------------------------------------------------------------------- */
/* Implementation                                                             */
/* -------------------------------------------------------------------------- */

function normalizeFrameTypes(raw: unknown): FrameTypeMeta[] {
  if (!Array.isArray(raw)) return [];

  return raw
    .map((item: any) => {
      // Preferred shape (target contract)
      if (item && typeof item === "object" && typeof item.frame_type === "string") {
        return item as FrameTypeMeta;
      }

      // Common fallback shape seen in placeholder registries: { id, label, description, schema_ref, icon? }
      if (item && typeof item === "object" && typeof item.id === "string") {
        const id: string = item.id;
        const family =
          typeof item.family === "string"
            ? item.family
            : id.includes(".")
              ? id.split(".")[0]
              : "frame";

        return {
          frame_type: id,
          family,
          title: typeof item.label === "string" ? item.label : id,
          description: typeof item.description === "string" ? item.description : "",
          status: "implemented",
        } satisfies FrameTypeMeta;
      }

      return null;
    })
    .filter(Boolean) as FrameTypeMeta[];
}

function normalizeLanguages(raw: unknown): Language[] {
  if (!Array.isArray(raw)) return [];
  // [FIX] Handle legacy backend returning string[] instead of Language[]
  return raw.map((item: any) => {
    if (typeof item === "string") {
      return { code: item, name: item, z_id: "" };
    }
    if (item && typeof item === "object" && item.code) {
      return item as Language;
    }
    return null;
  }).filter(Boolean) as Language[];
}

export const architectApi: ArchitectApi = {
  async health(): Promise<boolean> {
    try {
      // Prefer the newer liveness endpoint; fall back to older /health if present.
      const data = await requestWithFallback<any>(["/health/live", "/health"]);
      return (data?.status ?? "") === "ok";
    } catch {
      return false;
    }
  },

  async listFrameTypes(): Promise<FrameTypeMeta[]> {
    const raw = await request<unknown>("/frames/types");
    return normalizeFrameTypes(raw);
  },

  getFrameSchema(frameType: string): Promise<Record<string, any>> {
    const ft = encodeURIComponent(frameType);
    return requestWithFallback<Record<string, any>>([
      `/schemas/frames/${ft}`,
      `/frames/schemas/${ft}`,
    ]);
  },

  async listLanguages(): Promise<Language[]> {
    // Prefer no trailing slash; FastAPI may redirect; fetch follows 307 for GET.
    const raw = await request<unknown>("/languages");
    return normalizeLanguages(raw);
  },

  listEntities(params): Promise<Entity[]> {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.frame_type) query.set("frame_type", params.frame_type);

    const qs = query.toString();
    return request<Entity[]>(`/entities/${qs ? `?${qs}` : ""}`);
  },

  getEntity(id: number | string): Promise<Entity> {
    return request<Entity>(`/entities/${encodeURIComponent(String(id))}`);
  },

  createEntity(data: EntityCreatePayload): Promise<Entity> {
    return request<Entity>("/entities/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateEntity(id: number | string, data: EntityUpdatePayload): Promise<Entity> {
    return request<Entity>(`/entities/${encodeURIComponent(String(id))}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  deleteEntity(id: number | string): Promise<void> {
    return request<void>(`/entities/${encodeURIComponent(String(id))}`, {
      method: "DELETE",
    });
  },

  processIntent(req: IntentRequest): Promise<IntentResponse> {
    return request<IntentResponse>("/ai/intent", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  getSuggestions(req: SuggestionRequest): Promise<SuggestionResponse> {
    return request<SuggestionResponse>("/ai/suggest-fields", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  async generate(req: GenerateRequest): Promise<GenerationResult> {
    // Preferred (new): POST /generate/{lang_code}
    const lang = encodeURIComponent(req.lang);
    try {
      // [FIX] Flatten payload for Strict Path (BioFrame)
      // The backend expects flat keys (name, profession) at the root, 
      // NOT nested in 'frame_payload'.
      const flatBody = {
        frame_type: req.frame_type,
        ...req.frame_payload,
        ...req.options,
      };

      return await request<GenerationResult>(`/generate/${lang}`, {
        method: "POST",
        body: JSON.stringify(flatBody),
      });
    } catch (e) {
      // Backward-compatible fallback (legacy): POST /generate with frame_slug/language/fields.
      if (e instanceof ApiError && e.status === 404) {
        const legacy = await request<any>("/generate", {
          method: "POST",
          body: JSON.stringify({
            frame_slug: req.frame_type,
            language: req.lang,
            fields: req.frame_payload,
            options: req.options ?? {},
          }),
        });

        // Best-effort normalization to GenerationResult
        if (legacy && typeof legacy === "object") {
          const text = legacy.text ?? legacy.surface_text ?? "";
          return {
            text: String(text ?? ""),
            sentences: Array.isArray(legacy.sentences) ? legacy.sentences : undefined,
            lang: legacy.lang ?? legacy.language ?? req.lang,
            frame: legacy.frame ?? undefined,
            debug_info: legacy.debug_info ?? legacy.debug ?? undefined,
            surface_text: legacy.surface_text ?? undefined,
          };
        }
      }
      throw e;
    }
  },
};

export { API_BASE_URL };