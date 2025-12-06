// architect_frontend/src/lib/api.ts

/**
 * Thin typed wrapper around the Architect HTTP API.
 *
 * This module is intentionally small and stable:
 * - it hides URL construction and error handling
 * - it exposes typed entry points for the UI
 */

/* -------------------------------------------------------------------------- */
/* Base URL + low-level request helper                                        */
/* -------------------------------------------------------------------------- */

const DEFAULT_API_BASE_PATH = "/abstract_wiki_architect/api";

/**
 * Base URL for the Architect API.
 *
 * Override in your deployment with:
 *   NEXT_PUBLIC_ARCHITECT_API_BASE_URL="https://konnaxion.com/abstract_wiki_architect/api"
 */
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
    const message =
      typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? String((parsed as any).detail)
        : `API request failed with status ${response.status}`;
    throw new ApiError(message, response.status, parsed);
  }

  return parsed as T;
}

/* -------------------------------------------------------------------------- */
/* Shared types (mirroring docs/FRONTEND_API.md, nlg.api)                     */
/* -------------------------------------------------------------------------- */

/**
 * High-level generation controls.
 * Mirrors `nlg.api.GenerationOptions`.
 */
export interface GenerationOptions {
  register?: string | null;       // "neutral", "formal", "informal", etc.
  max_sentences?: number | null;  // upper bound on number of sentences
  discourse_mode?: string | null; // e.g. "intro", "summary"
  seed?: number | null;           // reserved for future stochastic behavior
}

/**
 * Generic semantic frame payload coming from the UI.
 *
 * This is the normalized JSON the backend will convert into an internal
 * frame object (BioFrame, Event, etc.). The exact fields depend on
 * `frame_type` and the semantics layer.
 */
export interface GenericFramePayload {
  frame_type: string; // e.g. "bio", "entity.person", "event.generic", ...
  // Arbitrary additional fields:
  [key: string]: unknown;
}

/**
 * Standard output from all generation calls.
 * Mirrors `nlg.api.GenerationResult` but with `frame` as raw JSON.
 */
export interface GenerationResult {
  text: string;               // final realized text
  sentences: string[];        // sentence-level split
  lang: string;               // language code used
  frame: GenericFramePayload; // original frame JSON
  debug_info?: Record<string, unknown> | null;
}

/**
 * Generic generate request to `/generate`.
 *
 * This is the main entry point the UI should use.
 */
export interface GenerateRequest {
  lang: string;
  frame: GenericFramePayload;
  options?: GenerationOptions | null;
  debug?: boolean;
}

/**
 * Convenience type for a biography frame; this is just a typed
 * specialization of GenericFramePayload with frame_type = "bio".
 * You can extend it in the UI as needed.
 */
export interface BioFramePayload extends GenericFramePayload {
  frame_type: "bio";
  name?: string;
  gender?: string;
  profession_lemma?: string;
  nationality_lemma?: string;
  // Add other bio fields as you expose them in the UI
}

export interface GenerateBioRequest {
  lang: string;
  bio: BioFramePayload;
  options?: GenerationOptions | null;
  debug?: boolean;
}

/* -------------------------------------------------------------------------- */
/* Frames registry types (for dynamic forms / inspectors)                     */
/* -------------------------------------------------------------------------- */

/**
 * Descriptor for a single frame field (for UI forms).
 * This mirrors what the Python `FramesRegistry` exposes.
 */
export interface FrameFieldDescriptor {
  name: string;
  json_type: "string" | "number" | "boolean" | "object" | "array";
  required: boolean;
  description?: string | null;
  enum?: string[] | null;
  default?: unknown;
}

/**
 * Descriptor for a frame type (used to drive the UI for a given frame).
 */
export interface FrameDescriptor {
  frame_type: string; // canonical frame_type, e.g. "bio"
  family: string;     // e.g. "biography", "event", "entity"
  title: string;      // human-friendly name
  description: string;
  fields: FrameFieldDescriptor[];
}

/* -------------------------------------------------------------------------- */
/* Public API surface                                                         */
/* -------------------------------------------------------------------------- */

export interface ArchitectApi {
  /**
   * Health-check endpoint. Optional but useful for wiring tests.
   * Returns true if the backend says it's healthy.
   */
  health(): Promise<boolean>;

  /**
   * List all known frame types and their field schemas.
   * Backed by the Python FramesRegistry.
   */
  listFrames(): Promise<FrameDescriptor[]>;

  /**
   * Fetch the descriptor for a single frame type.
   */
  getFrame(frameType: string): Promise<FrameDescriptor>;

  /**
   * Generic entry point: turn a semantic frame into text.
   * This should be the default for most UI flows.
   */
  generate(request: GenerateRequest): Promise<GenerationResult>;

  /**
   * Convenience wrapper for biography frames.
   * This is backed by the same engine as `generate` but fixes the
   * frame family and input shape to `BioFrame`.
   */
  generateBio(request: GenerateBioRequest): Promise<GenerationResult>;
}

/**
 * Default implementation of the Architect API.
 *
 * Routes are assumed to be:
 *   GET  /health
 *   GET  /frames
 *   GET  /frames/{frame_type}
 *   POST /generate
 *   POST /generate/bio
 *
 * Adjust paths here if your HTTP API uses different routes.
 */
export const architectApi: ArchitectApi = {
  async health(): Promise<boolean> {
    try {
      const data = await request<{ status: string }>("/health");
      return data.status === "ok" || data.status === "healthy";
    } catch {
      return false;
    }
  },

  listFrames(): Promise<FrameDescriptor[]> {
    return request<FrameDescriptor[]>("/frames");
  },

  getFrame(frameType: string): Promise<FrameDescriptor> {
    const encoded = encodeURIComponent(frameType);
    return request<FrameDescriptor>(`/frames/${encoded}`);
  },

  generate(req: GenerateRequest): Promise<GenerationResult> {
    return request<GenerationResult>("/generate", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  generateBio(req: GenerateBioRequest): Promise<GenerationResult> {
    return request<GenerationResult>("/generate/bio", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },
};

/* -------------------------------------------------------------------------- */
/* Convenience re-exports                                                     */
/* -------------------------------------------------------------------------- */

export { API_BASE_URL };
