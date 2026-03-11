# Construction Runtime Contract

Status: proposed  
Owner: SKA runtime / architecture  
Last updated: 2026-03-10

---

## 1. Purpose

This document defines the authoritative runtime contract between:

1. frame normalization,
2. construction selection,
3. discourse / sentence planning,
4. construction-plan building,
5. lexical resolution,
6. realization backends,
7. API response mapping.

It exists to prevent architectural drift.

The contract is intentionally construction-centric, not bio-centric.

This means:

- biography lead generation is one consumer of this contract,
- locatives, equatives, existentials, possession, topic-comment, eventive clauses, relative clauses, and future constructions must use the same runtime shape,
- no backend is allowed to invent a competing sentence contract.

---

## 2. Scope

This contract governs all single-sentence runtime generation paths that start from normalized semantic input and end in a canonical surface result.

It applies to:

- planner output,
- construction-plan output,
- lexical resolution input/output,
- renderer input,
- debug metadata,
- backend selection,
- fallback semantics,
- API response mapping.

It does not define:

- the full external API schema for every frame family,
- GF abstract or concrete grammar internals,
- family-specific morphology implementation details,
- multi-sentence discourse policy beyond per-sentence metadata.

### Migration note

At the renderer boundary, the canonical result object is `SurfaceResult`.

During migration, existing code may still use a `Sentence` domain type as a compatibility wrapper or adapter for the same logical result. That compatibility type MUST NOT become a competing contract.

---

## 3. Core architectural rule

The canonical runtime flow is:

```text
normalized frame(s)
  -> construction selection
  -> planner
  -> planned sentence
  -> construction-plan builder
  -> construction plan
  -> lexical resolution
  -> renderer backend
  -> surface result
````

No component may bypass this contract and become a second source of truth for sentence structure.

In particular:

* routers must not decide wording,
* renderers must not invent semantics,
* lexical resolvers must not choose discourse packaging,
* GF adapters must not become the primary semantic contract,
* family engines must not redefine construction meaning,
* direct `/generate` shortcuts must remain compatibility shims only during migration.

---

## 4. Design goals

This contract must satisfy all of the following:

1. **Generic across constructions**

   * Must support more than biography.

2. **Backend-agnostic**

   * Must work for GF, family engines, and safe-mode fallback.

3. **Language-scalable**

   * Must support family-level and language-level specialization without duplicating planning logic.

4. **Debuggable**

   * Every runtime decision must be traceable.

5. **Backward-compatible**

   * Existing API payloads may remain tolerated, but must normalize into this contract.

6. **Deterministic**

   * The same normalized construction plan should produce stable output under the same backend/configuration.

---

## 5. Normative keywords

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are used normatively in this document.

---

## 6. Canonical runtime objects

### 6.1 `PlannedSentence`

`PlannedSentence` is the canonical planner output.

It represents one sentence-level planning decision before renderer-facing realization packaging is finalized.

Required fields:

* `construction_id: str`
* `lang_code: str`
* `topic_entity_id: str | None`
* `focus_role: str | None`
* `discourse_mode: str | None`
* `generation_options: dict[str, Any]`

Optional fields:

* `metadata: dict[str, Any]`
* `source_frame_ids: list[str] | None`
* `priority: int | None`

Rules:

* `construction_id` MUST identify a registered construction.
* `lang_code` MUST be normalized before renderer selection.
* `generation_options` MUST contain planner-approved realization options.
* `metadata` MAY carry planner diagnostics and provenance, but MUST NOT be the only place where required renderer behavior is encoded.

### 6.2 `ConstructionPlan`

`ConstructionPlan` is the canonical renderer-facing handoff.

It represents one validated construction ready for lexical resolution and realization.

Required fields:

* `construction_id: str`
* `lang_code: str`
* `slot_map: SlotMap`
* `generation_options: dict[str, Any]`

Optional fields:

* `topic_entity_id: str | None`
* `focus_role: str | None`
* `discourse_mode: str | None`
* `lexical_bindings: dict[str, Any] | None`
* `metadata: dict[str, Any]`
* `provenance: dict[str, Any] | None`

Rules:

* `construction_id` MUST identify a registered construction.
* `slot_map` MUST be the only semantic-role container consumed by renderers.
* `generation_options` is the canonical renderer-safe options object.
* `metadata` MAY exist for planner diagnostics, migration notes, or provenance, but renderers MUST NOT depend on undocumented keys hidden inside `metadata`.
* `lexical_bindings` MAY be attached before or after lexical resolution, but if present they are authoritative for lexical identity.

### 6.3 `SlotMap`

`SlotMap` is the canonical role/value payload for one construction.

Shape:

```python
SlotMap = dict[str, Any]
```

Rules:

* keys MUST be semantic or constructional roles, not backend-specific names,
* values MUST be normalized objects or scalars accepted by the role contract,
* renderers MUST read from `slot_map` rather than raw frames.

Examples of role names:

* `subject`
* `predicate`
* `predicate_nominal`
* `predicate_adjective`
* `object`
* `location`
* `theme`
* `possessor`
* `possessed`
* `event`
* `time`
* `manner`
* `comparison`
* `topic`

### 6.4 `EntityRef`

`EntityRef` is the canonical entity reference object.

Minimum shape:

```python
{
  "label": "Alan Turing",
  "entity_id": "Q7251",
  "entity_type": "person",
  "gender": "m"
}
```

Required fields:

* `label: str`

Optional fields:

* `entity_id: str | None`
* `qid: str | None`
* `entity_type: str | None`
* `gender: str | None`
* `number: str | None`
* `person: str | None`
* `surface_hint: str | None`
* `features: dict[str, Any]`

Rules:

* `label` MUST be human-readable.
* `entity_id` SHOULD be stable when available.
* `qid` MAY be used as an external identity reference.
* `features` MAY carry renderer-relevant information, but must remain semantic or lexical rather than backend-internal.

### 6.5 `LexemeRef`

`LexemeRef` is the canonical lexical reference object.

Minimum shape:

```python
{
  "lemma": "mathematician",
  "lexeme_id": null,
  "pos": "NOUN",
  "source": "raw",
  "confidence": 0.0
}
```

Required fields:

* `lemma: str`

Optional fields:

* `lexeme_id: str | None`
* `qid: str | None`
* `pos: str | None`
* `surface_hint: str | None`
* `source: str`
* `confidence: float`
* `features: dict[str, Any]`

Rules:

* `lemma` MUST be backend-agnostic.
* `source` SHOULD identify where the lexical reference came from, for example `raw`, `local_lexicon`, `wikidata`, `bridge`.
* `confidence` SHOULD be in `[0.0, 1.0]`.

### 6.6 `SurfaceResult`

`SurfaceResult` is the canonical renderer result before API serialization.

Minimum shape:

```python
{
  "text": "Alan Turing is a British mathematician.",
  "lang_code": "en",
  "construction_id": "copula_equative_classification",
  "renderer_backend": "gf",
  "debug_info": {}
}
```

Required fields:

* `text: str`
* `lang_code: str`
* `construction_id: str`
* `renderer_backend: str`
* `debug_info: dict[str, Any]`

Optional fields:

* `fallback_used: bool`
* `tokens: list[str] | None`
* `warnings: list[str] | None`
* `timing_ms: float | None`

Rules:

* `text` MUST be non-empty on successful realization.
* `debug_info` MUST be machine-readable.
* `fallback_used` MAY appear top-level and SHOULD also be reflected in `debug_info`.

---

## 7. Canonical variable names

The following names are mandatory across new runtime code and documentation.

### 7.1 Required names

* `lang_code`
* `planned_sentence`
* `construction_plan`
* `construction_id`
* `slot_map`
* `generation_options`
* `entity_ref`
* `lexeme_ref`
* `renderer_backend`
* `surface_result`
* `debug_info`

### 7.2 Preferred names

* `normalized_frame`
* `topic_entity_id`
* `focus_role`
* `discourse_mode`
* `lexical_bindings`
* `provenance`

### 7.3 Compatibility names

The following names MAY remain as compatibility terms during migration, but must not define competing contracts:

* `sentence` as a compatibility wrapper for `SurfaceResult`
* `metadata` as a general diagnostics or provenance bag

### 7.4 Disallowed drift names

The following MUST NOT become top-level canonical runtime names:

* `bio_payload`
* `gf_payload`
* `engine_payload`
* `template_payload`
* `render_input`
* `surface_text` as the canonical output field name
* `metadata` as the only renderer-facing options bag
* `sentence_spec` as a generic replacement for `construction_plan`

These names may exist locally, but not as the authoritative shared contract.

---

## 8. Construction registry contract

Every runtime construction MUST declare:

* `construction_id`
* required roles
* optional roles
* cardinality rules
* supported sentence kinds
* validation rules
* lexical requirements
* renderer capability expectations
* fallback behavior if applicable

Minimum registry entry:

```python
{
  "construction_id": "copula_equative_classification",
  "required_roles": ["subject", "predicate_nominal"],
  "optional_roles": ["modifier", "time", "manner"],
  "sentence_kind": "definition",
  "domain_tags": ["generic", "entity"],
  "supports_topic_comment": True
}
```

Rules:

* planner output MUST reference only registered constructions,
* renderers MUST reject unknown `construction_id` values explicitly,
* construction validation MUST happen before surface realization.

### Construction ID rule

Canonical `construction_id` values MUST use snake_case identifiers, for example:

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_locative`
* `possession_have`
* `topic_comment_eventive`

Legacy dotted forms MAY be tolerated as migration aliases in normalization or documentation, but MUST NOT become the new canonical runtime IDs.

---

## 9. Planner contract

### 9.1 Planner responsibilities

The planner MUST decide:

* which construction is used,
* whether a wrapper construction is used,
* topic/focus metadata,
* discourse packaging,
* sentence ordering at the sentence level,
* planner-level generation options,
* fallback construction selection where needed.

The planner MUST NOT decide:

* final wording,
* morphology,
* GF AST internals,
* backend-specific formatting,
* backend dispatch.

### 9.2 Planner output requirements

For every sentence plan, the planner MUST emit a `PlannedSentence` containing at least:

* `construction_id`
* `lang_code`
* `topic_entity_id`
* `focus_role`
* `discourse_mode`
* `generation_options`

The planner MAY emit:

* `metadata`
* `priority`
* `sentence_kind`
* `source_frame_ids`

### 9.3 Construction-plan builder responsibilities

The construction-plan builder, bridge, or equivalent runtime step MUST:

* convert `PlannedSentence` into `ConstructionPlan`,
* produce a valid canonical `slot_map`,
* normalize slot values into `EntityRef`, `LexemeRef`, literals, or structured slot objects as required,
* attach realization-relevant metadata,
* validate construction completeness before realization.

### 9.4 Generic planner entrypoint

The authoritative planner entrypoint SHOULD follow this signature:

```python
def plan_text(
    frames: Iterable[Any],
    *,
    lang_code: str,
    domain: str = "auto",
) -> list[PlannedSentence]:
    ...
```

### 9.5 Construction-plan builder entrypoint

The authoritative renderer-facing bridge SHOULD follow this signature:

```python
def build_construction_plan(
    planned_sentence: PlannedSentence,
    *,
    normalized_frame: Any | None = None,
) -> ConstructionPlan:
    ...
```

---

## 10. Lexical resolution contract

### 10.1 Purpose

Lexical resolution converts semantic slot values into stable lexical references usable by renderers.

### 10.2 Lexical resolver responsibilities

The lexical resolver MUST:

* preserve semantic intent,
* normalize raw strings when possible,
* produce `LexemeRef` and `EntityRef` objects where applicable,
* annotate provenance,
* provide confidence and fallback information,
* return a lexicalized `ConstructionPlan` or equivalent normalized slot payload.

The lexical resolver MUST NOT:

* choose sentence structure,
* choose topic/focus,
* silently drop required semantic content,
* silently replace one construction with another.

### 10.3 Canonical lexical resolver interface

Preferred interface:

```python
class LexicalResolverPort(Protocol):
    def resolve(
        self,
        construction_plan: ConstructionPlan,
        *,
        lang_code: str,
    ) -> ConstructionPlan:
        ...
```

Allowed internal helper interface:

```python
class LexicalResolverPort(Protocol):
    def resolve_slot_map(
        self,
        slot_map: dict[str, Any],
        *,
        lang_code: str,
    ) -> dict[str, Any]:
        ...
```

Rules:

* the canonical runtime effect is lexicalized construction-plan output,
* helper methods MAY work at slot-map level,
* renderers MUST NOT become the hidden lexical resolver.

---

## 11. Renderer contract

### 11.1 Renderer responsibilities

A renderer backend MUST:

* accept a validated `ConstructionPlan`,
* consume the canonical `slot_map`,
* realize one sentence,
* return `SurfaceResult`,
* expose backend-specific debug data through `debug_info`.

A renderer backend MUST NOT:

* redefine construction semantics,
* bypass slot validation,
* rewrite planner meaning silently,
* change `construction_id`.

### 11.2 Canonical renderer interface

Preferred interface:

```python
class RealizerPort(Protocol):
    async def realize(
        self,
        construction_plan: ConstructionPlan,
    ) -> SurfaceResult:
        ...
```

### 11.3 Renderer backend names

Allowed canonical values:

* `gf`
* `family`
* `safe_mode`

Additional values MAY be added later, but all runtime debug and test artifacts MUST use the same string consistently.

### 11.4 Backend selection

Backend selection policy MUST be explicit.

Selection MAY consider:

* language capability,
* construction capability,
* engine availability,
* configuration flags,
* forced backend override,
* degraded mode.

Selection result MUST be recorded in `renderer_backend` and `debug_info`.

---

## 12. API contract boundary

### 12.1 Router behavior

Routers MAY accept legacy or ergonomic payloads.

Routers MUST normalize them into internal frames and then hand off to planner-centered runtime generation.

Routers MUST NOT directly encode sentence wording.

### 12.2 Response mapping

The final API response MAY remain:

```json
{
  "text": "...",
  "lang_code": "en",
  "debug_info": {}
}
```

But internally it MUST originate from `SurfaceResult`.

### 12.3 Backward compatibility

The runtime MAY continue to support current `bio`-style payloads during migration.

However:

* legacy input shape compatibility MUST terminate at normalization,
* downstream runtime logic MUST consume `PlannedSentence` and `ConstructionPlan`, not raw payload quirks.

---

## 13. Debug info contract

`debug_info` is required for all runtime surfaces.

Minimum fields:

* `construction_id`
* `renderer_backend`

Recommended fields:

* `lang_code`
* `resolved_language`
* `planner`
* `lexical_resolution`
* `fallback_used`
* `selected_backend`
* `attempted_backends`
* `capability_tier`
* `backend_trace`
* `ast` for GF only
* `template_id` for family or safe-mode only when relevant

Rules:

* `debug_info` MUST be machine-readable,
* backend-specific fields MAY exist,
* shared keys SHOULD remain stable across backends,
* fallback behavior MUST be explicit.

Example:

```json
{
  "construction_id": "copula_equative_classification",
  "renderer_backend": "gf",
  "lang_code": "en",
  "resolved_language": "WikiEng",
  "selected_backend": "gf",
  "attempted_backends": ["gf"],
  "lexical_resolution": {
    "subject": "entity_ref",
    "predicate_nominal": "lexeme_ref"
  },
  "fallback_used": false,
  "ast": "mkCopulaEquative ..."
}
```

---

## 14. Validation rules

### 14.1 Construction validation

Before realization, the runtime MUST validate:

* construction is registered,
* required roles are present,
* role value types are acceptable,
* multiplicity rules are respected,
* `lang_code` is normalized,
* renderer can attempt this construction.

### 14.2 Failure behavior

Validation failures MUST be explicit.

Preferred failure classes:

* unknown construction,
* missing required role,
* invalid slot type,
* lexical resolution failure,
* renderer unsupported,
* runtime generation failure.

These MUST be distinguishable in logs and SHOULD be distinguishable in tests.

---

## 15. Fallback policy

Fallback must be explicit, not silent.

### 15.1 Allowed fallback sequence

Preferred order:

1. primary backend for language/construction
2. alternate deterministic backend
3. safe-mode backend
4. explicit failure

### 15.2 Fallback invariants

Fallback MUST preserve:

* `construction_id`
* semantic role intent
* `lang_code`

Fallback MUST annotate:

* `fallback_used`
* original backend
* final backend
* reason

---

## 16. Capability tier integration

The runtime contract is compatible with tiered language support.

Recommended interpretation:

* **Tier 1** — high-road realization
* **Tier 2** — family renderer with strong morphology support
* **Tier 3** — safe-mode deterministic fallback
* **Tier 4** — unsupported / fail closed

Capability tier MUST NOT change planner semantics.
It only changes realization strategy.

---

## 17. Migration rule

During migration, existing direct runtime paths MAY remain temporarily.

But they MUST be treated as compatibility paths, not architectural peers.

Target end state:

* planner and construction runtime contract are authoritative,
* all renderers consume the same `ConstructionPlan`,
* direct frame-to-renderer generation is removed or reduced to an internal adapter,
* `Sentence` remains at most a compatibility wrapper around `SurfaceResult`.

---

## 18. Initial construction coverage

The following construction families are expected to conform to this contract:

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
* `passive_event`
* `relative_clause_subject_gap`
* `relative_clause_object_gap`
* `coordination_clauses`

Biography lead constructions remain one specialization within this generic system.

This document does not require all of them to migrate at once, but it defines the target runtime contract for all of them.

---

## 19. Non-goals

This contract does not attempt to:

* formalize every linguistic category,
* force all backends to share identical internal mechanics,
* replace language-specific morphology logic,
* define full multi-sentence discourse generation,
* make GF the required system core.

---

## 20. Acceptance criteria

The runtime contract is successfully implemented when:

1. planner output is represented as `PlannedSentence`,
2. renderer-facing handoff is represented as `ConstructionPlan`,
3. all new generation code consumes `slot_map`,
4. `generation_options` is the canonical renderer-safe options object,
5. renderers expose `renderer_backend` and `debug_info`,
6. lexical resolution is explicit and testable,
7. the API runtime no longer treats one construction family as architecturally special,
8. at least two backends can realize the same construction plan,
9. direct payload quirks no longer leak below normalization.

---

## 21. Summary

The system’s runtime source of truth is:

* construction-centered,
* planner-first,
* bridge-to-plan explicit,
* backend-agnostic,
* family-scalable,
* lexicon-aware,
* debuggable.

Everything else must align to that.


