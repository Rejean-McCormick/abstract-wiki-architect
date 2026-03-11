# Construction Renderer Contract

Status: normative  
Owner: Architecture / Runtime  
Scope: renderer-facing contract for all construction-based surface realization in SemantiK Architect (SKA)

---

## 1. Purpose

This document defines the authoritative contract between:

- the planner / construction-selection layer, and
- the renderer backends that produce surface text.

It exists to prevent drift between:

- API payload normalization,
- discourse planning,
- construction modules,
- lexical resolution,
- family-engine realization,
- GF-based realization,
- safe-mode fallback rendering.

This contract is generic across constructions.  
It is not specific to biography leads.

The governing rule is:

> one `ConstructionPlan` in, one `SurfaceResult` out, many renderer backends behind the same boundary

---

## 2. Architectural position

The renderer contract sits in this canonical runtime flow:

`frame normalization -> construction selection -> planner -> construction plan -> lexical resolution -> renderer -> surface result`

The renderer:

- does not choose the construction,
- does not own frame normalization,
- does not invent semantics,
- does not bypass lexical resolution rules,
- does not define API payload shapes.

The renderer is responsible only for:

1. consuming a validated construction plan,
2. realizing it for a target language/backend,
3. returning deterministic structured output.

---

## 3. Design principles

### 3.1 One construction contract, multiple backends

All renderers MUST consume the same construction-level input.

Allowed backend families include:

- `family`
- `gf`
- `safe_mode`
- future specialized renderers

### 3.2 Construction-first, not backend-first

The planner decides what sentence to say.  
The renderer decides how the selected backend says it.

### 3.3 Language-family reuse first

Renderers SHOULD maximize reuse across language families and minimize per-language bespoke code.

### 3.4 Lexicon stays external

Lexical resolution is upstream of the renderer.  
A renderer MAY consume lexical bindings, but it MUST NOT silently become its own private lexicon subsystem.

### 3.5 Deterministic by default

Given the same normalized input, backend selection, and language configuration, renderer output SHOULD be deterministic unless explicitly documented otherwise.

### 3.6 Backend substitution is a requirement

Any supported renderer backend MUST be able to consume the same `ConstructionPlan` for a supported `construction_id`.

---

## 4. Non-goals

This contract does not define:

- external API payload schemas,
- discourse-state update rules,
- frame normalization rules,
- lexicon harvesting,
- GF compiler/build tooling,
- QA dashboards,
- user-facing transport models.

Those are separate concerns.

---

## 5. Normative language

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

---

## 6. Canonical entities

## 6.1 ConstructionPlan

A `ConstructionPlan` is the canonical renderer input.

It represents one planned sentence or one clause-level realization unit.

### Required fields

- `construction_id: str`
- `lang_code: str`
- `slot_map: dict[str, Any]`
- `generation_options: dict[str, Any]`

### Optional fields

- `topic_entity_id: str | None`
- `focus_role: str | None`
- `lexical_bindings: dict[str, Any] | None`
- `provenance: dict[str, Any] | None`

### Invariants

- `construction_id` MUST identify a registered construction.
- `construction_id` MUST use the canonical runtime identifier format used across the planner/runtime boundary.
- `lang_code` MUST be normalized before renderer entry.
- `slot_map` MUST already reflect planner-level semantic role assignment.
- `generation_options` MUST contain only realization-relevant options.
- `lexical_bindings`, when present, MUST be treated as upstream lexical decisions rather than renderer hints.

### Compatibility rule

Older internal code may still refer to planner-side `metadata` or a broader `PlannedSentence`.  
At the renderer boundary, those MUST be normalized into `ConstructionPlan`, with renderer-relevant options carried in `generation_options`.

---

## 6.2 SlotMap

A `SlotMap` is the normalized argument bundle passed to a construction renderer.

It contains semantic-role-shaped values, not raw API payload fragments.

Examples of slot names include:

- `subject`
- `predicate_nominal`
- `predicate_adjective`
- `topic`
- `location`
- `existent`
- `possessor`
- `possessed`
- `event`
- `object`
- `time`
- `manner`
- `complement`

The exact slot inventory depends on `construction_id`.

### Slot rules

- Slot names MUST be construction-semantic, not backend-specific.
- Slot values MUST be normalized objects or primitives, not mixed raw payload fragments.
- Slot values SHOULD remain stable across renderers for the same construction.
- A renderer MUST consume `slot_map` rather than reinterpret raw frame fragments.

---

## 6.3 GenerationOptions

`generation_options` is a renderer-safe options object.

Typical keys include:

- `tense`
- `aspect`
- `polarity`
- `register`
- `definiteness`
- `voice`
- `style`
- `allow_fallback`
- `force_backend`
- `debug`

### Rules

- Unsupported options MUST be ignored safely or recorded in `debug_info`.
- A renderer MUST NOT crash solely because an optional option is unknown.
- Backend-specific options MAY exist, but MUST live under a namespaced key.

Example:

```json
{
  "tense": "present",
  "register": "neutral",
  "allow_fallback": true,
  "backend": {
    "gf": {
      "prefer_concrete": "WikiFre"
    }
  }
}
````

### Boundary rule

`generation_options` is the canonical renderer-facing options field.
Ad hoc names such as `gf_payload`, `engine_payload`, `template_payload`, or `render_input` MUST NOT become shared runtime contract names.

---

## 6.4 LexicalBindings

`lexical_bindings` contains lexical decisions made upstream.

This allows the planner / lexical resolver to attach normalized `entity_ref` and `lexeme_ref` information to construction roles.

Example structure:

```json
{
  "subject_head": {
    "label": "Marie Curie",
    "entity_id": "Q7186",
    "entity_type": "person",
    "features": {
      "number": "sg",
      "person": 3
    }
  },
  "profession": {
    "lemma": "physicist",
    "lexeme_id": null,
    "qid": "Q169470",
    "pos": "NOUN",
    "source": "wikidata",
    "confidence": 0.93,
    "features": {
      "human": true
    }
  },
  "nationality": {
    "lemma": "Polish",
    "lexeme_id": null,
    "qid": "Q36",
    "pos": "ADJ",
    "source": "wikidata",
    "confidence": 0.89
  }
}
```

### Rules

* Renderers MUST treat lexical bindings as authoritative when present.
* Renderers MAY fall back to slot content only when lexical bindings are absent or incomplete.
* Lexical fallback MUST be recorded in `debug_info`.
* Renderers MUST NOT silently substitute semantically unrelated lexical items.

### Practical rule

The renderer may choose the surface form.
It may not redefine lexical identity unless explicit fallback is invoked.

---

## 7. Renderer interface

All renderer backends MUST implement the same logical interface.

## 7.1 Required method

```python
async def realize(plan: ConstructionPlan) -> SurfaceResult:
    ...
```

Synchronous wrappers MAY exist, but the canonical runtime interface is asynchronous.

## 7.2 Required behavior

A renderer MUST:

1. validate that it can handle the requested `construction_id`,
2. validate that required slots are present,
3. validate that `lang_code` is normalized,
4. attempt realization for the target language,
5. return a structured `SurfaceResult`,
6. expose fallback and backend trace information in `debug_info`.

A renderer MUST NOT:

* mutate the caller’s `ConstructionPlan`,
* silently reinterpret the construction as a different one,
* silently discard required slots,
* invent semantic content not present in the plan,
* hide fallback behavior.

---

## 8. SurfaceResult

A `SurfaceResult` is the canonical renderer output.

### Required fields

* `text: str`
* `lang_code: str`
* `construction_id: str`
* `renderer_backend: str`
* `debug_info: dict[str, Any]`

### Optional fields

* `tokens: list[str] | None`
* `warnings: list[str] | None`
* `fallback_used: bool`
* `confidence: float | None`

### Invariants

* `text` MUST be a final surface string or a clearly marked failure placeholder.
* `lang_code` MUST equal the normalized input language code.
* `construction_id` MUST equal the input construction.
* `renderer_backend` MUST identify the backend actually used.

### Compatibility rule

Older code may still use a broader `Sentence` domain object.
At the renderer contract boundary, the canonical output shape is `SurfaceResult`.

---

## 9. Required debug_info contract

Every backend MUST return a structured `debug_info` object.

### Required keys

* `construction_id`
* `renderer_backend`
* `lang_code`
* `slot_keys`
* `fallback_used`

### Recommended keys

* `requested_backend`
* `backend_trace`
* `lexical_sources`
* `missing_slots`
* `unsupported_features`
* `template_id`
* `family`
* `resolved_language`
* `concrete_name`
* `ast`
* `surface_tokens`
* `warnings`
* `fallback_reason`
* `timings_ms`

### Rules

* `debug_info` MUST be machine-readable.
* Shared keys SHOULD remain stable across backends.
* Backend-specific keys MAY be added, but MUST NOT replace shared keys.
* Fallback reasons MUST be explicit when fallback occurs.

### Example

```json
{
  "construction_id": "copula_equative_simple",
  "renderer_backend": "family",
  "lang_code": "fr",
  "slot_keys": ["subject", "predicate_nominal"],
  "fallback_used": false,
  "family": "romance",
  "template_id": "equative.default",
  "backend_trace": [
    "validated construction",
    "selected romance renderer",
    "resolved subject np",
    "resolved copula",
    "assembled clause"
  ]
}
```

GF-specific example:

```json
{
  "construction_id": "bio_lead_identity",
  "renderer_backend": "gf",
  "lang_code": "fr",
  "slot_keys": ["subject", "profession", "nationality"],
  "fallback_used": false,
  "resolved_language": "WikiFre",
  "concrete_name": "WikiFre",
  "ast": "mkBioLeadIdentity ...",
  "backend_trace": [
    "selected gf backend",
    "mapped construction plan to ast",
    "linearized with WikiFre"
  ]
}
```

---

## 10. Error and fallback semantics

## 10.1 Validation failure

If the renderer cannot realize the plan because required information is missing or malformed, it MUST return a structured failure result or raise a typed runtime exception according to the application boundary.

It MUST NOT emit silently degraded text without marking fallback.

## 10.2 Unsupported construction

If a backend does not support the requested `construction_id`, it MUST:

* return an explicit unsupported signal, or
* allow a higher-level dispatcher to fall through to the next backend.

It MUST NOT pretend support and produce semantically unrelated output.

## 10.3 Fallback usage

If fallback rendering is used, the renderer MUST set:

* `fallback_used = true`

and MUST explain the reason in `debug_info`.

Example reasons include:

* backend does not support construction
* lexical binding missing
* target language missing family config
* GF concrete unavailable
* grammar linearization failed

## 10.4 Fallback invariants

Fallback MUST preserve:

* `construction_id`
* semantic role intent
* `lang_code`

Fallback MUST annotate:

* requested backend
* final backend
* reason
* any lexical degradation applied

---

## 11. Backend taxonomy

The system may include multiple backends.

## 11.1 Family renderer

The family renderer is the preferred generalized backend for many languages.

Responsibilities:

* apply language-family-level construction patterns
* call morphology APIs
* apply language-card overrides
* assemble clause structure deterministically

Characteristics:

* high reuse
* typology-driven
* construction-aware
* scalable to many languages

## 11.2 GF renderer

The GF renderer is an optional backend that maps a `ConstructionPlan` to GF constructs and linearizes them.

Responsibilities:

* consume the same normalized construction plan
* map construction slots to GF expressions
* expose AST/concrete metadata

Characteristics:

* precise where grammar support exists
* potentially narrower coverage
* MUST NOT define the global architecture by itself

## 11.3 Safe-mode renderer

The safe-mode renderer is the lowest-common-denominator backend.

Responsibilities:

* provide minimal intelligible output
* preserve semantics as much as possible
* make fallback explicit

Characteristics:

* lower quality
* highest survivability
* never hidden

---

## 12. Capability requirements

Each renderer backend SHOULD expose explicit capability checks.

Suggested interface:

```python
def supports(construction_id: str, lang_code: str) -> bool:
    ...
```

### Capability rules

* Capability checks SHOULD be cheap.
* Capability checks MUST NOT trigger full generation.
* Capability checks SHOULD be used by dispatcher/orchestration layers before realization attempts.

---

## 13. Construction support matrix

Every backend SHOULD conceptually support a matrix:

`construction_id x lang_code -> support status`

Support statuses MAY include:

* `full`
* `partial`
* `fallback_only`
* `unsupported`

This matrix is useful for:

* runtime dispatch
* tests
* QA reporting
* tooling
* future build health integration

---

## 14. Lexical resolution boundary

Lexical resolution happens before rendering.

The renderer MAY:

* consume lexical bindings,
* request simple fallback normalization,
* add debug notes about missing lexical information.

The renderer MUST NOT:

* become the canonical place where lexicon IDs are assigned,
* silently substitute semantically unrelated lexical items,
* embed its own hidden lexicon tables as a primary strategy.

---

## 15. Planner boundary

The planner owns:

* construction choice
* role assignment
* topic/focus structure
* sentence packaging
* ordering at the semantic/discourse level
* default realization options

The renderer owns:

* morphosyntactic realization
* backend-specific assembly
* token joining
* local ordering required by the target language
* surface fallback

### Key rule

The renderer MUST NOT change `construction_id`.

If a different construction is needed, that is a planner concern.

### Clarification

Upstream objects such as `PlannedSentence` MAY still exist in the architecture.
They are planner-side abstractions, not renderer inputs.

---

## 16. Determinism and reproducibility

Renderers SHOULD be deterministic.

A renderer MUST document any nondeterministic behavior.

### Minimum reproducibility requirements

A renderer SHOULD make it possible to reconstruct output from:

* `construction_id`
* `lang_code`
* `slot_map`
* `generation_options`
* `lexical_bindings`
* backend version / config version

`debug_info` SHOULD contain enough information to support regression testing.

---

## 17. Performance expectations

Renderers SHOULD:

* validate cheaply,
* fail early on missing required slots,
* avoid repeated lexical work already done upstream,
* expose backend timings when debug mode is enabled.

GF backends SHOULD avoid repeated grammar loads inside hot realization paths.

Family backends SHOULD reuse morphology/config caches when possible.

---

## 18. Security and safety

Renderers MUST treat all incoming strings as untrusted data.

### Required safeguards

* escape backend-specific special characters where needed,
* avoid arbitrary code execution through template fields,
* avoid raw string interpolation into executable grammar/compiler calls,
* sanitize debug output to avoid leaking secrets or internal paths unnecessarily.

---

## 19. Minimal reference shapes

## 19.1 ConstructionPlan example

```json
{
  "construction_id": "copula_equative_simple",
  "lang_code": "fr",
  "slot_map": {
    "subject": {
      "label": "Marie Curie",
      "entity_id": "Q7186",
      "entity_type": "person",
      "features": {
        "person": 3,
        "number": "sg"
      }
    },
    "predicate_nominal": {
      "role": "profession_plus_nationality",
      "features": {
        "human": true
      }
    }
  },
  "generation_options": {
    "tense": "past",
    "register": "neutral",
    "allow_fallback": true
  },
  "topic_entity_id": "Q7186",
  "focus_role": "predicate_nominal",
  "lexical_bindings": {
    "profession": {
      "lemma": "physicist",
      "qid": "Q169470",
      "pos": "NOUN",
      "source": "wikidata",
      "confidence": 0.93
    },
    "nationality": {
      "lemma": "Polish",
      "qid": "Q36",
      "pos": "ADJ",
      "source": "wikidata",
      "confidence": 0.89
    }
  }
}
```

## 19.2 SurfaceResult example

```json
{
  "text": "Marie Curie était une physicienne polonaise.",
  "lang_code": "fr",
  "construction_id": "copula_equative_simple",
  "renderer_backend": "family",
  "fallback_used": false,
  "tokens": [
    "Marie Curie",
    "était",
    "une",
    "physicienne",
    "polonaise"
  ],
  "debug_info": {
    "construction_id": "copula_equative_simple",
    "renderer_backend": "family",
    "lang_code": "fr",
    "slot_keys": ["subject", "predicate_nominal"],
    "fallback_used": false,
    "family": "romance",
    "backend_trace": [
      "validated slots",
      "resolved predicate lexical bindings",
      "assembled equative clause"
    ]
  }
}
```

---

## 20. Migration rules

During migration from older direct-generation code paths:

1. old paths MAY remain as compatibility shims,
2. new code MUST target this contract,
3. backends MUST converge on `ConstructionPlan -> SurfaceResult`,
4. planner-side `metadata` MUST be normalized into `generation_options` before renderer entry when those values affect realization,
5. construction-specific shims SHOULD be removed after parity is reached.

Compatibility layers MUST be temporary and clearly labeled.

---

## 21. Acceptance criteria

This contract is considered implemented when:

1. all active renderer backends accept the same `ConstructionPlan` shape,
2. all backends return `SurfaceResult`,
3. `construction_id` is planner-owned and stable end-to-end,
4. lexical fallback is explicit,
5. `debug_info` is structured and comparable across backends,
6. at least one non-bio construction and one bio construction use the same runtime contract.

---

## 22. Open questions

The following remain implementation decisions, not contract blockers:

* whether `ConstructionPlan` wraps `PlannedSentence` or is built from it,
* whether lexical bindings are embedded or referenced by ID,
* how strict capability checking should be at dispatch time,
* how much backend-specific trace detail to expose in production.

These decisions MUST NOT break the top-level contract defined here.

---

## 23. Final rule

If two backends require different planner-facing inputs, the contract is broken.

The whole point of this document is:

> one construction plan in, one surface result out, many backends behind it
