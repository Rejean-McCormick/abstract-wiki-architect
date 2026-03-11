# Construction Runtime Alignment

## Status

Approved Batch 1 alignment target.

## Purpose

This document defines the authoritative runtime architecture for sentence generation in SemantiK Architect (SKA).

Its goal is to eliminate architectural drift between:

- documented target architecture
- current discourse/planning model
- construction modules
- family renderers
- GF/PGF realization
- the current `/generate` runtime path

The central decision is:

> **All runtime generation must flow through one shared construction runtime contract.**

No renderer, router, or engine may remain an independent source of sentence-planning truth.

---

## Problem Statement

The repository already contains the core architectural ingredients needed for scalable multilingual generation:

- semantic frames
- discourse/planning
- construction modules
- family-oriented realization
- morphology
- lexicon
- GF integration

However, the current live runtime path for single-sentence generation still allows a direct route from API payloads to engine realization. This creates multiple overlapping centers of truth.

### Current architectural tension

At present, the system effectively has three competing runtime centers:

1. **Documented architecture**
   - semantics
   - constructions
   - family renderers / morphosyntax
   - lexicon

2. **Existing planner architecture**
   - `PlannedSentence`
   - `construction_id`
   - discourse-aware planning

3. **Direct generation path**
   - request payload
   - frame normalization
   - direct engine call
   - direct GF/Python realization

This document resolves that tension by making the planner-centered construction runtime authoritative.

---

## Architectural Decision

### Decision

SKA runtime generation shall be organized around the following authoritative pipeline:

```text
API/request
  -> frame normalization
  -> frame-to-plan bridge
  -> planner
  -> PlannedSentence
  -> ConstructionPlan
  -> lexical resolution
  -> renderer backend
  -> SurfaceResult
  -> API response mapping
````

### Consequence

This means:

* planner + construction runtime contract become the authoritative runtime center
* renderers become implementation backends
* GF becomes one renderer backend, not the architecture itself
* family renderers remain first-class
* direct frame-to-renderer generation becomes a compatibility shim only

---

## Scope

This decision applies to:

* API generation
* internal generation use cases
* family-renderer realization
* GF realization
* safe-mode realization
* lexical resolution for realized constructions
* debug/runtime tracing for generation

This decision does **not** require immediate redesign of all semantics or all grammar modules at once, but it does define the final target structure that all generation code must converge toward.

---

## Existing System Context

The current repository already supports a broader construction-oriented architecture than the live runtime path currently exposes.

### Already present in the system

* generic discourse planning objects and construction IDs
* construction modules for multiple sentence structures
* family-level rendering and morphology strategy
* GF grammar integration
* lexicon and language normalization infrastructure

### Already defined sentence/construction families

The system is not bio-only. Existing or documented sentence structures include categories such as:

* equative / classification
* attributive copular
* locative
* existential
* possession
* topic-comment copular
* topic-comment eventive
* relative clauses
* eventive structures
* coordination
* comparative / superlative patterns

Therefore, runtime architecture must be **construction-generic**, not biography-shaped.

---

## Design Principles

### 1. One source of runtime truth

The planner and the shared construction runtime contract define **what** sentence is to be said.

Renderers define **how** that sentence is realized in a given backend, language, or family.

### 2. Shared semantics, thin language specialization

The system must scale by sharing:

* frame normalization
* construction selection
* slot semantics
* planning logic
* renderer interface

Language-specific code should be limited to:

* lexical forms
* morphology
* local word-order differences
* idiomatic overrides where required

### 3. Backend independence

The same `ConstructionPlan` must be realizable by:

* family renderer
* GF renderer
* safe-mode renderer

### 4. Construction-first, not bio-first

Biography is one migrated construction family, not the architecture.

### 5. No duplicated planning logic

Construction logic must not be duplicated across:

* router code
* use cases
* GF wrappers
* family renderers
* construction modules

### 6. Fallback is explicit

Capability differences across languages and backends must be represented as explicit fallback policy, not hidden behavior.

### 7. Lexical resolution is explicit

Lexical resolution is its own runtime layer between planning and realization. It must not be hidden inside renderers.

---

## Target Runtime Architecture

## Layer 1 — API and Request Normalization

### Responsibility

Convert incoming external payloads into normalized internal frame/domain objects.

### Rules

* tolerate external payload variations only here
* normalize frame family and fields once
* do not perform realization logic here
* do not construct backend-specific ASTs here

### Output

A normalized internal frame object.

---

## Layer 2 — Frame-to-Plan Bridge

### Responsibility

Map a normalized frame to a planner-ready construction request.

### Example responsibilities

* choose classification vs locative vs possession vs eventive
* decide whether a frame becomes one sentence or multiple sentence candidates
* assign a canonical `construction_id`
* attach mapping provenance and fallback justification when needed

### Output

A planner-ready sentence-design request.

---

## Layer 3 — Planner

### Responsibility

Produce sentence-level planning objects that are backend-neutral and language-aware at the semantic level.

### Planner owns

* construction selection finalization
* topic/focus assignment
* discourse-sensitive choices
* sentence packaging
* sentence-level ordering decisions at the semantic/planning level
* fallback construction selection where needed
* default `generation_options`

### Planner does not own

* inflection
* backend-specific AST creation
* surface string concatenation
* direct language templates

### Output

One or more `PlannedSentence` objects.

---

## Layer 4 — ConstructionPlan Assembly

### Responsibility

Convert planner output into the canonical renderer-facing runtime contract.

### This layer owns

* transforming `PlannedSentence` into `ConstructionPlan`
* producing the canonical `slot_map`
* validating required vs optional roles
* attaching `generation_options`
* preserving any lexical requirements needed for resolution
* ensuring construction completeness before realization

### This layer does not own

* backend-specific realization
* morphology
* final wording

### Output

A validated `ConstructionPlan`.

---

## Layer 5 — Lexical Resolution

### Responsibility

Resolve semantic roles into lexicalized units usable by renderers.

### Examples

* entity naming strategy
* profession lemma lookup
* nationality/adjectival form lookup
* predicate lexical features
* language-specific fallback lemma selection

### Notes

Lexical resolution is not equivalent to realization. It prepares lexical material for realization.

### Output

A lexicalized `ConstructionPlan` with stable runtime references in the `slot_map` and optional `lexical_bindings`.

---

## Layer 6 — Renderer Backend

### Responsibility

Take the canonical construction runtime contract and produce a surface realization.

### Backends

* family renderer
* GF renderer
* safe-mode renderer

### Renderer owns

* backend-specific realization refinements that are strictly realization-local
* morphology calls
* AST construction for GF
* idiomatic linearization choices within backend limits
* controlled surface fallback

### Renderer does not own

* frame normalization
* construction selection
* semantic role identification
* discourse truth
* hidden construction substitution

---

## Layer 7 — Surface Result and Response Mapping

### Responsibility

Return a normalized renderer result and map it to the API response.

### Canonical renderer output

Renderers return `SurfaceResult` with:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend`
* `debug_info`

### API response

Public response mapping may remain backward-compatible, but it must originate from `SurfaceResult`.

---

## Authoritative Runtime Contract

The system must converge on one shared runtime contract for all constructions.

## Required runtime objects

### `PlannedSentence`

Planner-facing sentence-level object representing one sentence candidate.

### `ConstructionPlan`

Canonical planner-to-renderer contract for one construction.

### `SlotMap`

Canonical mapping of semantic roles to runtime slot payloads.

### `EntityRef`

Normalized entity reference used in slots.

### `LexemeRef`

Normalized lexical reference used in slots.

### `SurfaceResult`

Canonical renderer result before API serialization.

### `generation_options`

Canonical cross-boundary realization-options object.

### `debug_info`

Canonical structured runtime tracing object.

### `fallback_used`

Canonical machine-readable indicator that compatibility or capability fallback occurred.

---

## Canonical Naming Rules

The following names are canonical across planner and renderer boundaries.

### Required shared names

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

### Planner-local names allowed where relevant

* `normalized_frame`
* `topic_entity_id`
* `focus_role`
* `discourse_mode`

### Naming style

* construction IDs use stable backend-independent `snake_case`
* slot names use stable semantic `snake_case`
* backend-specific names must not cross the runtime contract boundary

These names must not be reinvented per construction family or per backend.

### Avoided drift names

The following must not replace the canonical runtime names above:

* `metadata` as a replacement for `generation_options`
* `surface_text` as a replacement for `SurfaceResult`
* dotted backend-local construction IDs
* backend-private payload names such as `gf_payload` or `engine_payload`

---

## Construction Contract Rules

Every construction must define:

* its `construction_id`
* required roles
* optional roles
* validation rules
* sentence-kind expectations
* lexical requirements
* renderer capability expectations
* fallback behavior

### Example construction families

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_attributive_adj`
* `copula_attributive_np`
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

Biography lead behavior may be one migrated specialization, but it must still conform to the same generic construction runtime contract.

---

## Planner Boundary

### Planner input

The planner consumes normalized frames and planning metadata.

### Planner output

The planner emits `PlannedSentence` objects that preserve sentence intent and discourse packaging without embedding backend-specific realization logic.

### Planner rule

Planner output must remain backend-neutral. No planner output may embed GF-only or family-only structures as its primary representation.

---

## ConstructionPlan Boundary

### ConstructionPlan input

This layer consumes `PlannedSentence`.

### ConstructionPlan output

This layer emits `ConstructionPlan` with:

* `construction_id`
* `lang_code`
* `slot_map`
* `generation_options`

It may also preserve planner-owned fields such as:

* `topic_entity_id`
* `focus_role`
* `discourse_mode`

And it may include optional runtime attachments such as:

* `lexical_bindings`
* provenance data

### Boundary rule

All semantic content required for realization must be present in `slot_map` before rendering starts.

`generation_options` is the canonical shared options object at this boundary. Planner-local metadata may exist, but it must not replace the canonical contract names.

---

## Renderer Boundary

### Renderer input

Each renderer consumes the same logical input:

* `construction_plan`

Optional renderer-specific context may be passed only through controlled fields on the shared contract, never through ad hoc payload shape changes.

### Renderer output

Each renderer returns `SurfaceResult` with:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend`
* `debug_info`

### Backend-specific behavior

Allowed:

* GF AST creation
* family morphology invocation
* safe-mode fallback formatting

Not allowed:

* changing construction semantics
* redefining slot meanings
* selecting a different construction without planner approval

---

## GF in the Aligned Architecture

GF remains valuable, but its role is constrained.

### GF is

* a realization backend
* a typed grammar backend
* a high-fidelity renderer for supported constructions and languages

### GF is not

* the source of semantic truth
* the construction selector
* the only runtime architecture
* the only path for multilingual support

### Required GF alignment

GF adapters must consume `ConstructionPlan` and `slot_map` rather than directly owning frame-to-sentence logic.

This implies:

* no permanent direct frame -> GF AST runtime path
* grammar functions must align with construction contracts
* GF wrappers become renderer adapters, not sentence planners

---

## Family Renderers in the Aligned Architecture

Family renderers remain central for scale.

### Why

For large multilingual support, family-level sharing is mandatory. The architecture must avoid bespoke per-language business logic.

### Family renderers should own

* family-level morphosyntactic strategies
* agreement policies
* article and word-order behaviors where shared
* fallback realization for languages without full GF support

### Family renderers should not own

* API payload parsing
* semantic role discovery
* frame normalization
* construction selection

---

## Lexicon in the Aligned Architecture

Lexicon is a shared subsystem, not a renderer detail.

### Lexicon responsibilities

* canonical code normalization
* lemma lookup
* feature lookup
* entity naming support
* lexical fallback selection

### Lexicon must be reusable by

* GF renderer
* family renderer
* safe-mode renderer
* planner support code where explicitly allowed

---

## Debug and Provenance Model

All runtime generation must return structured machine-readable debug metadata.

### Minimum shared debug expectations

* `construction_id`
* `renderer_backend`
* `fallback_used`

### Recommended shared diagnostics

* planning metadata
* lexical-resolution metadata
* backend realization metadata
* timing metadata
* warnings/errors where relevant

### Rule

Fallbacks, downgrades, and compatibility shims must be visible in runtime metadata.

---

## Compatibility Model

## Short-term compatibility

The current `/generate` API contract may remain externally stable while internals are migrated.

### Allowed temporary shape

```text
request
  -> normalize frame
  -> planner-centered runtime
  -> SurfaceResult
  -> response
```

while preserving current endpoint names and most payload compatibility behavior.

## Forbidden long-term shape

```text
request
  -> normalize frame
  -> direct GF/Python engine generation
  -> response
```

except as a temporary compatibility shim.

---

## Migration Intent

This architecture should be implemented to the final target shape, not as a permanent partial fork.

### Final migration goal

All generation code paths converge on:

* one planning contract
* one construction runtime contract
* one renderer boundary
* multiple renderer implementations

### First migrated constructions

Initial migration may begin with biography-oriented behavior or other high-value constructions, but each migrated path must be implemented as part of the generic runtime architecture, not as a special architecture of its own.

---

## Invariants

The following invariants are mandatory.

### Invariant 1 — Construction identity is explicit

Every realized sentence must have a `construction_id`.

### Invariant 2 — Planner output is backend-neutral

No planner output may embed GF-only or family-only logic as its primary representation.

### Invariant 3 — Renderer behavior is substitutable

Any renderer must be able to consume the same `ConstructionPlan` for a supported construction.

### Invariant 4 — No hidden semantic reinterpretation

Renderers may refine realization, but they may not reinterpret slot semantics.

### Invariant 5 — Debug info is structured

All runtime generation must return structured machine-readable debug/provenance metadata.

### Invariant 6 — Language fallback is explicit

Fallback backend or capability downgrade must be visible in runtime metadata through `fallback_used` and related `debug_info`.

### Invariant 7 — API responses originate from the shared runtime result

Public generation responses may stay backward-compatible, but they must originate from `SurfaceResult`, not from backend-private payloads.

### Invariant 8 — One cross-boundary options object

`generation_options` is the canonical shared realization-options object. No parallel generic `metadata` object may replace it at the planner-to-renderer boundary.

---

## Non-Goals

This document does not require:

* immediate migration of every construction in one commit
* immediate full GF coverage for all languages
* elimination of all compatibility code on day one
* redesign of all schemas before runtime contract definition

This document also does not authorize:

* a bio-only architecture fork
* backend-specific runtime contracts
* direct router-to-renderer sentence logic as a permanent pattern

---

## Risks If Not Adopted

If the system continues without this alignment, likely failure modes include:

* duplicated generation logic in multiple layers
* drift between docs and runtime behavior
* GF wrappers owning construction logic
* family renderers diverging in input assumptions
* poor scalability across large language inventories
* inconsistent debug/provenance behavior
* increased regression risk whenever new constructions are added

---

## Benefits If Adopted

* one authoritative runtime center
* reduced architectural drift
* clean backend substitution
* better multilingual scalability
* clearer testing strategy
* easier migration of existing constructions
* cleaner separation of semantics vs realization
* more robust future extension to non-bio domains

---

## Ownership

### Architecture authority

This document governs all new generation/runtime changes.

### Enforcement rule

Any new generation feature must answer all of the following before implementation:

1. What is the `construction_id`?
2. What are the required and optional roles?
3. What does `PlannedSentence` look like?
4. What does `ConstructionPlan` look like?
5. How is lexical resolution performed?
6. Which renderers support it?
7. What is fallback behavior?
8. What debug/provenance metadata will be returned?

If these are not defined, the feature is not ready for implementation.

---

## Implementation Consequence Summary

The codebase must be updated so that:

* API generation becomes planner-first
* frame-to-plan mapping becomes explicit
* `ConstructionPlan` assembly becomes explicit
* construction contracts become explicit
* lexical resolution becomes explicit
* renderers consume `ConstructionPlan`
* lexicon becomes a shared resolution layer
* GF and family renderers implement the same runtime boundary
* direct frame-to-renderer generation is demoted to compatibility support only

---

## Final Decision

The authoritative generation architecture for SKA is:

```text
frame normalization
  -> frame-to-plan bridge
  -> planner
  -> PlannedSentence
  -> ConstructionPlan
  -> lexical resolution
  -> renderer backend
  -> SurfaceResult
  -> API response mapping
```

This is the target architecture that all generation code must implement and all future construction work must follow.


