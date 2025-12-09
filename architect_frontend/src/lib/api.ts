// architect_frontend/src/lib/api.ts

/**
 * Typed wrapper around the Architect HTTP API.
 * Aligned with backend: architect_http_api
 * * Key alignments:
 * - Base URL includes /api/v1 (or root depending on config)
 * - Entities use frame_type/frame_payload (matching schemas/entities.py)
 * - AI uses Command/Patches pattern (matching ai/intent_handler.py)
 * - Generation endpoint handles frame rendering
 * - Frames endpoints handle dynamic registry discovery
 */

/* -------------------------------------------------------------------------- */
/* Base URL + low-level request helper                                        */
/* -------------------------------------------------------------------------- */

// Backend default port is 4000 (from config.py), but often mapped to 8000 in dev.
// We default to root since we updated main.py to serve at root.
const DEFAULT_API_BASE_PATH = "http://127.0.0.1:8000";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL ?? DEFAULT_API_BASE_PATH
).replace(/\/$/, "");

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

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE_URL}${path}`;
  const headers = new Headers(init.headers ?? {});
  
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
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
    const message =
      typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as any).detail)
        : `API request failed with status ${response.status}`;
    throw new ApiError(message, response.status, parsed);
  }

  return parsed as T;
}

/* -------------------------------------------------------------------------- */
/* Frame Registry Types                                                       */
/* -------------------------------------------------------------------------- */

export interface LocalizedLabel {
  text: string;
  translations?: Record<string, string>;
}

export interface FrameTypeMeta {
  frame_type: string;     // e.g. "bio", "event.generic"
  family: string;         // e.g. "entity", "event"
  // Title/Description can be a string (legacy) or LocalizedLabel (new)
  title?: string | LocalizedLabel;
  description?: string | LocalizedLabel;
  status?: "implemented" | "experimental" | "planned";
}

/**
 * Helper to safely extract text from a label that might be a string or object.
 */
export function getLabelText(val: string | LocalizedLabel | undefined | null): string {
  if (!val) return "";
  if (typeof val === "string") return val;
  return val.text || "";
}

/* -------------------------------------------------------------------------- */
/* Language Types (REQUIRED FOR LANGUAGE SELECTOR)                            */
/* -------------------------------------------------------------------------- */

export interface Language {
  code: string; // e.g. "zul"
  name: string; // e.g. "Zulu"
  z_id: string; // e.g. "Z1032"
}

/* -------------------------------------------------------------------------- */
/* Domain Types (Entities)                                                    */
/* Matches architect_http_api.schemas.entities.EntityRead                     */
/* -------------------------------------------------------------------------- */

export interface Entity {
  id: number; // Backend uses Integer ID
  name: string;
  slug?: string;
  lang: string; // e.g. "en", "fr"
  
  // Aligned with backend schemas/entities.py
  frame_type?: string;      // e.g. 'entity.person', 'bio'
  frame_payload?: Record<string, unknown>; // The actual content
  
  short_description?: string;
  notes?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;

  created_at: string;
  updated_at: string;
}

// Matches EntityCreate
export interface EntityCreatePayload {
  name: string;
  slug?: string;
  lang?: string;
  frame_type?: string;
  frame_payload?: Record<string, unknown>;
  short_description?: string;
  tags?: string[];
}

// Matches EntityUpdate
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
/* Matches architect_http_api.schemas.ai (AICommandRequest/Response)          */
/* -------------------------------------------------------------------------- */

export interface AIMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface AIFramePatch {
  path: string;  // e.g. "birth_date" or "relations.0.target"
  value: unknown;
  op?: "replace" | "add" | "remove";  
}

/**
 * Payload sent to POST /ai/intent
 * (Maps to AICommandRequest in backend)
 */
export interface IntentRequest {
  message: string;        // User's natural language input
  lang?: string;
  workspace_slug?: string;    // Context context
  
  // Context: the current state of the frame being edited
  context_frame?: {
    frame_type: string;
    payload: Record<string, unknown>;
  };
  
  debug?: boolean;
}

/**
 * Response from POST /ai/intent
 * (Maps to AICommandResponse in backend)
 */
export interface IntentResponse {
  intent_label: string;
  assistant_messages: AIMessage[];
  patches: AIFramePatch[];      // Proposed changes to the frame
  debug?: Record<string, unknown>;
}

/**
 * Payload sent to POST /ai/suggest-fields
 */
export interface SuggestionRequest {
  frame_type: string;
  current_payload?: Record<string, unknown>;
  field_name?: string;      // If asking for specific field suggestions
  partial_input?: string;     // What the user typed so far
}

export interface SuggestionResponse {
  suggestions: Array<{
    id: string;
    title: string;
    description: string;
    value?: unknown;      // Suggested value
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
  text: string; // The backend returns 'text' (matches pydantic schema)
  sentences?: string[];
  lang?: string;
  frame?: Record<string, unknown>;
  debug_info?: Record<string, unknown>;
  // Fallback for older interface usage
  surface_text?: string;
}

/* -------------------------------------------------------------------------- */
/* Public API surface                                                         */
/* -------------------------------------------------------------------------- */

export interface ArchitectApi {
  /**
   * Health-check endpoint.
   */
  health(): Promise<boolean>;

  // --- Frame Registry (Dynamic Configuration) ---

  /** Get list of all available frame types for menus/dashboards */
  listFrameTypes(): Promise<FrameTypeMeta[]>;

  /** Get the JSON Schema for a specific frame type to build the form */
  getFrameSchema(frameType: string): Promise<Record<string, any>>;

  // --- Language Management (NEW) ---
  
  /** Get list of all supported languages */
  listLanguages(): Promise<Language[]>; // <-- NEW FUNCTION

  // --- Entity Management ---

  listEntities(params?: { search?: string; frame_type?: string }): Promise<Entity[]>;

  getEntity(id: number | string): Promise<Entity>;

  createEntity(data: EntityCreatePayload): Promise<Entity>;

  updateEntity(id: number | string, data: EntityUpdatePayload): Promise<Entity>;

  deleteEntity(id: number | string): Promise<void>;

  // --- AI Features ---

  /**
   * Process natural language instructions to mutate a frame.
   */
  processIntent(req: IntentRequest): Promise<IntentResponse>;

  /**
   * Get field value suggestions.
   */
  getSuggestions(req: SuggestionRequest): Promise<SuggestionResponse>;

  // --- Generation ---

  /**
   * Generate surface text from a frame.
   */
  generate(req: GenerateRequest): Promise<GenerationResult>;
}

/**
 * Implementation
 */
export const architectApi: ArchitectApi = {
  async health(): Promise<boolean> {
    try {
      const data = await request<{ status: string }>("/health");
      return data.status === "ok";
    } catch {
      return false;
    }
  },

  // --- Frames Registry ---

  listFrameTypes(): Promise<FrameTypeMeta[]> {
    return request<FrameTypeMeta[]>("/frames/types");
  },

  getFrameSchema(frameType: string): Promise<Record<string, any>> {
    return request<Record<string, any>>(`/frames/schemas/${frameType}`);
  },
  
  // --- Language Management (IMPLEMENTATION) ---

  listLanguages(): Promise<Language[]> { // <-- NEW IMPLEMENTATION
    return request<Language[]>("/languages");
  },

  // --- Entities ---

  listEntities(params): Promise<Entity[]> {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.frame_type) query.set("frame_type", params.frame_type);
    
    const queryString = query.toString();
    // FIX: Added trailing slash to avoid 307 Redirect -> 422 Error
    return request<Entity[]>(`/entities/?${queryString}`);
  },

  getEntity(id: number | string): Promise<Entity> {
    return request<Entity>(`/entities/${id}`);
  },

  createEntity(data: EntityCreatePayload): Promise<Entity> {
    // FIX: Added trailing slash to avoid 307 Redirect -> 422 Error
    return request<Entity>("/entities/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateEntity(id: number | string, data: EntityUpdatePayload): Promise<Entity> {
    return request<Entity>(`/entities/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  deleteEntity(id: number | string): Promise<void> {
    return request<void>(`/entities/${id}`, {
      method: "DELETE",
    });
  },

  // --- AI ---

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

  // --- Generation ---

  generate(req: GenerateRequest): Promise<GenerationResult> {
    return request<GenerationResult>("/generate", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },
};

export { API_BASE_URL };