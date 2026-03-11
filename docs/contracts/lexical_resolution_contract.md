# Lexical Resolution Contract

Status: normative
Owner: SKA runtime / lexicon / realization
Last updated: 2026-03-10

---

## 1. Purpose

This document defines the **lexical resolution contract** for SemantiK Architect (SKA).

Lexical resolution is the runtime step that converts semantic slot values from a `construction_plan` into stable, backend-agnostic lexical references that renderers can consume deterministically.

It exists to separate:

* **what the sentence means** from
* **which lexical identities should express that meaning**.

This contract is generic across constructions and languages. It is **not** bio-specific.

---

## 2. Position in the runtime

Canonical runtime flow:

```text
frame normalization
  -> planner
  -> construction_plan
  -> lexical resolution
  -> renderer backend
  -> surface_result
```

Lexical resolution happens **after planning** and **before realization**.

It consumes a validated `construction_plan`.

It produces a **lexicalized construction plan** by:

* normalizing lexicalized slot values,
* attaching `entity_ref` / `lexeme_ref` values where possible,
* recording per-slot provenance and fallback,
* making lexical identity explicit before renderer entry.

Lexical resolution is upstream of all renderers, including:

* GF renderer,
* family renderer,
* safe-mode renderer.

---

## 3. Why lexical resolution is separate

Lexical resolution must not be hidden inside renderers.

Reasons:

1. Multiple renderers must be able to consume the same lexical interpretation.
2. Lexical fallback must be visible and testable.
3. Morphology and syntax need stable lexical inputs.
4. Planning and realization must not duplicate lexical lookup logic.
5. Debugging multilingual failures requires explicit lexical provenance.
6. Renderer backends must remain realization-only layers.

---

## 4. Scope

This contract governs runtime lexical resolution of lexicalized slots such as:

* entities,
* professions,
* nationalities,
* predicates,
* relations,
* roles,
* event labels,
* locations,
* titles / classes / offices,
* other lexicalized slot values required by constructions.

This contract does **not** define:

* sentence planning,
* construction selection,
* morphology realization,
* word order,
* punctuation policy,
* discourse topic/focus decisions,
* external API transport schemas.

---

## 5. Core principles

1. **Planner decides semantics.**
2. **Lexical resolver decides lexical identity.**
3. **Renderer decides surface form.**
4. **Lexical fallback must be explicit.**
5. **Raw strings are allowed only as controlled fallback.**
6. **The contract must be renderer-agnostic.**
7. **Lexical resolution must scale across constructions, not just biography.**
8. **Renderers must not silently replace lexical identity chosen upstream.**

---

## 6. Canonical terminology

### `construction_plan`

A planned sentence-level object chosen by the planner and handed to lexical resolution.

### `slot_map`

A normalized mapping of semantic roles to slot values for one planned sentence.

### `entity_ref`

A normalized entity reference suitable for realization.

### `lexeme_ref`

A normalized lexical reference suitable for realization.

### `lexical_bindings`

A per-slot lexical-resolution record attached to `construction_plan` for renderer use and debug tracing.

### `resolution_result`

A structured lexical resolution output for one slot.

### `lang_code`

A normalized language code used for resolution and realization.

### `generation_options`

A renderer-safe options object that may influence lexical choice policy but does not change sentence semantics.

### `debug_info`

Structured metadata attached to runtime outputs.

---

## 7. Contract boundary

### 7.1 Canonical input

The canonical lexical-resolution input is:

```python
ConstructionPlan(
    construction_id: str,
    lang_code: str,
    slot_map: SlotMap,
    generation_options: dict[str, Any],
    topic_entity_id: str | None = None,
    focus_role: str | None = None,
    lexical_bindings: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
)
```

Lexical resolution receives:

* `construction_plan`
* `construction_plan.lang_code`
* `construction_plan.construction_id`
* `construction_plan.slot_map`
* optional `construction_plan.generation_options`
* optional discourse context already present on the plan

The resolver may also consult:

* lexicon indices,
* entity lookup bridges,
* alias maps,
* QID / canonical ID maps,
* language inventory metadata,
* fallback policies.

### 7.2 Canonical output

Lexical resolution returns a **lexicalized `construction_plan`** with:

* the same `construction_id`,
* the same `lang_code`,
* the same semantic slot structure,
* resolved slot values where applicable,
* `lexical_bindings` populated per slot,
* fallback metadata preserved,
* provenance preserved.

The resolver may also expose per-slot `resolution_result` values internally or in debug metadata, but the canonical planner → renderer handoff remains `construction_plan`.

### 7.3 Boundary rule

The canonical runtime boundary is:

```text
planner -> construction_plan -> lexical resolution -> lexicalized construction_plan -> renderer
```

Not:

```text
planner -> renderer-private lexical lookup
```

---

## 8. Required data structures

## 8.1 `EntityRef`

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class EntityRef:
    entity_id: Optional[str]
    label: str
    lang_code: str
    source: str
    confidence: float
    qid: Optional[str] = None
    surface_key: Optional[str] = None
    entity_type: Optional[str] = None
    alias_used: Optional[str] = None
    features: Mapping[str, Any] = field(default_factory=dict)
```

### Required fields

* `entity_id`

  * stable internal ID when available
  * may be `None` for controlled fallback
* `label`

  * human-readable lexical label for downstream realization
* `lang_code`

  * language of the resolved label
* `source`

  * where the resolution came from
* `confidence`

  * normalized confidence score

### Optional fields

* `qid`

  * external semantic identity where available
* `surface_key`

  * planner-stable discourse identity when available
* `entity_type`

  * semantic class hint such as `person`, `place`, `organization`
* `alias_used`

  * alias or normalized form used during lookup
* `features`

  * lexical or agreement-relevant features

---

## 8.2 `LexemeRef`

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class LexemeRef:
    lemma: str
    lang_code: str
    pos: Optional[str]
    source: str
    confidence: float
    lexeme_id: Optional[str] = None
    qid: Optional[str] = None
    surface_hint: Optional[str] = None
    features: Mapping[str, Any] = field(default_factory=dict)
```

### Required fields

* `lemma`
* `lang_code`
* `source`
* `confidence`

### Recommended fields

* `pos`
* `lexeme_id`
* `qid`

### Optional fields

* `surface_hint`

  * preferred citation or orthographic form
* `features`

  * lexical features useful to renderers, for example:

    * gender
    * animacy
    * countability
    * adjective-vs-noun behavior
    * nationality behavior
    * classifier family
    * agreement hints

---

## 8.3 `ResolutionResult`

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class ResolutionResult:
    slot_name: str
    resolved_value: Any
    source: str
    confidence: float
    fallback_used: bool
    kind: str
    error: Optional[str] = None
    notes: Mapping[str, Any] = field(default_factory=dict)
```

### Required fields

* `slot_name`
* `resolved_value`
* `source`
* `confidence`
* `fallback_used`
* `kind`

### `kind` values

Typical values include:

* `entity_ref`
* `lexeme_ref`
* `literal`
* `unresolved`

---

## 8.4 `lexical_bindings`

`lexical_bindings` is the canonical per-slot lexical-resolution map attached to `construction_plan`.

Example:

```json
{
  "subject": {
    "kind": "entity_ref",
    "source": "entity_index",
    "confidence": 1.0,
    "fallback_used": false,
    "qid": "Q7186"
  },
  "profession": {
    "kind": "lexeme_ref",
    "source": "lexicon",
    "confidence": 0.95,
    "fallback_used": false,
    "qid": "Q169470"
  },
  "nationality": {
    "kind": "lexeme_ref",
    "source": "raw_string",
    "confidence": 0.25,
    "fallback_used": true
  }
}
```

Rules:

* keys must match slot names in `slot_map`,
* the map must be stable across backends,
* renderers must treat `lexical_bindings` as authoritative when present,
* fallback to raw slot content is allowed only when bindings are absent or incomplete and policy allows it.

---

## 9. Slot-level resolution rules

Lexical resolution is applied per slot, but may use construction-level context.

### 9.1 Entity-like slots

Examples:

* `subject`
* `object`
* `location`
* `organization`
* `person`
* `office_holder`

Preferred output:

* `EntityRef`

### 9.2 Predicate-like slots

Examples:

* `profession`
* `predicate_nominal`
* `predicate_adjective`
* `relation_label`
* `office_title`
* `event_label`

Preferred output:

* `LexemeRef`

### 9.3 Literal slots

Examples:

* date strings,
* numerals,
* quoted strings,
* identifiers intentionally preserved as literals.

Preferred output:

* a literal-preserving value or controlled scalar fallback,
* with `ResolutionResult.kind = "literal"`.

---

## 10. Construction sensitivity

Lexical resolution must be construction-aware.

The same semantic item may resolve differently depending on `construction_id`.

Examples:

* a nationality may need adjective behavior in one construction and noun behavior in another,
* a profession may need indefinite classification behavior in one construction and title behavior in another,
* a location may need locative features in one construction and citation form in another,
* a relation may need predicate-noun behavior in one construction and eventive behavior in another.

Therefore lexical resolution must use:

* `construction_plan.construction_id`
* `construction_plan.slot_map`
* `construction_plan.generation_options`
* relevant discourse hints when present

as part of lexical selection policy.

---

## 11. Source precedence

Unless a construction-specific override exists, resolution should follow this precedence:

1. explicit stable ID on the slot (`entity_id`, `lexeme_id`, `qid`)
2. explicit lexical payload already attached to the plan
3. language-specific lexicon entry
4. alias / normalization lookup
5. cross-language canonical mapping
6. controlled raw-string fallback
7. unresolved marker

This order must be deterministic.

---

## 12. Fallback policy

### 12.1 Allowed fallback

Allowed fallbacks include:

* label-only entity resolution,
* lemma-only lexical resolution,
* raw-string lexical fallback,
* unresolved-slot marking with safe renderer behavior.

### 12.2 Disallowed fallback

Not allowed:

* silent replacement with unrelated lexemes,
* hidden language fallback without metadata,
* backend-private lexical guessing invisible to runtime metadata,
* replacing semantic slot meaning with renderer templates.

### 12.3 Fallback visibility

Any fallback must be visible in:

* `lexical_bindings`,
* `ResolutionResult`,
* `debug_info`,
* testable runtime metadata.

---

## 13. Confidence model

Each resolution output must expose a normalized confidence score.

Suggested interpretation:

* `1.0` — exact canonical match
* `0.9` — exact language lexicon match
* `0.75` — alias or normalized match
* `0.5` — cross-language inferred match
* `0.25` — raw fallback
* `0.0` — unresolved

Confidence is diagnostic and policy-facing. It must not be used to silently suppress output.

---

## 14. Resolver interface

### 14.1 Canonical port

```python
from typing import Protocol


class LexicalResolverPort(Protocol):
    def resolve_slot(
        self,
        *,
        lang_code: str,
        construction_id: str,
        slot_name: str,
        slot_value: object,
        generation_options: dict | None = None,
    ) -> ResolutionResult:
        ...

    def resolve_plan(
        self,
        *,
        construction_plan: object,
    ) -> object:
        ...
```

### 14.2 Required semantics

#### `resolve_slot(...)`

Must:

* resolve one slot deterministically,
* return a `ResolutionResult`,
* never return a renderer-specific type.

#### `resolve_plan(...)`

Must:

* resolve all lexicalized slots for one `construction_plan`,
* preserve `construction_id`,
* preserve `lang_code`,
* preserve slot names,
* return a lexicalized `construction_plan`,
* populate `lexical_bindings`,
* include fallback markers where needed.

### 14.3 Compatibility note

Helper methods such as `resolve_slot_map(...)` may exist internally during migration, but the canonical shared runtime boundary is still:

```text
ConstructionPlan -> lexicalized ConstructionPlan
```

---

## 15. Renderer contract expectations

Renderers must consume lexical outputs through stable refs.

Renderers may assume:

* `EntityRef` and `LexemeRef` are already normalized,
* lexical provenance exists,
* fallback status is available,
* slot names are stable,
* `lexical_bindings` is authoritative when present.

Renderers must **not**:

* redo lexicon lookup unless explicitly configured as a visible fallback,
* silently replace lexical choices,
* reinterpret semantic slots into new meanings,
* change `construction_id`.

---

## 16. Debug metadata contract

Lexical resolution must contribute to `debug_info`.

Minimum shape:

```json
{
  "construction_id": "copula_equative_classification",
  "renderer_backend": "gf",
  "lexical_resolution": {
    "subject": {
      "kind": "entity_ref",
      "source": "entity_index",
      "confidence": 1.0,
      "fallback_used": false
    },
    "profession": {
      "kind": "lexeme_ref",
      "source": "lexicon_alias",
      "confidence": 0.75,
      "fallback_used": false
    },
    "nationality": {
      "kind": "lexeme_ref",
      "source": "raw_string",
      "confidence": 0.25,
      "fallback_used": true
    }
  }
}
```

Required per resolved slot:

* `kind`
* `source`
* `confidence`
* `fallback_used`

Optional:

* `entity_id`
* `lexeme_id`
* `qid`
* `alias_used`
* `surface_hint`
* `error`

---

## 17. Error handling

Lexical resolution must fail softly unless the construction explicitly requires a hard lexical dependency.

### 17.1 Soft failure

Allowed when:

* a raw fallback exists,
* a label-only fallback exists,
* the renderer can continue safely.

### 17.2 Hard failure

Allowed when:

* the construction cannot be realized without lexical identity,
* downstream rendering would be semantically wrong,
* runtime policy explicitly requires strict lexical support.

Hard failures must be explicit and structured.

---

## 18. Batch resolution

Resolvers may support batch lookup internally, but the external contract remains deterministic and slot-based.

If batch resolution is implemented, it must:

* preserve per-slot provenance,
* preserve per-slot confidence,
* preserve stable slot ordering in output mappings,
* still return a lexicalized `construction_plan`.

---

## 19. Caching

Caching is allowed.

Rules:

* cache keys must include `lang_code`,
* cache keys must include normalized lexical input or stable ID,
* cache must not hide fallback metadata,
* cache must not alter resolution determinism.

---

## 20. Language policy

Lexical resolution is language-aware, but must support partial coverage.

### 20.1 Full language support

Resolver returns:

* language-native lexical refs,
* relevant features,
* high confidence.

### 20.2 Partial language support

Resolver returns:

* language-normalized refs when possible,
* controlled cross-language fallback when allowed,
* visible fallback metadata.

### 20.3 Minimal language support

Resolver returns:

* raw-string fallback,
* clear fallback visibility.

---

## 21. Construction examples

### 21.1 Equative classification

Input slot:

* `profession = "mathematician"`

Possible output:

* `LexemeRef(lemma="mathematician", pos="NOUN", lang_code="en", ...)`

### 21.2 Locative construction

Input slot:

* `location = "Paris"`

Possible output:

* `EntityRef(label="Paris", qid="Q90", entity_id=None, lang_code="fr", ...)`

### 21.3 Biography lead

Input slots:

* `profession = "writer"`
* `nationality = "French"`

Possible output:

* `LexemeRef(...)` for profession
* `LexemeRef(...)` for nationality

No special bio-only runtime behavior is assumed in this contract.

---

## 22. Responsibilities by layer

### Planner

Owns:

* semantic packaging,
* construction choice,
* slot assignment,
* topic/focus metadata,
* default realization options.

### Lexical resolver

Owns:

* lexical identity,
* lexical provenance,
* controlled fallback,
* feature enrichment.

### Renderer

Owns:

* morphology,
* agreement,
* backend-specific assembly,
* local word order,
* final surface form.

---

## 23. Anti-patterns

The following are forbidden:

1. Router-level lexical guessing
2. Renderer-private hidden lexicon fallback
3. Construction modules returning backend-specific lexical objects
4. Bio-specific lexical contract at the architecture layer
5. Silent substitution across semantic categories
6. Raw strings treated as fully resolved lexical identity without metadata
7. Renderers changing lexical identity without explicit fallback recording

---

## 24. Testing requirements

The lexical resolution layer must have tests for:

* canonical ID match,
* alias match,
* language-native lemma match,
* cross-language fallback,
* raw-string fallback,
* unresolved slot behavior,
* per-slot provenance,
* confidence stability,
* construction-sensitive resolution differences,
* `lexical_bindings` population,
* renderer-visible fallback metadata.

---

## 25. Migration rule

During migration, any existing lexical logic embedded in:

* router code,
* `GenerateText`,
* GF wrapper,
* family renderers,
* safe-mode renderers

must be moved behind this contract or explicitly marked as temporary compatibility behavior.

No new lexical logic should be added outside the lexical-resolution boundary.

---

## 26. Definition of done

This contract is fully implemented when:

1. all migrated constructions resolve lexicalized slots through one shared contract,
2. all renderers consume the same lexical outputs,
3. fallback is explicit and testable,
4. lexical provenance appears in `debug_info`,
5. `lexical_bindings` is available to renderers,
6. lexical lookup logic is no longer duplicated across runtime layers.

---

## 27. Final rule

**The planner chooses meaning, the lexical resolver chooses lexical identity, and the renderer chooses surface form.**

