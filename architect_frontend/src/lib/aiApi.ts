// architect_frontend/src/lib/aiApi.ts

/**
 * Client utilities for the Abstract Wiki Architect AI endpoints.
 *
 * This module wraps the HTTP AI API (intent → frame patches, explanations, etc.)
 * and exposes small, typed functions that the frontend can call.
 */

const ARCHITECT_API_BASE =
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE ?? '/abstract_wiki_architect/api';

export interface APIErrorPayload {
  code: string;
  message: string;
  details?: unknown;
}

export class ArchitectAPIError extends Error {
  readonly status: number;
  readonly payload?: APIErrorPayload;

  constructor(status: number, payload?: APIErrorPayload) {
    super(payload?.message ?? `Architect API error (${status})`);
    this.name = 'ArchitectAPIError';
    this.status = status;
    this.payload = payload;
  }
}

/**
 * Common context for a frame that AI should see.
 */
export interface AIFrameContext {
  frame_type: string;
  frame: Record<string, unknown>;
  lang?: string;
}

/**
 * Patch describing how to update or create a frame.
 */
export interface FramePatch {
  frame_type: string;
  /**
   * "new" → create a new frame instance.
   * "existing" → patch an existing stored frame (frame_id required).
   */
  target: 'new' | 'existing';
  frame_id?: string;
  patch: Record<string, unknown>;
  confidence?: number;
}

/**
 * Lightweight chat-style message used for AI explanations / traces.
 */
export interface ChatMessage {
  role: 'system' | 'assistant' | 'user';
  content: string;
}

/**
 * Request for the AI to interpret an utterance and propose frame edits.
 */
export interface AISuggestFramesRequest {
  utterance: string;
  context_frames?: AIFrameContext[];
  entity_id?: string;
}

/**
 * Response from the AI suggesting frame edits.
 */
export interface AISuggestFramesResponse {
  frame_patches: FramePatch[];
  messages?: ChatMessage[];
}

/**
 * Request for AI explanations of a generation.
 */
export interface ExplainGenerationRequest {
  lang: string;
  frame_type: string;
  frame: Record<string, unknown>;
  text: string;
  debug_info?: Record<string, unknown>;
  user_goal?: string;
}

/**
 * Explanation item as normalized by the backend.
 */
export type ExplanationKind =
  | 'general'
  | 'coverage'
  | 'style'
  | 'linguistic'
  | 'debug'
  | 'other';

export interface ExplanationItem {
  kind: ExplanationKind;
  title: string;
  body: string;
  score?: number;
}

/**
 * Response containing explanations for a generation.
 */
export interface ExplainGenerationResponse {
  explanations: ExplanationItem[];
}

/**
 * Internal helper to build full URLs against the AI API.
 */
function aiUrl(path: string): string {
  const trimmedBase = ARCHITECT_API_BASE.replace(/\/+$/, '');
  const trimmedPath = path.replace(/^\/+/, '');
  return `${trimmedBase}/${trimmedPath}`;
}

/**
 * Internal helper to parse responses and normalize errors.
 */
async function parseResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type') ?? '';

  if (!res.ok) {
    if (contentType.includes('application/json')) {
      const body = (await res.json()) as { error?: APIErrorPayload };
      throw new ArchitectAPIError(res.status, body.error);
    }

    throw new ArchitectAPIError(res.status, {
      code: 'HTTP_ERROR',
      message: `HTTP ${res.status} from AI API`,
    });
  }

  if (!contentType.includes('application/json')) {
    // Empty body or unexpected content-type; treat as error for AI endpoints.
    throw new ArchitectAPIError(res.status, {
      code: 'INVALID_CONTENT_TYPE',
      message: 'Expected JSON response from AI API',
    });
  }

  return (await res.json()) as T;
}

/**
 * Call the AI endpoint that suggests frame patches from a natural-language utterance.
 *
 * Expected backend route:
 *   POST /ai/suggest_frames
 *
 * Request body:
 *   {
 *     "utterance": string,
 *     "context_frames": [{ frame_type, frame, lang? }],
 *     "entity_id": string | null
 *   }
 *
 * Response body:
 *   {
 *     "frame_patches": [...],
 *     "messages": [...]
 *   }
 */
export async function suggestFramesFromUtterance(
  request: AISuggestFramesRequest,
  signal?: AbortSignal,
): Promise<AISuggestFramesResponse> {
  const res = await fetch(aiUrl('/ai/suggest_frames'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  });

  return parseResponse<AISuggestFramesResponse>(res);
}

/**
 * Call the AI endpoint that explains how a given generation was produced.
 *
 * Expected backend route:
 *   POST /ai/explain_generation
 *
 * Request body:
 *   {
 *     "lang": string,
 *     "frame_type": string,
 *     "frame": {...},
 *     "text": string,
 *     "debug_info"?: {...},
 *     "user_goal"?: string
 *   }
 *
 * Response body:
 *   {
 *     "explanations": [...]
 *   }
 */
export async function explainGeneration(
  request: ExplainGenerationRequest,
  signal?: AbortSignal,
): Promise<ExplainGenerationResponse> {
  const res = await fetch(aiUrl('/ai/explain_generation'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  });

  return parseResponse<ExplainGenerationResponse>(res);
}
