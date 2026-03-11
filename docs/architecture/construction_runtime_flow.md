# Construction Runtime Flow

Status: proposed implementation target
Owner: Architecture / Runtime
Scope: define the authoritative runtime flow for sentence generation across all constructions in SemantiK Architect (SKA)

---

## 1. Purpose

This document defines the **authoritative runtime flow** for text generation in SKA.

It exists to prevent drift between:

1. the documented architecture,
2. the planner / discourse layer,
3. the live API generation path,
4. the renderer backends,
5. the lexicon and morphology subsystems.

The core decision is:

> **Runtime generation is planner-first and construction-centered.**

The authoritative flow is:

`HTTP payload -> frame normalization -> frame-to-construction bridge -> planner -> construction plan -> lexical resolution -> renderer dispatch -> surface result -> API response`

The runtime must **not** be organized as:

`raw frame -> backend-specific renderer -> surface text`

---

## 2. Architectural context

SKA is documented as a system that separates:

* semantics,
* constructions,
* morphosyntax,
* lexicon,
* realization backends.

It already includes:

* a discourse/planning layer,
* construction IDs and planned-sentence concepts,
* an existing construction inventory,
* family-oriented realization,
* GF integration,
* a live `/generate` path that still needs to be realigned behind one construction runtime contract.

This document resolves the runtime boundary between those pieces.

---

## 3. Problem statement

### 3.1 Current situation

Today, the repository contains both:

1. a **documented planner/construction architecture**, and
2. a **live direct generation path** that can bypass planner-centered construction handling.

That is acceptable as a migration state, but it is not acceptable as the final architecture.

### 3.2 Main risk

If runtime generation remains backend-centered, then:

* GF adapters,
* family engines,
* safe-mode renderers,
* routers and use cases

can each become hidden sources of sentence-planning logic.

That would violate the architecture’s core goal of shared, construction-level runtime semantics.

### 3.3 Goal of this document

Define one runtime flow that:

* works for **all constructions**, not just biography,
* keeps the planner/construction layer authoritative,
* allows multiple renderer backends,
* scales across languages and language families,
* preserves API compatibility during migration.

---

## 4. Core runtime decision

### 4.1 Authoritative source of truth

The runtime source of truth for sentence generation is:

1. normalized semantic input,
2. frame-to-construction bridging,
3. construction planning,
4. lexical resolution,
5. construction-level realization.

### 4.2 Backend role

Backends do **not** decide the sentence’s semantic structure.

Backends decide only:

* how a selected construction is realized in a target language,
* how morphology, agreement, and word order are handled,
* how backend-specific fallback is executed and reported.

### 4.3 Summary rule

* the planner decides **what sentence is to be said**
* the renderer decides **how the target language says it**

---

## 5. Runtime layers

### 5.1 Layer A — Input normalization

**Responsibility**

* accept API payloads and tolerated legacy variants
* normalize them into authoritative internal frame/domain objects
* attach request metadata needed for downstream orchestration

**Examples**

* `BioFrame`
* `EventFrame`
* relational/entity frames
* other normalized frame families

**Must not do**

* language-specific wording
* backend-specific AST creation
* hidden fallback sentence construction
* renderer selection

---

### 5.2 Layer B — Frame-to-construction bridge

**Responsibility**

* inspect the normalized frame
* identify the relevant construction family
* prepare a construction-oriented planning request

**Outputs**

* construction-oriented planning input
* candidate `construction_id`
* normalized semantic role expectations

**Examples**

* `copula_equative_classification`
* `copula_locative`
* `topic_comment_eventive`
* `topic_comment_copular`
* biography-lead construction selection as one construction family among many

**Must not do**

* morphology
* backend-specific realization
* direct string templating

---

### 5.3 Layer C — Planning

**Responsibility**

* finalize construction choice
* assign semantic roles into canonical slots
* produce the planner-authoritative runtime object
* assign topic/focus metadata
* attach planner metadata needed for realization

**Outputs**

* `planned_sentence` as a planner concept
* `ConstructionPlan` as the authoritative realization handoff
* `construction_id`
* `slot_map`
* `topic_entity_id`
* `focus_role`
* `metadata`

**Notes**

`planned_sentence` and `ConstructionPlan` are aligned concepts during migration, but realization is governed by the `ConstructionPlan` contract.

The planner owns:

* sentence packaging,
* slot assignment,
* discourse-sensitive information structure,
* semantic-level realization options.

The planner does **not** own:

* inflection,
* morphology,
* backend-specific AST creation,
* backend-specific syntax templates,
* final string assembly.

---

### 5.4 Layer D — Lexical resolution

**Responsibility**

* resolve raw slot values into stable `EntityRef` and `LexemeRef` objects
* preserve slot structure while enriching lexical identity
* attach lemma, features, provenance, confidence, and fallback data

**Examples**

* profession lemma resolution
* predicate nominal resolution
* nationality/adjectival lookup
* entity label normalization
* alias normalization
* controlled raw-string fallback

**Must remain reusable**

* across multiple constructions,
* across multiple renderers,
* across multiple languages.

**Output**

A lexicalized `ConstructionPlan`, typically by enriching the existing `slot_map` rather than replacing the runtime contract.

---

### 5.5 Layer E — Realization and renderer dispatch

**Responsibility**

* choose the realization backend explicitly
* validate backend capability against language and construction
* realize the lexicalized plan into one surface result

**Canonical backends**

* `family`
* `gf`
* `safe_mode`

All backends must consume the **same construction-level contract**.

Renderers own:

* morphology,
* agreement,
* word-order realization,
* backend-local AST or template assembly,
* controlled backend fallback.

Renderers do **not** own:

* frame normalization,
* construction selection,
* semantic role assignment,
* canonical lexical normalization.

---

### 5.6 Layer F — API response packaging

**Responsibility**

* map the canonical renderer output into the public API response
* preserve `text` and `lang_code`
* expose `debug_info` when enabled
* preserve fallback visibility

**Output**

A stable response mapped from `SurfaceResult`.

---

## 6. Canonical runtime flow

### 6.1 High-level flow

```text
HTTP request
  -> payload normalization
  -> normalized frame
  -> frame-to-construction bridge
  -> planner
  -> ConstructionPlan
  -> lexical resolution
  -> renderer dispatch
  -> backend realization
  -> SurfaceResult
  -> API response
```

### 6.2 Flow in terms of runtime objects

```text
Request JSON
  -> normalized_frame
  -> planned_sentence
  -> construction_plan
  -> lexicalized construction_plan
  -> surface_result
  -> Response JSON
```

### 6.3 Authoritative runtime chain

```text
generation router
  -> GenerateText / PlanText orchestrator
  -> frame-to-construction bridge
  -> planner
  -> lexical resolver
  -> realizer
  -> renderer backend
  -> SurfaceResult
  -> response mapper
```

### 6.4 Compatibility rule

Any direct `frame -> engine.generate(...)` path is **compatibility-only** during migration.

It must not be treated as an architectural peer to the planner-first runtime.

---

## 7. Canonical data contracts

This document does not define full schemas, but it defines the runtime boundaries.

### 7.1 Semantic input

A normalized semantic frame must contain:

* `frame_type`
* normalized semantic content
* discourse-relevant entity information where available

Examples include:

* `BioFrame`
* `EventFrame`
* relational/entity frames
* generic normalized frame objects

### 7.2 Construction plan

A `ConstructionPlan` must contain at least:

* `construction_id`
* `lang_code`
* `slot_map`
* `topic_entity_id`
* `focus_role`
* `metadata`

**Alignment note**

`metadata` is the canonical top-level option bag for the shared runtime contract.

If another document or temporary interface refers to `generation_options`, that should be treated as renderer-relevant planning metadata normalized into `metadata` at the contract boundary.

### 7.3 Slot map

A `slot_map` contains semantically named construction inputs, for example:

* `subject`
* `predicate_nominal`
* `predicate_adjective`
* `location`
* `event`
* `agent`
* `patient`
* `theme`
* `time`
* `topic`
* `comment`
* `profession`
* `nationality`

Slot names must be semantic or constructional, not backend-specific.

### 7.4 Lexical resolution

Lexical resolution enriches slot values with:

* `entity_ref` and `lexeme_ref` identity,
* lemma,
* part of speech,
* lexical features,
* provenance,
* confidence,
* explicit fallback notes.

Lexical resolution does not change sentence meaning or information packaging.

### 7.5 Surface result

A `SurfaceResult` must contain:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend`
* `debug_info`

**Alignment note**

`SurfaceResult` is the canonical renderer output before API response mapping.

Older wording such as `Sentence` or `sentence result` should be interpreted as this renderer output unless a different transport model is explicitly defined.

---

## 8. Sequence flow

### 8.1 Request-time flow

```text
Client
  -> API Router
  -> Input Normalizer
  -> Frame-to-Construction Bridge
  -> Planner
  -> Lexical Resolver
  -> Realizer
  -> Backend
  -> Response Mapper
  -> Client
```

### 8.2 Expanded step sequence

1. Client submits payload.
2. Router validates and normalizes payload.
3. Router obtains a normalized frame.
4. Frame-to-construction bridge prepares construction-oriented planning input.
5. Planner selects and finalizes the construction.
6. Planner emits `ConstructionPlan`.
7. Lexical resolver enriches plan slots.
8. Realizer chooses a backend explicitly.
9. Backend realizes the construction.
10. Runtime emits `SurfaceResult`.
11. API packages response and debug metadata.
12. Client receives the sentence response.

---

## 9. Backend dispatch model

### 9.1 Why dispatch exists

Different languages and constructions require different realization strengths.

The runtime therefore supports multiple renderer backends behind one interface.

### 9.2 Backends

#### A. Family-construction backend

Use when:

* the language family is supported,
* construction realization is implemented in family engines,
* morphology/config data is available.

Best for:

* scalable multilingual support,
* family-shared realization,
* morphology-aware generation.

#### B. GF-construction backend

Use when:

* a GF construction exists,
* the grammar path is healthy,
* the construction is representable in the available grammar.

Best for:

* high-quality controlled realization,
* deterministic grammar-backed output,
* selected high-support constructions/languages.

#### C. Safe-mode backend

Use when:

* no stronger backend is available,
* capability is partial,
* the runtime must still produce a controlled fallback.

Best for:

* degraded mode,
* partial coverage languages,
* continuity and debugging.

### 9.3 Dispatch rule

Dispatch is selected by:

* language capability,
* construction capability,
* backend readiness,
* runtime configuration,
* explicit fallback policy.

Dispatch must never change the semantic meaning of the plan.

Dispatch choice must be visible in:

* `renderer_backend`
* `debug_info`

---

## 10. Relationship to the planner

### 10.1 Planner is authoritative

The planner is the runtime authority for:

* selecting `construction_id`
* determining information packaging
* assigning roles into `slot_map`
* topic/focus metadata
* sentence-level semantic ordering

### 10.2 Planner is not a renderer

The planner must not:

* inflect words,
* choose backend-specific syntax directly,
* emit backend-specific ASTs as the primary runtime contract,
* perform final string concatenation.

### 10.3 Existing planner alignment

This runtime flow is aligned with the planner-side concepts:

* `PlannedSentence`
* `construction_id`
* `topic_entity_id`
* `focus_role`

These are not optional side-data. They are part of the planner-centered runtime model.

---

## 11. Relationship to constructions

### 11.1 Constructions are generic

Constructions are language-family-agnostic semantic/syntactic packages.

Examples already present in the system include:

* equative / classification structures
* attributive copular structures
* locative structures
* existential structures
* possession structures
* topic-comment structures
* eventive structures
* relative clauses
* coordination

### 11.2 Construction contract

Every construction must define:

* `construction_id`
* required slots
* optional slots
* validation assumptions
* realization assumptions
* capability notes where needed

### 11.3 Anti-pattern

A backend must not invent a private construction.

If a sentence type exists at runtime, it must be represented as an explicit construction with a registered contract.

---

## 12. Relationship to lexicon

### 12.1 Lexicon is separate by design

The lexicon subsystem remains separate from renderers.

This matters because lexical data must be reusable across:

* multiple constructions,
* multiple backends,
* multiple languages,
* QA and coverage tooling.

### 12.2 Runtime rule

Renderers consume lexical resolution results.

They do not own canonical lexical normalization.

### 12.3 Local vs external lexicon

Runtime lexical resolution may combine:

* local lexicon data,
* alias/normalization tables,
* optional external identifiers such as QIDs,
* controlled raw-string fallback.

The runtime contract must remain stable even when lexical information is partial.

---

## 13. Relationship to morphology

### 13.1 Family engines remain first-class

Morphology engines remain first-class realization components.

This flow preserves that design.

### 13.2 Morphology responsibility

Morphology engines are responsible for:

* inflection,
* feature-driven surface realization,
* agreement,
* family-specific helper logic.

They are not responsible for deciding sentence meaning or construction choice.

### 13.3 Construction-to-morphology boundary

The `ConstructionPlan` determines:

* what roles exist,
* what lexical items are needed,
* what semantic packaging was chosen.

The renderer/morphology layer determines how those roles and lexical items surface in the target language.

---

## 14. Current implementation gap

### 14.1 Existing mismatch

The current live runtime path still allows direct frame-to-engine generation behavior.

That means semantic frames can still bypass the planner-first construction runtime contract.

### 14.2 Why this matters

This creates drift risk:

* planner logic can be bypassed,
* backend-specific assumptions can become hidden architecture,
* one domain can distort the generic runtime model.

### 14.3 Resolution

The target authority order is:

`frame normalization -> frame-to-construction bridge -> planner -> construction runtime contract -> lexical resolution -> backend`

Any direct frame-to-backend generation path is compatibility behavior only.

---

## 15. Migration policy

### 15.1 Policy

Migration proceeds by making the **construction runtime contract authoritative first**, then adapting modules behind it.

### 15.2 Required migration rule

No new runtime feature should bypass:

* construction planning,
* slot mapping,
* lexical resolution,
* renderer dispatch.

### 15.3 Compatibility

Legacy payloads may continue to be accepted at the API boundary.

Compatibility belongs in the **normalization layer**, not in the planner or renderer layers.

### 15.4 Direct-runtime sunset rule

Temporary compatibility fallbacks may exist during migration, but they must:

* be explicit,
* preserve `construction_id`,
* preserve semantic role intent,
* expose fallback usage in `debug_info`,
* be removable once construction coverage is complete.

---

## 16. Debugging and observability

### 16.1 Required debug fields

When debug is enabled, the runtime should expose at least:

* `construction_id`
* `renderer_backend`
* `lang_code`
* lexical resolution summary
* fallback flag
* backend trace

### 16.2 Backend-specific debug

Backends may expose additional metadata such as:

* GF AST or concrete name,
* family engine rule identifiers,
* morphology trace,
* fallback reasons,
* capability tier.

### 16.3 Principle

Debug output should make runtime authority visible:

* which construction was chosen,
* which backend realized it,
* whether fallback occurred,
* whether lexical fallback or compatibility behavior was used.

---

## 17. Example flows

### 17.1 Copular classification

Input:

* subject entity
* class or profession predicate

Flow:

* normalize frame
* bridge to classification planning
* planner chooses `copula_equative_classification`
* `slot_map` binds `subject` and `predicate_nominal`
* lexical resolver resolves the predicate nominal
* renderer realizes the classification sentence

### 17.2 Locative sentence

Input:

* subject entity
* location

Flow:

* normalize frame
* bridge to locative planning
* planner chooses `copula_locative`
* `slot_map` binds `subject` and `location`
* lexical resolver resolves location labeling and lexical features
* renderer realizes the locative form

### 17.3 Biography lead

Input:

* subject
* profession
* nationality

Flow:

* normalize frame
* bridge to biography-lead planning
* planner chooses the appropriate lead construction
* `slot_map` binds subject and identity slots
* lexical resolver resolves profession and nationality
* renderer realizes the sentence according to language/backend capability

Biography is therefore one construction family inside the runtime flow, not the architecture itself.

---

## 18. Non-goals

This document does **not**:

* define every construction schema,
* define every renderer’s internal algorithm,
* require GF to be the only backend,
* require family engines to be removed,
* prescribe one exact `debug_info` shape beyond the shared core fields,
* redesign the semantics model from scratch.

---

## 19. Acceptance criteria

This runtime flow is considered implemented when:

1. generation entrypoints produce or consume `ConstructionPlan`,
2. planner output is authoritative for sentence structure,
3. all renderers accept the same construction-level runtime contract,
4. lexical resolution is reusable across renderers,
5. morphology remains delegated to realization backends,
6. debug output identifies construction and backend,
7. direct frame-to-engine generation is compatibility-only,
8. planner-first generation is the default path for migrated constructions.

---

## 20. Summary

The authoritative SKA runtime flow is:

`HTTP payload -> frame normalization -> frame-to-construction bridge -> planner -> construction plan -> lexical resolution -> renderer dispatch -> surface result -> API response`

This preserves the documented architecture:

* semantics are separate,
* constructions are explicit,
* the planner is authoritative,
* lexicon is reusable,
* morphology remains in realization backends,
* renderers are pluggable,
* and no single backend is allowed to become the hidden architecture.
