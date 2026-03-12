# 🛠️ Developer Tools & Unified Launch System

**SemantiK Architect v2.5**

## 1. The "God Mode" Launcher (`Run-Architect.ps1`)

The **Unified Orchestrator** is a PowerShell script that manages the hybrid environment (Windows Frontend + Linux/WSL Backend) automatically.

**Location:** `Run-Architect.ps1` (Root)

### Why it exists

1. **Zombie killing:** It forcefully kills lingering `uvicorn` (Linux) or `node` (Windows) processes holding ports 8000 or 3000 to prevent address errors.
2. **Window Management:** It spawns **3 separate visible windows** for simultaneous monitoring of API, Worker, and Frontend logs.
3. **Consistency:** It delegates startup arguments to `manage.py`, ensuring the environment matches the system’s canonical configuration.

### Usage

Right-click the file and select **"Run with PowerShell"**, or run from the terminal:

```powershell
.\Run-Architect.ps1
````

### Process Flow

* **Host (PowerShell):** Performs cleanup, verifies Docker/Redis, and spawns child windows.
* **Terminal 1 (WSL):** API Backend via `python3 manage.py start-api`.
* **Terminal 2 (WSL):** Background Worker via `python3 manage.py start-worker`.
* **Terminal 3 (Windows Native):** Frontend via `npm run dev`.

---

## 2. The Developer Console (`/dev`)

A dedicated dashboard for immediate system health verification and smoke testing.

**URL:** `http://localhost:3000/semantik_architect/dev`

### Features

* **System Heartbeat:** Real-time component status (ready/healthy) from the backend health endpoint.

  * **Broker:** Redis connection status.
  * **Storage:** Lexicon file accessibility.
  * **Engine:** PGF binary loading status.
* **One-Click Smoke Test:** Sends a standard test payload to verify end-to-end generation without manual `curl`.
* **Command Cheat Sheet:** Quick reference for common restart commands.

---

## 3. The System Tools Dashboard (`/tools`)

A GUI wrapper for backend maintenance scripts, allowing operational tasks to be performed without a WSL terminal.

**URL:** `http://localhost:3000/semantik_architect/tools`

### How it works (authoritative)

1. **Request:** The frontend sends a tool run request to `POST /api/v1/tools/run`:

   * `tool_id`: allowlisted identifier (e.g., `language_health`, `compile_pgf`)
   * `args`: optional argv-style list (backend validates/filters)
   * `dry_run`: if true, returns the resolved command without executing
2. **Validation:** The backend checks `tool_id` against a strict **Allowlist Registry** and validates flags/arg-shapes per-tool (prevents flag injection and arbitrary execution).
3. **Execution:** The backend spawns a subprocess **from the configured repo root** (`FILESYSTEM_REPO_PATH`) with environment injection (`PYTHONPATH`, `PYTHONUNBUFFERED`, `TOOL_TRACE_ID`).
4. **Result envelope:** The backend returns a stable response envelope including:

   * `trace_id`, `success`, `command`
   * `stdout`/`stderr` (plus back-compat `output`/`error`)
   * `exit_code`, `duration_ms`
   * `args_received` / `args_accepted` / `args_rejected`
   * `truncation` metadata (stdout/stderr)
   * `events` lifecycle telemetry (INFO/WARN/ERROR steps)

### Security & operational guarantees

* **No arbitrary execution:** only allowlisted tool IDs can run.
* **No aliases / no remaps:** tool IDs are canonical; legacy IDs are rejected (404 from the registry lookup).
* **Repo confinement:** tool targets must resolve under `FILESYSTEM_REPO_PATH`.
* **Timeouts:** per-tool timeout enforced; default via `ARCHITECT_TOOLS_DEFAULT_TIMEOUT_SEC`.
* **Output truncation:** enforced via `ARCHITECT_TOOLS_MAX_OUTPUT_CHARS`.
* **AI gating:** AI tools return 403 unless `ARCHITECT_ENABLE_AI_TOOLS=1`.
* **Auth:** tools router is protected by API key (`verify_api_key`) and is treated as **admin-only**.

### Available Dashboard Tool Mappings (examples)

| Tool ID           | Action Taken                                                        |
| ----------------- | ------------------------------------------------------------------- |
| `language_health` | Language health/diagnostics utility (compile/API checks).           |
| `compile_pgf`     | Triggers the build orchestrator to compile/link `semantik_architect.pgf`. |
| `harvest_lexicon` | Runs the lexicon harvester (subcommands: `wordnet` or `wikidata`).  |
| `run_judge`       | Executes golden-standard regression checks (AI Judge integration).  |

Note: the UI registry of tools (labels/categories/parameter docs) must stay in sync with backend `TOOL_REGISTRY` tool IDs and their allowed flags.

---

## 4. Backend Orchestration Details

The developer interfaces above rely on the following infrastructure:

* **Secure Tools Router:** `app/adapters/api/routers/tools.py`

  * Implements `/api/v1/tools/registry` and `/api/v1/tools/run`
  * Enforces allowlist registry + argument policy + truncation + timeouts + telemetry
* **Tool Registry:** `TOOL_REGISTRY` maps safe tool IDs to physical scripts/tests and their execution policy:

  * allowed flags
  * whether positionals are permitted
  * flag value-shape rules (single-value vs multi-value)
  * AI gating (`requires_ai_enabled`)
* **Repo Root Standardization:** tools always execute with `cwd = FILESYSTEM_REPO_PATH` and `PYTHONPATH` injected accordingly.
* **Unified Commander:** `manage.py` remains the canonical orchestrator for lifecycle operations; external launchers should delegate to it rather than re-implement environment logic.


