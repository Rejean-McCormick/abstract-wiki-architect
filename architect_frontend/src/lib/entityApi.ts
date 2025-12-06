// architect_frontend/src/lib/entityApi.ts

/**
 * Thin typed client for the Architect HTTP API "entities" endpoints.
 *
 * All paths here are relative to the Architect base path, which defaults to
 * `/abstract_wiki_architect/api` but can be overridden with
 * NEXT_PUBLIC_ARCHITECT_API_BASE.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE ?? "/abstract_wiki_architect/api";

export type EntityId = string;

export interface EntitySummary {
  id: EntityId;
  slug: string;
  label: string;
  frame_type: string;
  lang: string;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface EntityDetail extends EntitySummary {
  /**
   * The stored frame payload. Shape depends on `frame_type`, so we keep it
   * generic here and let frame-specific components refine it.
   */
  payload: Record<string, unknown>;
}

export interface EntityListFilters {
  frame_type?: string;
  lang?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface PagedEntityList {
  items: EntitySummary[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Payload used when creating a new entity.
 *
 * `slug` is intended to be unique and URL-safe; the backend should enforce
 * uniqueness and return a validation error if needed.
 */
export interface CreateEntityPayload {
  slug: string;
  label: string;
  frame_type: string;
  lang: string;
  payload: Record<string, unknown>;
}

/**
 * Payload used when updating an existing entity.
 * All fields are optional and will be merged server-side.
 */
export interface UpdateEntityPayload {
  slug?: string;
  label?: string;
  lang?: string;
  payload?: Record<string, unknown>;
  frame_type?: string;
}

/**
 * Minimal shape for error payloads returned by the API.
 * FastAPI-style errors typically use `{"detail": ...}`.
 */
export interface ApiErrorPayload {
  detail?: unknown;
  error?: unknown;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

/**
 * Internal helper: JSON fetch with consistent error handling.
 */
async function fetchJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init.headers ?? {}),
  };

  const response = await fetch(url, { ...init, headers });

  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // leave as raw text if JSON parsing fails
      data = text;
    }
  }

  if (!response.ok) {
    const payload: ApiErrorPayload | undefined =
      data && typeof data === "object" ? (data as ApiErrorPayload) : undefined;

    const message =
      (payload?.detail as string | undefined) ??
      (payload?.error as string | undefined) ??
      `API error ${response.status}`;

    throw new ApiError(response.status, message, payload);
  }

  return data as T;
}

/**
 * Build a query string from optional filters.
 */
function buildQuery(filters?: EntityListFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();

  if (filters.frame_type) params.set("frame_type", filters.frame_type);
  if (filters.lang) params.set("lang", filters.lang);
  if (filters.search) params.set("search", filters.search);
  if (
    typeof filters.limit === "number" &&
    Number.isFinite(filters.limit)
  ) {
    params.set("limit", String(filters.limit));
  }
  if (
    typeof filters.offset === "number" &&
    Number.isFinite(filters.offset)
  ) {
    params.set("offset", String(filters.offset));
  }

  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

/**
 * List entities with optional filtering and pagination.
 */
export async function listEntities(
  filters?: EntityListFilters,
): Promise<PagedEntityList> {
  const query = buildQuery(filters);
  return fetchJson<PagedEntityList>(`/entities${query}`, {
    method: "GET",
  });
}

/**
 * Fetch a single entity by ID.
 */
export async function getEntity(id: EntityId): Promise<EntityDetail> {
  const encodedId = encodeURIComponent(id);
  return fetchJson<EntityDetail>(`/entities/${encodedId}`, {
    method: "GET",
  });
}

/**
 * Create a new entity.
 */
export async function createEntity(
  payload: CreateEntityPayload,
): Promise<EntityDetail> {
  return fetchJson<EntityDetail>("/entities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Update an existing entity. Fields not included in `payload`
 * are left unchanged on the server.
 */
export async function updateEntity(
  id: EntityId,
  payload: UpdateEntityPayload,
): Promise<EntityDetail> {
  const encodedId = encodeURIComponent(id);
  return fetchJson<EntityDetail>(`/entities/${encodedId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/**
 * Delete an entity by ID.
 */
export async function deleteEntity(id: EntityId): Promise<void> {
  const encodedId = encodeURIComponent(id);
  await fetchJson<unknown>(`/entities/${encodedId}`, {
    method: "DELETE",
  });
}

/**
 * Convenience helper used by forms:
 * - if `id` is null/undefined → create
 * - otherwise → update
 *
 * Returns the up-to-date entity detail from the server.
 */
export async function saveEntity(
  id: EntityId | null | undefined,
  payload: CreateEntityPayload | UpdateEntityPayload,
): Promise<EntityDetail> {
  if (!id) {
    // Treat as "create"; payload must satisfy CreateEntityPayload at call site.
    return createEntity(payload as CreateEntityPayload);
  }
  return updateEntity(id, payload as UpdateEntityPayload);
}
