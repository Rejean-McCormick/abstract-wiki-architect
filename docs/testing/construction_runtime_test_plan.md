# Construction Runtime Test Plan

## Status

Proposed implementation target.

## Purpose

This document defines the test strategy for the aligned construction runtime in SemantiK Architect (SKA).

It exists to verify that runtime generation is consistently implemented through the authoritative architecture:

```text
frame normalization
  -> frame-to-construction bridge
  -> planner
  -> PlannedSentence
  -> construction-plan builder
  -> ConstructionPlan
  -> lexical resolution
  -> renderer backend
  -> SurfaceResult
  -> response mapping
````

The test plan is designed to prevent drift between:

* API behavior
* frame-to-construction mapping
* planner behavior
* construction-plan building
* lexical resolution
* renderer backends
* grammar/runtime realization
* debug/provenance output

---

## Test Objectives

The construction runtime test suite must prove all of the following:

1. **Planner authority**

   * generation flows through planning and shared runtime contracts
   * renderers do not invent sentence semantics independently

2. **Contract stability**

   * `PlannedSentence`, `ConstructionPlan`, `SlotMap`, `EntityRef`, `LexemeRef`, and `SurfaceResult` remain structurally valid

3. **Renderer substitutability**

   * the same planned construction can be consumed by multiple backends where supported

4. **Lexical resolution correctness**

   * lexical resolution produces normalized runtime inputs suitable for rendering

5. **Construction consistency**

   * each construction enforces its required and optional role rules

6. **Compatibility preservation**

   * current `/generate` API behavior remains externally stable while internals migrate

7. **Fallback transparency**

   * capability downgrades or renderer fallback are explicit in runtime metadata

8. **Multilingual scalability**

   * construction logic remains generic while language-specific behavior remains localized to renderers and lexical resolution

---

## Test Scope

This plan covers:

* domain planning objects
* construction contract objects
* frame normalization
* frame-to-construction mapping
* construction-plan building
* slot mapping
* lexical resolution
* renderer selection
* GF rendering
* family-engine rendering
* safe-mode rendering
* API integration
* compatibility behavior
* debug/provenance structure

This plan does **not** attempt to fully test every lexical item in every language.
It verifies architecture, contract behavior, and representative multilingual paths.

---

## Test Layers

## 1. Unit Tests

### Goal

Verify the behavior of isolated runtime components.

### Targets

* planning objects
* construction contract validation
* frame normalization helpers
* frame-to-construction mapping
* construction-plan builders
* slot mapping
* lexical resolution
* renderer adapters
* debug info builders
* fallback policy helpers

### Success condition

Each unit can be tested without requiring full API startup or end-to-end execution.

---

## 2. Integration Tests

### Goal

Verify end-to-end cooperation between runtime layers inside Python.

### Targets

* normalized frame -> frame-to-construction bridge -> planner -> construction-plan builder -> lexical resolution -> renderer
* shared `ConstructionPlan` consumed by multiple renderers
* renderer backend selection
* compatibility shim behavior during migration

### Success condition

The full internal runtime path works without requiring browser or UI tools.

---

## 3. HTTP API Tests

### Goal

Verify that public generation endpoints preserve stable behavior while using the planner-first runtime internally.

### Targets

* `/api/v1/generate/{lang_code}`
* payload normalization
* compatibility handling for tolerated legacy request shapes
* response shape stability
* error status behavior

### Success condition

External clients can continue using the API while the internals are migrated.

---

## 4. Regression Tests

### Goal

Prevent old architectural drift from reappearing.

### Targets

* direct frame-to-renderer shortcuts
* construction modules bypassing contract validation
* renderer-specific reinterpretation of slot semantics
* loss of `construction_id`
* inconsistent `debug_info`
* backend-private response payloads bypassing `SurfaceResult`

### Success condition

Any regression toward multiple generation centers of truth is detected early.

---

## 5. Capability / Fallback Tests

### Goal

Verify that support differences across renderers and languages are handled explicitly.

### Targets

* GF supported path
* family-engine supported path
* safe-mode fallback path
* unsupported construction path
* unsupported language path

### Success condition

The system fails or downgrades predictably, with structured metadata.

---

## Authoritative Test Rule

All runtime generation tests must treat the following as authoritative:

* `construction_id`
* `slot_map`
* lexicalized `ConstructionPlan`
* `renderer_backend`
* `SurfaceResult`
* structured `debug_info`

Tests must not treat backend-specific strings or ASTs as the primary source of semantic truth.

---

## Canonical Test Object Names

These names are canonical across tests:

* `raw_payload`
* `normalized_frame`
* `planned_sentence`
* `construction_plan`
* `slot_map`
* `resolved_construction_plan`
* `lang_code`
* `renderer_backend`
* `surface_result`

These names should be used consistently across unit, integration, and API tests.

---

## Test Matrix

## A. Frame Normalization

### Objective

Verify that external payload variants normalize into stable internal frame/domain objects.

### Cases

* canonical payload
* tolerated legacy payload
* nested payload
* top-level flat payload where legacy compatibility is intentionally supported
* payload with extra irrelevant fields
* payload missing required frame family fields
* payload with conflicting language fields
* malformed payload
* wrong field types

### Assertions

* normalized frame type is correct
* required internal fields are present
* normalization is deterministic
* no renderer-specific fields appear at this layer
* invalid input fails with correct error semantics

---

## B. Frame-to-Construction Mapping

### Objective

Verify that normalized frames are routed to the correct construction family.

### Cases

* equative/classification frame
* attributive frame
* locative frame
* existential frame
* possession frame
* topic-comment frame
* eventive frame
* relative-clause frame
* ambiguous frame with deterministic rule
* unsupported frame family

### Assertions

* correct `construction_id`
* correct planner input shape
* unsupported frames fail explicitly
* no backend-specific routing logic leaks into this layer

---

## C. Planning

### Objective

Verify planner output is semantically correct and backend-neutral.

### Cases

* single-clause construction
* topic/focus-sensitive construction
* discourse-aware planning
* planner with minimal roles
* planner with all optional roles present
* planner receiving unsupported role combinations

### Assertions

* `construction_id` present
* planner output is a valid `PlannedSentence`
* `topic_entity_id` behavior correct where applicable
* `focus_role` behavior correct where applicable
* planner output does not embed GF-only structures
* planner output does not embed family-template-only structures

---

## D. Construction-Plan Building

### Objective

Verify planner output is converted into the canonical renderer-facing runtime contract.

### Cases

* complete `PlannedSentence`
* missing optional role
* missing required role
* repeated role where multiplicity is allowed
* repeated role where multiplicity is forbidden
* incompatible role type
* entity vs predicate confusion
* metadata propagation
* surface hint presence/absence where supported

### Assertions

* `ConstructionPlan` shape valid
* `slot_map` present
* required roles enforced
* slot types validated
* slot names canonical
* multiplicity rules enforced
* no silent coercion that changes semantics

---

## E. Slot Mapping

### Objective

Verify semantic roles are converted into stable runtime slots.

### Cases

* complete role set
* missing optional role
* missing required role
* repeated role where multiplicity is allowed
* repeated role where multiplicity is forbidden
* incompatible role type
* entity vs predicate confusion

### Assertions

* required slots enforced
* slot payload types validated
* slot names canonical
* no backend-private fields leak into the shared contract

---

## F. Lexical Resolution

### Objective

Verify semantic slot values are converted into lexicalized runtime values.

### Cases

* entity with explicit label
* entity with QID and no label
* profession/predicate with lemma
* predicate with QID-backed lookup
* nationality/adjectival lookup
* unresolved lexical item with fallback
* missing lexical entry
* language-specific lexical override
* language-independent fallback

### Assertions

* `EntityRef` shape valid
* `LexemeRef` shape valid
* fallback is explicit
* lexical resolution is deterministic
* missing lexical data does not silently corrupt construction semantics
* output remains a valid shared `ConstructionPlan`

---

## G. Renderer Selection

### Objective

Verify the system selects the correct renderer backend.

### Cases

* GF available and supports construction
* family renderer selected by capability
* safe-mode selected by fallback
* forced backend override
* unsupported backend
* unsupported language in selected backend
* backend downgrade path

### Assertions

* chosen backend matches capability rules
* backend fallback is explicit
* `ConstructionPlan` is unchanged in semantic content by selection
* debug info records selected backend

---

## H. GF Renderer Tests

### Objective

Verify GF consumes the generic construction runtime contract instead of owning sentence semantics directly.

### Cases

* valid `ConstructionPlan` to GF AST path
* supported construction and language
* missing slot rejected before GF realization
* lexicalized plan with entity and predicate refs
* unsupported construction for GF backend
* unsupported language in GF backend
* malformed AST generation failure

### Assertions

* GF adapter consumes `construction_plan`
* no direct raw frame-to-GF shortcut is used
* failure path is structured
* output metadata includes backend and construction info

---

## I. Family Renderer Tests

### Objective

Verify family renderers consume the same contract as GF.

### Cases

* same `ConstructionPlan` realized by family renderer
* family-specific word-order handling
* morphology-dependent output
* lexical fallback behavior
* unsupported construction in a family engine
* unsupported feature combination

### Assertions

* family renderer uses shared contract
* family renderer does not reinterpret slot semantics
* family renderer may vary surface form while preserving semantic intent
* failure is explicit and structured

---

## J. Safe-Mode Renderer Tests

### Objective

Verify safe-mode remains a controlled fallback backend.

### Cases

* supported construction in safe-mode
* fallback from unsupported GF path
* fallback from unsupported family path
* unresolved lexical item
* minimal slot plan

### Assertions

* safe-mode output is well-formed
* safe-mode is marked explicitly in metadata
* safe-mode does not become an untracked silent fallback

---

## K. Surface Result Tests

### Objective

Verify final renderer result shape is stable and complete.

### Cases

* successful generation
* partial-fallback generation
* failed generation
* unsupported language
* unsupported construction
* lexical failure
* renderer failure

### Assertions

* `text` present on success
* `lang_code` present
* `construction_id` present
* `renderer_backend` present
* `debug_info` present
* error shape consistent on failure
* no silent empty-string success unless explicitly permitted

---

## L. API Compatibility Tests

### Objective

Verify the public API remains stable while internals migrate.

### Cases

* current canonical payload
* tolerated legacy payload
* language in URL only
* language in payload where allowed
* language mismatch
* missing `frame_type`
* missing required semantic fields
* unknown construction/frame family
* malformed JSON

### Assertions

* response status codes correct
* response model shape stable
* compatibility normalization works where intended
* invalid requests fail with correct status and detail shape
* public response originates from `SurfaceResult`

---

## M. Debug / Provenance Tests

### Objective

Verify runtime metadata is structured and useful.

### Required metadata

* `construction_id`
* `renderer_backend`
* language resolution
* lexical fallback markers where relevant
* backend downgrade markers where relevant
* planner/build metadata where relevant
* AST or renderer trace only where applicable

### Assertions

* metadata shape is structured
* fields are stable across backends
* missing metadata is treated as a failure for runtime contract tests

---

## Minimum Construction Coverage

The following construction families must be represented in automated tests:

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

Each construction does not need identical coverage depth initially, but each must have at least:

* contract validation coverage
* planner mapping coverage
* one positive realization path
* one negative/failure path

---

## Language Coverage Strategy

## Target language sets

### Tier A — mandatory migration languages

These are the first languages used to validate the aligned runtime end to end.

* English
* French

### Tier B — representative family languages

Add at least one representative language for each active family backend as migration proceeds.

### Tier C — fallback coverage languages

Include languages that are expected to use safe-mode or partial support to verify explicit fallback behavior.

---

## Cross-Backend Equivalence Testing

### Objective

Ensure backend variation does not become semantic drift.

### Rule

Where the same construction is supported by multiple backends, tests must verify:

* same `construction_id`
* same slot semantics
* same essential proposition
* allowed surface variation only

### Allowed differences

* article choice
* word order
* morphology
* idiomatic phrasing
* punctuation where language-specific

### Forbidden differences

* changed predicate meaning
* changed argument structure
* dropped required roles without explicit fallback marker
* silent reinterpretation of semantic roles

---

## Failure Testing

The runtime must be tested for predictable failure behavior.

## Failure classes

* invalid payload
* unsupported frame family
* unsupported construction
* invalid `PlannedSentence`
* invalid `ConstructionPlan`
* missing required role
* lexical resolution failure
* renderer selection failure
* renderer realization failure
* unsupported language
* backend capability mismatch
* malformed debug metadata

## Failure requirements

Every failure test must verify:

* correct exception or error response type
* stable error shape
* no silent success
* no hidden backend substitution unless explicitly allowed and recorded

---

## Performance / Stability Sanity Tests

These are not benchmark-heavy tests, but guardrails.

### Required sanity checks

* repeated generation with same plan is deterministic where expected
* repeated generation does not mutate shared slot state
* `PlannedSentence` is immutable or treated as immutable by later stages
* `ConstructionPlan` is immutable or treated as immutable by renderers
* lexical resolution does not leak cross-test cache state incorrectly
* backend selection does not depend on incidental ordering

---

## Required Test Files

## Unit

* `tests/unit/planning/test_construction_plan.py`
* `tests/unit/planning/test_frame_to_plan.py`
* `tests/unit/planning/test_frame_to_slots.py`
* `tests/unit/lexicon/test_lexical_resolution.py`
* `tests/unit/renderers/test_family_construction_adapter.py`
* `tests/unit/renderers/test_gf_construction_adapter.py`
* `tests/unit/use_cases/test_plan_text.py`
* `tests/unit/use_cases/test_realize_text.py`

## Integration

* `tests/integration/test_generate_via_planner_en.py`
* `tests/integration/test_generate_via_planner_fr.py`

## HTTP API / Regression

* `tests/http_api/test_generate.py`
* `tests/http_api/test_generations.py`
* `tests/test_multilingual_generation.py`
* `tests/test_gf_dynamic.py`
* `tests/core/test_use_cases.py`
* `tests/core/test_domain_models.py`

---

## Acceptance Gates

A construction runtime migration is not complete until all of the following pass.

## Gate 1 — Contract gate

* shared contract objects exist
* planner emits `PlannedSentence`
* construction-plan building emits `ConstructionPlan`
* renderers consume `ConstructionPlan`
* tests verify the contract end to end

## Gate 2 — Backend gate

* at least one construction is realizable through:

  * GF backend
  * family backend
  * safe-mode backend

## Gate 3 — Compatibility gate

* `/generate` remains externally usable
* legacy-compatible payloads still behave as intended

## Gate 4 — Metadata gate

* `debug_info` is present and structured
* backend and construction identity are visible

## Gate 5 — Regression gate

* direct frame-to-renderer generation is no longer the primary runtime path
* planner-first generation is observable in tests

---

## Test Data Guidelines

### Use stable semantic examples

Prefer examples that are:

* simple
* unambiguous
* reproducible
* easy to compare across languages

### Avoid test data that depends on

* incidental lexical richness
* unstable external services
* live external APIs
* random generation
* hidden mutable state

### Prefer semantic fixtures over raw strings

Where possible, tests should build canonical semantic inputs and compare normalized runtime behavior instead of only comparing final strings.

---

## Assertions Policy

### Strong assertions

Use strong assertions for:

* `construction_id`
* slot presence
* backend selection
* metadata shape
* error types
* fallback markers

### Flexible assertions

Use flexible assertions for:

* allowed surface variation
* morphology differences across backends
* punctuation differences where not semantically important

### Avoid brittle assertions

Do not overfit tests to:

* internal incidental field ordering
* exact debug formatting beyond documented fields
* backend-internal AST details unless the test is explicitly about AST production

---

## Migration Testing Policy

During migration, every moved construction must receive tests in this order:

1. frame-to-construction mapping validation
2. planner validation
3. construction-plan validation
4. lexical resolution validation
5. one renderer success path
6. one failure path
7. API regression coverage where publicly exposed

No construction should be considered migrated based only on manual browser testing.

---

## Exit Criteria

The construction runtime alignment is considered fully implemented when:

* all generation paths pass through planner + shared construction runtime contract
* all active renderers consume the same `ConstructionPlan` boundary
* direct frame-to-renderer generation is compatibility-only
* required construction families have automated coverage
* multilingual fallback behavior is explicit and tested
* public API behavior remains stable
* debug/provenance metadata is structured and stable

---

## Final Rule

A runtime generation feature is not complete until its tests prove:

* what construction is being realized
* what roles or slots are being realized
* how lexical resolution was resolved
* which backend produced the result
* whether fallback occurred
* that the sentence came from the planner-first construction runtime

If those facts are not testable, the runtime is not sufficiently aligned.


