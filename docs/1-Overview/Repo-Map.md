# Repo Map

This map lists the **main repo areas you’ll touch most**, grouped by purpose (not exhaustive). It reflects the **current repo layout**, with notes where naming is **legacy** or where behavior is a **target contract** rather than guaranteed in every branch.

## Top-level (conceptual)

* **Backend API (server-side)**
  The backend is where generation, discovery endpoints, and admin/tooling endpoints live. Historically there have been multiple entrypoints; the intent is to converge on a **single canonical API app** and deprecate duplicates over time.

* **Frontend UI (client-side)**
  The UI lives under `architect_frontend/`. It is expected to behave as a single client against the versioned API (see `architect_frontend/src/lib/api.ts` for the central API wrapper).

* **Data (lexicon + configuration)**
  - Lexicon data is stored per language under `data/lexicon/{LANG}/...`.
  - `{LANG}` is typically the **two-letter ISO code** for internal directories (e.g., `data/lexicon/en/`).  
    If you also maintain external/public identifiers, treat them as a **mapped surface**, not a directory rule.
  - Key mappings and configuration live under `data/config/` (e.g., `data/config/iso_to_wiki.json`).

* **Grammars (grammar sources + compiled artifact)**
  Grammar sources live under `gf/` (abstract syntax + per-language grammars such as `gf/Wiki{WikiCode}.gf`). A compiled **PGF** artifact is typically generated under `gf/` as part of the build.  
  Note: some filenames may still carry **legacy naming** from the project’s earlier name.

* **Generated sources (build outputs)**
  Generated language sources are produced under `generated/`. If there are multiple mirrors (e.g., an older `gf/generated/...` layout), treat `generated/` as the **preferred** source of truth and regard mirrors as legacy compatibility.

* **Tools & utilities (operators + QA + data ops)**
  - `tools/` contains operator-facing tools (including QA suites).
  - `utils/` contains helper scripts and data operations.
  This split may evolve; avoid hardcoding paths in automation where possible.  
  The Tools Registry is served by the backend router (commonly referenced under `app/adapters/api/routers/...`).

* **Deployment**
  Deployment wiring typically lives in `deploy/` (reverse proxy config, etc.) and `docker-compose.yml` (services wiring).

* **Project launcher / orchestrator**
  `manage.py` is the main “project command” entrypoint used for common flows (build/clean/align), depending on how your repo is operated.

---

## Suggested tree view (high level)

* `app/` — Backend API (canonical entrypoint under `app/adapters/api/...`)
* `architect_frontend/` — Frontend UI
* `data/`
  * `data/lexicon/{LANG}/...` — Lexicon per language
  * `data/config/...` — Configuration + mappings (e.g., `iso_to_wiki.json`)
* `gf/` — Grammar sources + compiled grammar artifact (PGF)
* `generated/` — Preferred generated sources
* `tools/` — Operator tools / QA
* `utils/` — Data ops + helper scripts
* `deploy/` — Reverse proxy configuration
* `docker-compose.yml` — Services wiring
* `manage.py` — Orchestration entrypoint