# Migration: `/generate` Path to Planner-Centered Runtime

Status: approved migration design
Owner: SKA runtime / generation
Last updated: 2026-03-10

---

## 1. Purpose

This document defines the migration from the current direct generation path:

`API payload -> frame normalization -> GenerateText -> engine.generate(...) -> text`

to the target planner-centered runtime:

`API payload -> frame normalization -> frame-to-plan bridge -> planner -> PlannedSentence -> ConstructionPlan -> lexical resolution -> renderer backend -> SurfaceResult -> API response mapping`

The migration makes the **planner-centered construction runtime** the single source of truth for sentence generation across all supported frame families and sentence structures.

This is a **runtime-alignment migration**, not a rewrite of the project’s architecture.

---

## 2. Why this migration is necessary

The repository already documents a layered architecture with clear separation between:

* semantics
* constructions
* morphosyntax
* lexicon
* language-family realization

The repository also already contains:

* a generic discourse planner
* a `PlannedSentence` abstraction
* `construction_id` assignment
* multiple construction modules
* multiple family-engine backends
* GF integration points
* safe-mode generation

However, the live `/generate` path still bypasses that architecture for single-sentence generation by sending normalized frames directly into runtime engines.

This creates three competing centers of truth:

1. the documented architecture
2. the planner / construction layer
3. the direct frame-to-engine generation path

This migration resolves that drift by making the planner-centered path authoritative.

---

## 3. Current state

### 3.1 Current live generation path

Today, generation is effectively:

1. API router receives payload.
2. Router normalizes into `Frame` or a frame-family-specific domain object.
3. `GenerateText.execute(...)` validates the normalized frame.
4. `engine.generate(lang_code, frame)` is called directly.
5. The engine converts the frame into its backend-specific representation.
6. Text is returned.

This path is operational, but it keeps sentence-design logic too close to the API/domain boundary and allows backend-local generation behavior to become implicit architecture.

### 3.2 Existing planner path

The repository already includes generic planning concepts such as:

* `plan_generic(...)`
* `plan_biography(...)`
* `PlannedSentence`
* `construction_id`
* `topic_entity_id`
* `focus_role`

This proves the repository already has the right abstraction for a planner-centered runtime.

### 3.3 Existing construction layer

The repository already contains multiple construction modules beyond biography, including copular, locative, existential, possession, eventive, relative-clause, and topic-comment structures.

This means the migration must be **generic across constructions**, not bio-specific.

### 3.4 Existing backend diversity

The repository already supports or anticipates multiple realization backends:

* GF / PGF
* family renderer
* safe-mode renderer

The migration must preserve that backend flexibility while forcing all backends behind one runtime contract.

---

## 4. Migration decision

### 4.1 Authoritative runtime center

After migration, the authoritative runtime center is:

`frame normalization -> frame-to-plan bridge -> planner -> PlannedSentence -> ConstructionPlan -> lexical resolution -> renderer backend -> SurfaceResult`

The planner-centered construction layer becomes the source of truth for:

* sentence type
* information packaging
* construction choice
* topic/focus metadata
* slot layout
* realization options
* lexical requirements

Backends become realization layers only.

### 4.2 What is not changing

This migration does **not** change the following high-level architectural commitments:

* SKA remains semantics-first and NLG-first.
* GF remains a realization backend, not the architecture itself.
* Family renderers remain first-class.
* Lexicon remains a separate subsystem.
* API compatibility is preserved during migration.

---

## 5. Migration goals

1. Make `PlannedSentence` and `ConstructionPlan` authoritative for runtime generation.
2. Remove sentence-logic duplication across router, use case, and renderer adapters.
3. Standardize a renderer-agnostic runtime contract.
4. Keep GF, family, and safe-mode renderers behind one realization boundary.
5. Preserve backward compatibility for current `/generate` callers.
6. Support all major sentence-structure families already present in the repo.
7. Prevent future drift between docs, planner, schemas, tests, and runtime code.

---

## 6. Non-goals

This migration does **not** aim to:

* redesign the semantics model from scratch
* replace GF
* eliminate family renderers
* rewrite every grammar before the new runtime lands
* force one uniform realization depth for all languages
* migrate callers to a new API payload format immediately

---

## 7. Core problem statement

The problem is **not** that the repository lacks architecture.

The problem is that runtime generation is currently split between:

* documented architecture
* planner abstractions
* direct engine generation

As long as these coexist as peer runtime architectures, the system will keep drifting.

The migration therefore makes one runtime contract authoritative.

---

## 8. Target runtime model

### 8.1 Canonical flow

```text
HTTP payload
  -> frame normalization
  -> frame-to-plan bridge
  -> planner
  -> PlannedSentence
  -> ConstructionPlan
  -> lexical resolution
  -> renderer dispatch
       -> gf
       -> family
       -> safe_mode
  -> SurfaceResult
  -> API response mapping
```

### 8.2 Runtime object roles

#### `PlannedSentence`

`PlannedSentence` is the sentence-level planning object.

It carries planner-owned decisions such as:

* `construction_id`
* `topic_entity_id`
* `focus_role`
* `discourse_mode`
* sentence packaging diagnostics
* planner-local provenance

It is authoritative for **what sentence is being planned**.

#### `ConstructionPlan`

`ConstructionPlan` is the backend-facing realization plan.

It carries the normalized renderer handoff:

* `construction_id`
* `lang_code`
* `slot_map`
* `generation_options`
* optional `lexical_bindings`
* optional provenance

It is authoritative for **what the renderer must realize**.

#### `SurfaceResult`

`SurfaceResult` is the canonical renderer output before API serialization.

It carries:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend`
* `debug_info`

The public API response may stay minimal, but internally it must come from `SurfaceResult`.

### 8.3 Authority boundaries

#### API/router

Responsible for:

* transport
* payload validation
* compatibility normalization
* request metadata

Not responsible for:

* sentence design
* construction choice
* wording
* lexical resolution
* backend-specific realization

#### Frame-to-plan bridge

Responsible for:

* mapping normalized frames into planner-ready construction requests
* identifying candidate construction families
* preserving semantic content needed for planning

Not responsible for:

* realization
* morphology
* string assembly

#### Planner

Responsible for:

* construction selection
* topic/focus assignment
* sentence packaging
* semantic slot layout
* discourse-sensitive choices
* default `generation_options`

Not responsible for:

* backend-specific syntax
* morphology
* AST ownership
* string templating

#### Lexical resolution

Responsible for:

* resolving entities and predicates into stable refs
* producing `entity_ref` and `lexeme_ref` values where possible
* attaching lexical features and provenance
* controlled raw-string fallback
* exposing fallback and confidence information

Not responsible for:

* choosing sentence structure
* choosing topic/focus
* changing construction meaning

#### Renderer

Responsible for:

* backend-specific realization
* morphology
* agreement
* word order
* AST construction where relevant
* string assembly
* returning `SurfaceResult`

Not responsible for:

* choosing what sentence to say
* redefining slot meanings
* inventing semantics
* silently replacing the selected construction

---

## 9. Canonical runtime contracts

### 9.1 Required generic contracts

The migration introduces or stabilizes generic runtime contracts that are **not bio-specific**:

* `planned_sentence`
* `construction_plan`
* `construction_id`
* `slot_map`
* `entity_ref`
* `lexeme_ref`
* `lexical_bindings`
* `generation_options`
* `renderer_backend`
* `surface_result`
* `debug_info`
* `fallback_used`

### 9.2 Why these contracts must be generic

The repository already defines multiple sentence structures and construction families, not just biography.

Therefore, runtime contracts must not be shaped around one construction family.

Biography lead becomes one implementation, not the runtime model.

### 9.3 Construction ID rule

`construction_id` values must be canonical runtime identifiers shared by docs, code, tests, and schemas.

Use snake_case runtime IDs such as:

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_locative`
* `copula_existential`
* `possession_have`
* `possession_existential`
* `topic_comment_copular`
* `topic_comment_eventive`
* `intransitive_event`
* `transitive_event`
* `ditransitive_event`
* `relative_clause_subject_gap`
* `relative_clause_object_gap`
* `bio_lead_identity`

Do not introduce alternate dotted or backend-local identifiers at the runtime boundary.

---

## 10. Compatibility policy

### 10.1 External API compatibility

Existing `/generate` callers continue to send current payloads.

The router remains backward-compatible by accepting current payload shapes and normalizing them into the new planner-centered runtime path.

### 10.2 Internal compatibility

During migration, `GenerateText` remains the public application use case, but internally becomes an orchestration layer over:

* frame normalization
* frame-to-plan bridging
* planning
* lexical resolution
* realization
* response mapping

This preserves dependency and routing stability while moving the implementation center.

### 10.3 Temporary fallback policy

Until all constructions are migrated:

* planner-first generation is authoritative for migrated constructions
* direct engine generation may remain only as a temporary compatibility fallback
* fallback use must be explicit in `debug_info`
* `fallback_used` must be machine-readable
* fallback paths must be removed once construction coverage is complete

### 10.4 Boundary rule for legacy payloads

Legacy input-shape compatibility ends at normalization.

Downstream runtime code must consume `PlannedSentence` / `ConstructionPlan`, not raw payload quirks.

---

## 11. Scope of the final version

The final version is **not** a bio-only runtime.

It must support the repository’s broader construction inventory.

Minimum migration target includes:

* equative / classification constructions
* attributive copular constructions
* locative constructions
* existential constructions
* possession constructions
* topic-comment copular constructions
* topic-comment eventive constructions
* eventive clause constructions
* relative clause constructions
* biography lead as one specialized migrated construction

---

## 12. Migration strategy

### 12.1 Strategy summary

This migration is implemented in batches, but the target is the **final architecture**, not a temporary alternative design.

The migration sequence is:

1. document the target runtime fully
2. define the generic runtime contract
3. wire planner-first orchestration
4. migrate construction modules onto the shared contract
5. externalize lexical resolution
6. migrate renderers onto the shared contract
7. retire direct frame-to-engine runtime ownership

### 12.2 Why documentation comes first

Documentation is Batch 1 because it prevents further drift in:

* naming
* interface boundaries
* object ownership
* construction coverage
* migration sequencing

Without migration docs first, code changes will reintroduce local architectural decisions.

---

## 13. Batch plan

### Batch 1 — Documentation

Deliver:

* architecture alignment docs
* runtime flow docs
* runtime contract docs
* planner / realizer interface docs
* lexical resolution contract docs
* migration and testing docs

Exit criteria:

* one agreed authoritative runtime model
* one agreed vocabulary for contracts and boundaries
* one agreed file / batch plan

### Batch 2 — Generic runtime contracts and planning core

Deliver:

* `PlannedSentence`
* `ConstructionPlan`
* `SlotMap`
* shared planning/runtime classes
* planner / realizer / lexical-resolver ports
* frame-to-plan bridge
* construction selector

Exit criteria:

* one backend-agnostic runtime contract in code
* one authoritative planning path

### Batch 3 — API and DI realignment

Deliver:

* router and dependency updates
* container wiring
* `GenerateText` orchestration changes
* API request/response mappers

Exit criteria:

* `/generate` runs planner-first for migrated constructions

### Batch 4 — Construction module migration

Deliver:

* existing construction modules aligned to the shared slot/spec contract
* construction registry alignment
* shared slot model alignment

Exit criteria:

* construction layer uses one runtime shape across modules

### Batch 5 — Lexical resolution layer

Deliver:

* generic lexical resolution adapters
* entity and predicate resolution helpers
* controlled raw-string fallback
* lexical bindings output for renderers

Exit criteria:

* renderers do not own lexical resolution logic

### Batch 6 — Renderer alignment

Deliver:

* generic renderer adapter boundary
* GF renderer alignment
* family renderer alignment
* safe-mode alignment

Exit criteria:

* all backends consume the same `ConstructionPlan` contract
* all backends return `SurfaceResult`

### Batch 7 — Family-engine migration

Deliver:

* family backends converted from ad hoc construction entrypoints to shared-contract realization

Exit criteria:

* language-family engines become realization-only layers

### Batch 8 — GF grammar/runtime migration

Deliver:

* GF abstract/concrete/runtime surface aligned to construction runtime
* direct ad hoc bio/event wrappers reduced or isolated

Exit criteria:

* GF is one backend under the same runtime contract

### Batch 9 — Schema alignment

Deliver:

* contract schemas for runtime planning objects
* frame-schema updates where needed for migrated construction mapping

Exit criteria:

* schemas support the planner-centered runtime without forcing backend-shaped payloads

### Batch 10 — Tests and cutover

Deliver:

* unit, integration, and API regression coverage
* direct-path deprecation and removal

Exit criteria:

* planner-centered runtime is the only authoritative generation path

---

## 14. Migration invariants

These rules must remain true throughout the migration.

1. The planner decides **what sentence to say**.
2. The renderer decides **how the selected backend says it**.
3. Lexical resolution is not hidden inside renderers.
4. API payloads do not become backend-shaped.
5. `ConstructionPlan` is the only planner-to-renderer handoff contract.
6. `SurfaceResult` is the only renderer-to-API handoff contract.
7. Debug metadata must expose at minimum:

   * `construction_id`
   * `renderer_backend`
   * `fallback_used`
8. No construction may introduce a second private runtime contract.
9. No backend may silently replace planner-selected construction semantics.

---

## 15. Naming rules

To prevent drift, the migration uses these canonical names:

* `lang_code`
* `planned_sentence`
* `construction_plan`
* `construction_id`
* `slot_map`
* `entity_ref`
* `lexeme_ref`
* `lexical_bindings`
* `generation_options`
* `renderer_backend`
* `surface_result`
* `debug_info`
* `fallback_used`

Use these planner fields where relevant:

* `topic_entity_id`
* `focus_role`
* `discourse_mode`

### 15.1 Reserved usage rule

* `generation_options` is the canonical cross-boundary options object passed into realization.
* `debug_info` is the canonical structured runtime trace object returned from realization.
* planner-local provenance or internal notes may exist, but they must not replace the canonical runtime names above.

### 15.2 Avoided drift names

Avoid using these as authoritative shared runtime names:

* `sentence` as the renderer contract object name
* `surface_text` as the primary result object name
* `metadata` as a generic replacement for `generation_options`
* `engine_payload`
* `gf_payload`
* `template_payload`
* `render_input`
* `sentence_spec` as a generic replacement for `construction_plan`

### 15.3 Generic vs specialized names

Examples of names that remain specialized rather than generic:

* `bio_lead_spec`
* `eventive_clause_spec`

Examples of names that remain generic:

* `planned_sentence`
* `construction_plan`
* `realizer`
* `lexical_resolver`

---

## 16. Risk analysis

### 16.1 Risk: duplication between planner and renderers

If the planner and renderers both encode sentence packaging logic, the migration fails.

Mitigation:

* construction selection and packaging live only in planner/construction code
* renderers only realize the given contract

### 16.2 Risk: bio-specific architecture leak

If runtime contracts are designed around biography, the migration will not scale to the existing construction inventory.

Mitigation:

* keep contracts generic
* keep construction-specific specs local

### 16.3 Risk: permanent compatibility bypass

If the legacy direct runtime remains indefinitely, drift continues.

Mitigation:

* mark legacy direct generation as temporary
* expose fallback use in `debug_info`
* require `fallback_used`
* remove direct fallback once construction coverage is complete

### 16.4 Risk: backend lock-in

If GF becomes the implicit owner of construction semantics, the repository will diverge from its documented architecture.

Mitigation:

* keep planner/runtime contracts renderer-agnostic
* treat GF as one backend

### 16.5 Risk: uncontrolled lexical fallback

If raw strings are injected directly into renderers without a lexical-resolution boundary, multilingual quality will remain brittle.

Mitigation:

* centralize lexical resolution
* log fallback source and confidence
* preserve deterministic fallback behavior

### 16.6 Risk: object-boundary drift

If `PlannedSentence`, `ConstructionPlan`, and `SurfaceResult` are used inconsistently, the migration will reintroduce ambiguity.

Mitigation:

* planner emits `PlannedSentence`
* planner-to-renderer handoff is `ConstructionPlan`
* renderers return `SurfaceResult`
* API response mapping happens only after `SurfaceResult`

---

## 17. Testing and acceptance

### 17.1 Acceptance conditions

The migration is complete when:

1. `/generate` uses planner-first orchestration for all migrated constructions.
2. Construction choice is visible in runtime `debug_info`.
3. GF, family, and safe-mode backends consume the same `ConstructionPlan`.
4. Lexical resolution is externalized from renderers.
5. Existing construction families run through the shared runtime contract.
6. Direct frame-to-engine generation is no longer an authoritative path.
7. Renderer fallback, if any, is explicit through `renderer_backend` and `fallback_used`.
8. API responses originate from `SurfaceResult`.

### 17.2 Minimum regression coverage

Coverage must include:

* unit tests for planning objects and slot maps
* unit tests for frame-to-plan mapping
* unit tests for lexical resolution
* unit tests for GF/family renderer adapters
* integration tests for planner-first generation in English and French
* API tests preserving current `/generate` compatibility

---

## 18. Operational guidance

### During migration

* prefer additive compatibility shims over hidden rewrites
* keep `debug_info` rich and machine-readable
* avoid premature grammar rewrites before the runtime contract is fixed
* document every new runtime object before broad usage
* keep dotted/backend-local identifiers out of the shared runtime surface

### After each batch

* refresh codedump
* verify file inventory and interface names
* validate that no new parallel runtime path has appeared
* confirm object names still match the canonical vocabulary

---

## 19. Definition of done

This migration is done only when:

* the planner/construction runtime is authoritative
* `PlannedSentence` and `ConstructionPlan` have stable ownership boundaries
* renderers are backend implementations only
* `SurfaceResult` is the canonical output contract
* the current direct runtime path is removed or strictly compatibility-only with documented sunset
* the broader construction inventory is supported by the shared runtime contract
* docs, code, schemas, and tests all describe the same runtime model

---

## 20. Final statement

This migration does not invent a new architecture for SKA.

It restores alignment between:

* the repository’s documented architecture
* the existing planner/construction abstractions
* the runtime generation path

The final runtime model is therefore:

**generic planner-centered construction runtime, explicit lexical resolution, backend-agnostic contracts, and renderer-specific realization behind a shared interface.**
