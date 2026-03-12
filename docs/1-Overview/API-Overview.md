# API Overview

SemantiK Architect is accessed through a **versioned HTTP API**. The **stable convention** is to keep client-facing endpoints under the **`/api/v1`** prefix.

> Note: some deployments also mount the UI/API under a **base path**. Treat the base path as a deployment choice, not an API rule.

## Base path (deployment)

In packaged deployments, the UI may be served under a base path and the API is served under:

- **`{BASE_PATH}/api/v1`**

Example (legacy): UI under `/abstract_wiki_architect`, API under `/abstract_wiki_architect/api/v1`.

## Public vs admin endpoints (auth boundary)

- **Public read endpoints** may be accessible without admin credentials (deployment-configurable).
- **Admin endpoints** require authentication (API key/token).
- The **Tools API** is **admin-only**.

## Core generation endpoint (meaning → text)

### `POST /api/v1/generate/{lang}`

- `lang` is passed as a **path parameter**.

**Two supported input shapes (conceptually):**
- **Strict / production path:** a flat “frame” JSON (example: `BioFrame`).
- **Prototype / experimental path:** a recursive Ninai-style tree (`UniversalNode`).

**Response shape (stable envelope):**
- `surface_text`: the generated text
- `meta`: lightweight provenance (e.g., engine/adapter/strategy)

## Session/context support (multi-sentence coherence)

Requests may include a session identifier header to enable discourse behavior across sentences (example: `X-Session-ID`).

## Discovery endpoints (used by the UI)

Some deployments/UI flows rely on discovery endpoints such as:
- `GET /api/v1/languages` returning a list of languages (for a language selector).
- `GET /api/v1/entities/...` returning a defined entity schema (for browsing/search).

If your current build does not expose these yet, treat them as the **target contract** for UI/API alignment.

## Tools API (GUI-driven operations; admin-only)

Tools are executed via an **allowlisted registry** (no arbitrary command execution).

- `GET /api/v1/tools/registry`: lists tool metadata
- `POST /api/v1/tools/run`: runs a tool by `tool_id` and returns a stable execution envelope (trace/output/events/exit code)

**Security note:** do not pass secrets in tool args; args may be echoed in responses and/or surfaced in UI logs.