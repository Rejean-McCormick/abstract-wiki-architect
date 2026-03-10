# 🧰 Tools Dashboard & API

**SemantiK Architect**

This document defines the canonical architecture for the **Tools Dashboard** (`/semantik_architect/tools`) and the secure **Tools API** (`/api/v1/tools/*`).

It covers:

1. The dashboard’s role in the system
2. The backend API contract
3. The security model
4. The workflow-oriented tool filtering model
5. The relationship between frontend registry metadata and backend execution policy
6. Validation and maintenance rules

---

## 1. Purpose

The Tools Dashboard exists to provide a **safe, operator-friendly control surface** for running approved maintenance, build, QA, and diagnostics tasks without exposing arbitrary shell execution.

The dashboard is not a generic terminal. It is a **curated orchestration UI** over a backend allowlist registry.

Core goals:

- expose only approved tool IDs
- enforce argument policy
- preserve repo-root confinement
- provide consistent lifecycle and output logs
- separate **normal workflows** from **power-user / debug tooling**
- guide operators with **recommended workflows**, not just a flat inventory

---

## 2. Canonical Paths

### 2.1 Frontend route

The Tools Dashboard is served at:

```text
/semantik_architect/tools
````

### 2.2 API base

The Tools API is served under:

```text
/semantik_architect/api/v1
```

Canonical tools endpoints:

```text
GET  /api/v1/tools/registry
POST /api/v1/tools/run
```

### 2.3 Repo execution root

All tool execution must be confined to:

```text
FILESYSTEM_REPO_PATH
```

The backend must resolve tool targets relative to this repo root and reject paths outside it.

---

## 3. Design Principles

### 3.1 Workflow-first UI

The dashboard must be organized around **operator intent**, not backend implementation categories.

The primary selector is:

```text
Workflow / Tool Set
```

This is the main navigation model for the page.

### 3.2 Power user is a visibility modifier

**Power user** is **not** a workflow.

It is a visibility switch that reveals hidden, debug, test, internal, heavy, or advanced tools within the currently selected workflow.

### 3.3 Curated normal mode

Normal mode must show a curated subset of tools that support common workflows.

Hidden tools, raw tests, scanners, and risky internals should remain out of sight unless Power user is enabled.

### 3.4 Recommended workflow guidance

When a workflow filter is selected, the page must display a **Recommended workflow** card that explains the normal step order for that tool set.

The dashboard should help users answer:

* what should I run first?
* what should I run next?
* which tools are normal vs optional vs recovery-only?

---

## 4. Backend API Contract

## 4.1 `GET /api/v1/tools/registry`

Returns the safe tool registry for the dashboard.

Each entry must describe:

* canonical `tool_id`
* label
* category
* description
* execution policy
* allowed flags
* positionals policy
* hidden/internal/heavy/test metadata
* workflow metadata used by the dashboard

### 4.1.1 Canonical metadata shape

Recommended registry metadata shape:

```json
{
  "tool_id": "language_health",
  "label": "Language Health",
  "category": "health",
  "description": "Compile + runtime health checks for one or more languages.",
  "hidden": false,
  "internal": false,
  "heavy": false,
  "is_test": false,
  "requires_ai_enabled": false,
  "allowed_flags": ["--mode", "--langs", "--json", "--verbose", "--fast"],
  "allow_positionals": false,
  "workflow_tags": ["recommended", "languageIntegration", "qaValidation"],
  "normal_path": true,
  "power_user_only": false,
  "recommended_order": 50
}
```

### 4.1.2 Workflow metadata

The backend registry should provide workflow-oriented metadata so the frontend does not need to hardcode all tool grouping logic.

Recommended fields:

* `workflow_tags: string[]`
* `normal_path: boolean`
* `power_user_only: boolean`
* `recommended_order: number`

These fields are presentation metadata only. They do **not** affect execution permissions.

---

## 4.2 `POST /api/v1/tools/run`

Executes a registered tool using a safe request envelope.

Request shape:

```json
{
  "tool_id": "language_health",
  "args": ["--mode", "both", "--langs", "en", "fr", "--json", "--verbose"],
  "dry_run": false
}
```

Response shape must include:

* trace ID
* lifecycle events
* stdout
* stderr
* exit code
* timing metadata
* argument validation warnings/errors

Example response envelope:

```json
{
  "trace_id": "uuid",
  "started_at": "2026-03-07T13:07:04.674490Z",
  "duration_ms": 68743,
  "lifecycle": [
    { "level": "INFO", "event": "request_received", "message": "Tool run request received" },
    { "level": "INFO", "event": "tool_validated", "message": "Tool found in registry" },
    { "level": "INFO", "event": "args_validated", "message": "All arguments accepted." },
    { "level": "INFO", "event": "process_spawned", "message": "Executing command with timeout 1800s" },
    { "level": "INFO", "event": "process_exited", "message": "Process exited with code 0" }
  ],
  "stdout": "...",
  "stderr": "...",
  "exit_code": 0
}
```

---

## 5. Security Model

The Tools API is **admin-only** and must never allow arbitrary command execution.

Required protections:

* strict allowlist registry
* canonical tool IDs only
* no aliases or remaps
* repo-root confinement under `FILESYSTEM_REPO_PATH`
* flag allowlisting
* optional flag value-shape validation
* per-tool timeout enforcement
* output truncation
* AI tool gating
* authenticated access

### 5.1 Required rules

* only tool IDs present in `TOOL_REGISTRY` may execute
* only allowlisted flags may pass
* disallowed positionals must be rejected
* commands must execute with `cwd = FILESYSTEM_REPO_PATH`
* tool targets resolving outside the repo root must be rejected
* AI tools must return 403 unless explicitly enabled
* output must be truncated to configured limits
* the router must record lifecycle telemetry for every run

---

## 6. Dashboard UX Model

## 6.1 Main controls

The dashboard should expose:

* search input
* **Workflow / Tool Set** dropdown
* **Power user** checkbox
* optional dry-run toggle
* advanced filters (wired only, show tests, show internal, show heavy, show legacy)
* health refresh action
* visible/wired counts

### 6.1.1 Main workflow dropdown values

Canonical dropdown values:

* `recommended`
* `languageIntegration`
* `lexiconWork`
* `buildMatrix`
* `qaValidation`
* `debugRecovery`
* `aiAssist`
* `all`

Display labels:

* Recommended
* Language Integration
* Lexicon Work
* Build & Matrix
* QA & Validation
* Debug & Recovery
* AI Assist
* All Tools

### 6.1.2 Power user behavior

When Power user is off:

* hide debug-only tools
* hide internal-only tools
* hide raw test tools
* hide heavy tools unless explicitly allowed
* prefer curated normal-path tools

When Power user is on:

* reveal hidden/debug/internal/test/heavy tools according to the active workflow
* expose advanced filters
* preserve the current workflow selection

---

## 6.2 Recommended workflow card

Selecting a workflow must show a card with:

* workflow label
* one-line goal
* ordered steps
* required tools
* optional tools
* warning if Power user is needed for parts of the flow

This card is instructional only. It does not trigger execution automatically.

---

## 7. Canonical Workflow Bundles

## 7.1 Recommended

**Goal:** shortest safe path for most operator tasks.

Visible tools:

* `build_index`
* `compile_pgf`
* `language_health`
* `run_judge`

Recommended workflow:

1. Build Index
2. Compile PGF
3. Language Health
4. Generate a sentence
5. Run Judge

---

## 7.2 Language Integration

**Goal:** add, repair, and validate one language.

Visible tools:

* `build_index`
* `lexicon_coverage`
* `compile_pgf`
* `language_health`
* `run_judge`
* `harvest_lexicon`
* `gap_filler`
* `bootstrap_tier1`

Recommended workflow:

1. Add or change language files
2. Build Index
3. Lexicon Coverage
4. Harvest / Gap Fill if needed
5. Bootstrap Tier 1 if needed
6. Compile PGF
7. Language Health
8. Generate a sentence
9. Run Judge

---

## 7.3 Lexicon Work

**Goal:** build or repair lexicon data.

Visible tools:

* `harvest_lexicon`
* `gap_filler`
* `lexicon_coverage`

Power-user add-ons may include:

* `seed_lexicon`
* import/build helpers

Recommended workflow:

1. Harvest or seed lexicon data
2. Fill gaps
3. Run Lexicon Coverage
4. Build Index
5. Run Language Health

---

## 7.4 Build & Matrix

**Goal:** manage inventory/build state.

Visible tools:

* `build_index`
* `compile_pgf`

Power-user add-ons:

* `rgl_scanner`
* `lexicon_scanner`
* `app_scanner`
* `qa_scanner`
* `bootstrap_tier1`

Recommended workflow:

1. Build Index
2. Compile PGF
3. Language Health

Power-user note:

Use individual scanners only when the Everything Matrix looks wrong or stale.

---

## 7.5 QA & Validation

**Goal:** verify correctness, runtime health, and performance.

Visible tools:

* `language_health`
* `run_judge`
* `profiler`

Power-user add-ons:

* raw smoke/API/GF/multilingual tests
* regression generators

Recommended workflow:

1. Language Health
2. Generate a sentence
3. Run Judge
4. Profiler

---

## 7.6 Debug & Recovery

**Goal:** isolate broken or inconsistent states.

Visible tools:

* `diagnostic_audit`

Power-user add-ons:

* targeted scanners
* raw pytest tools
* low-level diagnostics

Recommended workflow:

1. Diagnostic Audit
2. Run targeted scanner or raw test
3. Fix the issue
4. Build Index
5. Compile PGF
6. Language Health

---

## 7.7 AI Assist

**Goal:** human-guided AI help for difficult gaps.

Visible only when Power user is enabled:

* `ai_refiner`
* `seed_lexicon`

Recommended workflow:

1. Confirm deterministic tools reveal a real gap
2. Use AI assistance
3. Build Index
4. Compile PGF
5. Language Health
6. Run Judge

AI tools must never replace the deterministic normal path.

---

## 8. Tool Classification Rules

The dashboard may still maintain internal categories such as:

* build
* maintenance
* health
* qa
* data
* ai
* internal

However, those categories are **secondary metadata**, not the primary user navigation model.

The page must filter by **workflow first**, then optionally group or decorate by category.

---

## 9. Frontend Architecture

Recommended frontend responsibilities:

### 9.1 `page.tsx`

Owns:

* tool data loading
* filter state
* workflow selection
* visible tool list derivation
* selected tool state
* runner state
* workflow card state

### 9.2 `useToolsPrefs.ts`

Owns persisted user preferences, including:

* `workflowFilter`
* `powerUser`
* `showLegacy`
* `showTests`
* `showInternal`
* `wiredOnly`
* `showHeavy`
* layout preferences
* console behavior preferences

### 9.3 `workflows.ts`

Owns frontend workflow metadata:

* workflow IDs and labels
* fallback workflow card copy
* fallback tool membership
* fallback recommended order

This file exists as a UI helper even when backend registry metadata is present.

### 9.4 `backendRegistry.ts`

Owns curated frontend tool metadata and must remain in sync with the backend registry.

### 9.5 `buildToolItems.ts`

Builds normalized dashboard tool items from backend registry + frontend presentation metadata.

---

## 10. Backend Architecture

## 10.1 Router

`app/adapters/api/routers/tools.py` is the canonical tools router.

It owns:

* `/api/v1/tools/registry`
* `/api/v1/tools/run`
* request validation
* argument policy enforcement
* lifecycle envelope generation
* timeout and truncation handling

## 10.2 Registry modules

Execution policy lives in the backend registry modules, including:

* build tools registry
* maintenance tools registry
* QA registry
* AI / optional registry if present

These registries define:

* tool target
* allowed flags
* positionals policy
* timeout
* AI gating
* hidden/internal metadata
* workflow metadata for the frontend

## 10.3 Shared models

The tools API models must explicitly support workflow metadata so frontend and backend stay aligned.

Recommended model additions:

* `workflow_tags: list[str]`
* `normal_path: bool`
* `power_user_only: bool`
* `recommended_order: int | None`

---

## 11. Sync Rules

The following must remain synchronized:

* backend `TOOL_REGISTRY`
* frontend `backendRegistry.ts`
* workflow bundles shown in the dashboard
* documentation in this file
* documentation in `docs/17-TOOLS_AND_TESTS_INVENTORY.md`

Any tool added to the backend registry should be reviewed for:

1. normal visibility
2. workflow membership
3. power-user status
4. parameter docs
5. documentation impact

---

## 12. Validation Checklist

## 12.1 Registry/API checks

* `GET /api/v1/tools/registry` returns canonical tool IDs
* hidden/internal/heavy/test metadata is present
* workflow metadata is present
* invalid tool IDs return 404
* invalid flags are rejected
* AI tools return 403 when disabled

## 12.2 Dashboard checks

* workflow dropdown changes visible tools
* Power user reveals advanced tools without changing the active workflow
* recommended workflow card updates correctly
* `build_index` appears in normal workflows
* advanced filters still work
* counts update correctly
* tool selection remains stable where possible during filter changes

## 12.3 Execution checks

* `language_health` runs and shows lifecycle events
* `diagnostic_audit` runs and shows argument validation
* `lexicon_coverage` rejects unsupported flags
* `compile_pgf` runs with allowed flags only
* dry-run mode displays the resolved command without execution

---

## 13. Operational Guidance

### 13.1 Normal operator behavior

Use workflow filters, not raw category browsing.

Preferred order:

* Recommended
* Language Integration
* QA & Validation

### 13.2 Power-user behavior

Use Power user only when:

* the normal workflow is insufficient
* you need scanners or raw tests
* you are debugging registry/matrix drift
* you are working with AI-only tooling

### 13.3 Do not use the Tools Dashboard for

* arbitrary shell execution
* ad-hoc filesystem access outside repo policy
* replacing deterministic build steps with AI calls
* bypassing the official registry

---

## 14. Future Extensions

Planned or supported future improvements:

* registry-served workflow descriptions
* per-workflow analytics
* pinned favorite tools
* workflow-specific presets
* operator runbooks linked from workflow cards
* richer tool dependency graph visualization

---

## 15. Summary

The Tools Dashboard is a **workflow-oriented, allowlisted operator console** over the secure Tools API.

The final model is:

* **workflow dropdown** = what the user is trying to do
* **Power user** = whether hidden/debug tools are visible
* **registry metadata** = execution policy + presentation metadata
* **recommended workflow card** = guidance for the selected tool set

This keeps the page safe, scalable, and understandable even as the tool inventory grows.


