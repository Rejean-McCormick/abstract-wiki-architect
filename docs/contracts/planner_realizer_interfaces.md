# Planner / Realizer Interfaces Contract

Status: normative
Owner: SKA runtime maintainers
Scope: canonical runtime interfaces between semantic planning and surface realization
Applies to: API generation path, discourse planner, construction modules, family engines, GF adapter, safe-mode renderer

---

## 1. Purpose

This document defines the canonical interfaces between:

* semantic/frame normalization,
* discourse and sentence planning,
* construction selection,
* construction-plan building,
* lexical resolution,
* realization backends.

It establishes a single runtime contract so that:

1. planning is the authoritative source of sentence intent,
2. all renderers consume the same `ConstructionPlan`,
3. GF is one backend rather than the runtime contract itself,
4. family engines and safe-mode remain first-class backends,
5. direct `frame -> engine` generation becomes a compatibility layer only.

---

## 2. Architectural position

The repository already distinguishes:

* semantics / frames,
* discourse planning,
* constructions,
* family-level morphology engines,
* lexicon resolution.

This interface contract preserves that architecture and defines the missing runtime boundary between planner output and renderer input.

Canonical target flow:

```text
request payload
  -> frame normalization
  -> discourse planning
  -> construction-plan building
  -> lexical resolution
  -> realization backend
  -> surface result
```

The planner decides **what sentence is to be said**.
The realizer decides **how the target language says it**.

---

## 3. Non-goals

This contract does **not** define:

* the external HTTP payload schema in full,
* individual construction semantics,
* GF abstract/concrete grammar details,
* family-specific morphology algorithms,
* lexicon storage implementation.

Those are specified in separate documents.

---

## 4. Design principles

1. **Planner-first**

   * No renderer may invent sentence structure that the planner did not authorize.

2. **Renderer-agnostic planning**

   * Planner output must be valid for GF, family engines, and safe-mode.

3. **Construction-centered runtime**

   * The runtime contract is expressed in terms of constructions and slots, not renderer-specific ASTs.

4. **Typed lexical boundary**

   * Raw strings may enter the system, but renderer input must use normalized `EntityRef` / `LexemeRef` values where possible.

5. **Stable debug surface**

   * All backends must emit a common debug shape.

6. **Graceful fallback**

   * Failure to realize in one backend may fall through to another backend only through explicit policy.

7. **Backward compatibility**

   * Existing API callers may continue to send current frame payloads while the runtime migrates internally.

---

## 5. Canonical terminology

### 5.1 Core runtime objects

* **Frame**
  Semantic/domain input object.

* **PlannedSentence**
  Sentence-level planning object carrying discourse and construction metadata.

* **ConstructionPlan**
  Canonical runtime handoff from planner-side logic to the renderer.

* **SlotMap**
  Normalized semantic slots required by a construction.

* **EntityRef**
  Normalized entity reference for a discourse participant or topic.

* **LexemeRef**
  Normalized lexical reference for a predicate, role word, adjective, noun, or modifier.

* **SurfaceResult**
  Final surface result returned by the runtime.

### 5.2 Canonical field names

These names are mandatory across planner and realizer code:

* `lang_code`
* `construction_id`
* `slot_map`
* `topic_entity_id`
* `focus_role`
* `metadata`
* `renderer_backend`
* `debug_info`
* `text`
* `fallback_used`

Use these preferred runtime variable names where applicable:

* `planned_sentence`
* `construction_plan`
* `surface_result`

Do not introduce alternate top-level names such as:

* `lang`, `language`, `resolved_lang`
* `construction`, `template_id`, `pattern_id`
* `slots`, `args`, `payload_slots`
* `backend_name`, `engine_name`
* `surface_text`

Use the canonical names above.

---

## 6. Runtime object contracts

## 6.1 EntityRef

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class EntityRef:
    entity_id: Optional[str]
    label: str
    entity_type: Optional[str] = None
    qid: Optional[str] = None
    gender: Optional[str] = None
    number: Optional[str] = None
    person: Optional[str] = None
    animacy: Optional[str] = None
    features: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### Semantics

* `entity_id` is the internal stable ID when available.
* `label` is the preferred canonical display label.
* `entity_type` is an optional semantic type such as `person`, `place`, or `organization`.
* `qid` is optional external identity.
* discourse-relevant and morphology-relevant features may be attached.

### Invariants

* `label` is required.
* `entity_id` is optional but strongly recommended when available.
* renderer backends must not mutate `EntityRef`.

---

## 6.2 LexemeRef

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class LexemeRef:
    lexeme_id: Optional[str]
    lemma: str
    pos: Optional[str] = None
    qid: Optional[str] = None
    lang_code: Optional[str] = None
    features: Mapping[str, Any] = field(default_factory=dict)
    source: str = "raw"
    confidence: float = 0.0
```

### Semantics

* `lemma` is the canonical lexical content seen by the realizer.
* `pos` is optional but recommended.
* `features` may include gender, countability, definiteness constraints, adjective position class, or inflection hints.
* `source` identifies provenance: `raw`, `lexicon`, `wikidata`, `resolved`, etc.

### Invariants

* `lemma` is required.
* `confidence` is a float in `[0.0, 1.0]`.
* unresolved raw input is allowed only when fallback policy permits it.

---

## 6.3 SlotMap

```python
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SlotMap:
    values: Mapping[str, Any] = field(default_factory=dict)
```

### Semantics

`SlotMap.values` is the normalized mapping from construction slot name to typed value.

Allowed slot value types:

* `EntityRef`
* `LexemeRef`
* plain scalar literals (`str`, `int`, `float`, `bool`)
* tuples / sequences only where the construction explicitly allows them

### Invariants

* slot names must be stable lower_snake_case strings.
* slot semantics are defined by the target construction, not by the backend.
* renderers must reject unknown required/forbidden slot combinations.

---

## 6.4 ConstructionPlan

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class ConstructionPlan:
    construction_id: str
    lang_code: str
    slot_map: SlotMap
    topic_entity_id: Optional[str] = None
    focus_role: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### Semantics

This is the canonical planner/build-step -> realizer contract.

### Required fields

* `construction_id`
* `lang_code`
* `slot_map`

### Optional fields

* `topic_entity_id`
* `focus_role`
* `metadata`

### Metadata rules

`metadata` may carry:

* sentence-kind hints,
* discourse notes,
* provenance,
* planner diagnostics,
* renderer-safe generation options.

Renderer-safe generation options must live under:

```python
metadata["generation_options"]
```

Typical keys there include:

* `tense`
* `aspect`
* `polarity`
* `register`
* `definiteness`
* `voice`
* `style`
* `allow_fallback`
* `force_backend`
* `debug`

### Invariants

* `construction_id` is globally stable and backend-independent.
* `lang_code` is normalized before realization.
* `metadata` may refine realization behavior but may not silently change construction semantics.
* all semantic content required for realization must already be present in `slot_map`.

---

## 6.5 PlannedSentence

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class PlannedSentence:
    frame: Any
    construction_id: str
    topic_entity_id: Optional[str] = None
    focus_role: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

### Semantics

`PlannedSentence` is discourse-planning output.
It may still carry source-frame context, but it is not renderer-ready until converted into a `ConstructionPlan`.

### Rule

`PlannedSentence` is planner-facing.
`ConstructionPlan` is renderer-facing.

---

## 6.6 SurfaceResult

```python
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SurfaceResult:
    text: str
    lang_code: str
    construction_id: str
    renderer_backend: str
    debug_info: Mapping[str, Any] = field(default_factory=dict)
```

### Semantics

This is the final surface output returned to callers.

### Required debug keys

All renderers must include:

* `construction_id`
* `renderer_backend`
* `lang_code`
* `fallback_used`

Optional keys may include:

* `resolved_language`
* `ast`
* `slot_map`
* `lexical_resolution`
* `timings_ms`
* `warnings`

### Compatibility note

A legacy internal `Sentence` type may remain temporarily as an alias or wrapper during migration, but the canonical contract name is `SurfaceResult`.

---

## 7. Planner interface

```python
from __future__ import annotations
from typing import Protocol, Sequence


class PlannerPort(Protocol):
    def plan(
        self,
        frames: Sequence[object],
        *,
        lang_code: str,
        domain: str = "auto",
    ) -> list[PlannedSentence]:
        """
        Produce sentence-level discourse plans from semantic frames.
        """
        ...
```

### Responsibilities

The planner must:

* preserve or intentionally reorder semantic content,
* choose `construction_id`,
* set `topic_entity_id`,
* set `focus_role`,
* attach sentence-level metadata.

The planner must **not**:

* choose renderer backends,
* build GF ASTs,
* inflect morphology directly,
* generate final strings.

---

## 8. Construction-plan builder interface

```python
from __future__ import annotations
from typing import Protocol


class ConstructionPlanBuilder(Protocol):
    def build_plan(
        self,
        planned_sentence: PlannedSentence,
        *,
        lang_code: str,
    ) -> ConstructionPlan:
        """
        Convert a PlannedSentence into a renderer-ready ConstructionPlan.
        """
        ...
```

### Responsibilities

The construction-plan builder must:

* map sentence-level intent into a stable slot contract,
* normalize slot values into `EntityRef` / `LexemeRef` / literals,
* attach realization-relevant metadata,
* validate construction completeness.

This is the authoritative bridge between planning and realization.

---

## 9. Lexical resolver interface

```python
from __future__ import annotations
from typing import Protocol


class LexicalResolverPort(Protocol):
    def resolve_slot_map(
        self,
        slot_map: SlotMap,
        *,
        lang_code: str,
    ) -> SlotMap:
        """
        Resolve slot values into stable EntityRef / LexemeRef forms where possible.
        """
        ...
```

Optional helper methods may also be provided:

```python
from __future__ import annotations
from typing import Protocol


class LexicalResolverHelpers(Protocol):
    def resolve_entity(
        self,
        value: object,
        *,
        lang_code: str,
    ) -> EntityRef:
        ...

    def resolve_lexeme(
        self,
        value: object,
        *,
        lang_code: str,
        pos: str | None = None,
    ) -> LexemeRef:
        ...
```

### Responsibilities

The lexical resolver must:

* normalize raw input into stable typed refs,
* prefer existing lexicon IDs / known lemmas when available,
* annotate provenance and confidence,
* provide controlled raw fallback where resolution is incomplete.

### Rule

No renderer should have to guess whether a raw input is an entity, profession, adjective, or event label. That classification belongs in lexical resolution and construction-plan building.

---

## 10. Realizer interface

```python
from __future__ import annotations
from typing import Protocol


class RealizerPort(Protocol):
    async def realize(
        self,
        construction_plan: ConstructionPlan,
    ) -> SurfaceResult:
        """
        Produce a surface result from a ConstructionPlan.
        """
        ...
```

### Responsibilities

The realizer must:

* consume only `ConstructionPlan`,
* select language/family-specific realization logic,
* return a `SurfaceResult`,
* populate standard `debug_info`,
* never mutate the input plan.

### Rule

A realizer may fail because the plan is unsupported, incomplete, or unlexicalized.
It may not silently reinterpret the construction into a different one.

---

## 11. Backend adapter contracts

Each backend adapter must implement the same public runtime surface:

```python
async def realize(construction_plan: ConstructionPlan) -> SurfaceResult
```

### 11.1 GF adapter

Additional responsibilities:

* map `construction_id` and `slot_map` to backend-specific ASTs,
* report backend concrete selection in `debug_info["resolved_language"]`,
* report AST when available in `debug_info["ast"]`.

### Constraint

GF is a backend.
GF-specific data may appear in debug output but may not be required by the planner contract.

### 11.2 Family-engine adapter

Additional responsibilities:

* use family config + language card data,
* apply morphology through the registered family engine,
* remain construction-driven rather than frame-driven.

### Constraint

Family backends must not expose `render_bio(...)`-style interfaces as their public runtime surface.
The public runtime surface is `realize(construction_plan)`.

### 11.3 Safe-mode adapter

Additional responsibilities:

* produce deterministic fallback output,
* remain contract-faithful even when realization depth is low.

### Constraint

Safe-mode output must still honor `construction_id` and the shared slot contract.

---

## 12. Runtime orchestrator interface

```python
from __future__ import annotations
from typing import Protocol, Sequence


class TextRuntimePort(Protocol):
    async def generate(
        self,
        frames: Sequence[object],
        *,
        lang_code: str,
        domain: str = "auto",
    ) -> list[SurfaceResult]:
        """
        End-to-end generation:
        frames -> planner -> construction plans -> realization -> surface results
        """
        ...
```

### Responsibilities

The runtime orchestrator must:

1. normalize / validate frames,
2. invoke the planner,
3. build construction plans,
4. resolve lexical items,
5. select realization backend(s),
6. return final surface results.

This is the preferred successor to direct `GenerateText -> engine.generate(frame)` for construction-based generation.

---

## 13. Backend selection policy

Canonical backend preference order:

1. GF backend, when the language/construction pair is supported and healthy
2. family backend, when family realization is available
3. safe-mode backend, when deterministic fallback is allowed

### Rules

* backend selection must be explicit and observable,
* fallback must be recorded in `debug_info["fallback_used"]`,
* failure in one backend does not authorize semantic drift,
* unsupported construction/backend combinations must fail clearly.

---

## 14. Error contract

### 14.1 Planner errors

Use when:

* frames are invalid,
* construction cannot be assigned,
* discourse planning fails.

Suggested type:

* `PlanningError`

### 14.2 Construction-plan errors

Use when:

* required slots are missing,
* slot values are of the wrong type,
* construction constraints are violated.

Suggested type:

* `ConstructionPlanError`

### 14.3 Lexical resolution errors

Use when:

* required lexeme/entity normalization fails without permitted fallback.

Suggested type:

* `LexicalResolutionError`

### 14.4 Realization errors

Use when:

* backend cannot realize the plan,
* backend is unavailable,
* generated AST or morphology realization fails.

Suggested type:

* `RealizationError`

### 14.5 Runtime policy

* Prefer explicit typed errors internally.
* API layer may translate them into clean domain/API errors.
* Never silently switch constructions to recover from an error.

---

## 15. Debug-info contract

Every `SurfaceResult.debug_info` must support the following keys:

```json
{
  "construction_id": "string",
  "renderer_backend": "gf|family|safe_mode",
  "lang_code": "string",
  "fallback_used": false
}
```

Recommended optional keys:

```json
{
  "topic_entity_id": "optional string",
  "focus_role": "optional string",
  "resolved_language": "optional concrete language key",
  "ast": "optional backend expression",
  "slot_map": "optional normalized slot dump",
  "lexical_resolution": "optional lexical resolver summary",
  "timings_ms": {
    "planning": 0.0,
    "resolution": 0.0,
    "realization": 0.0
  },
  "warnings": []
}
```

### Invariants

* `renderer_backend` must always be present.
* `construction_id` in debug info must equal the realized plan’s `construction_id`.
* `fallback_used` must be truthful.

---

## 16. Compatibility layer

During migration, the existing direct runtime path may remain as a compatibility adapter.

Allowed transitional shape:

```text
legacy frame
  -> compatibility mapper
  -> ConstructionPlan
  -> canonical realizer
```

Not allowed:

```text
legacy frame
  -> ad hoc renderer-specific logic
  -> final text
```

The compatibility layer must be temporary and isolated.

---

## 17. Example end-to-end flow

### Input frames

```python
frames = [bio_frame]
```

### Planner output

```python
[
    PlannedSentence(
        frame=bio_frame,
        construction_id="copula_equative_classification",
        topic_entity_id="Q7251",
        focus_role="predicate_nominal",
        metadata={"sentence_kind": "biographical_definition"},
    )
]
```

### Construction plan

```python
ConstructionPlan(
    construction_id="copula_equative_classification",
    lang_code="fr",
    slot_map=SlotMap(
        values={
            "subject": EntityRef(
                entity_id="Q7251",
                label="Alan Turing",
                qid="Q7251",
                gender="m",
                entity_type="person",
            ),
            "predicate_nominal": LexemeRef(
                lexeme_id=None,
                lemma="mathématicien",
                pos="NOUN",
                source="lexicon",
                confidence=0.92,
            ),
            "nationality": LexemeRef(
                lexeme_id=None,
                lemma="britannique",
                pos="ADJ",
                source="lexicon",
                confidence=0.95,
            ),
        }
    ),
    topic_entity_id="Q7251",
    focus_role="predicate_nominal",
    metadata={
        "sentence_kind": "biographical_definition",
        "generation_options": {
            "register": "neutral",
            "polarity": "positive",
        },
    },
)
```

### Surface result

```python
SurfaceResult(
    text="Alan Turing est un mathématicien britannique.",
    lang_code="fr",
    construction_id="copula_equative_classification",
    renderer_backend="gf",
    debug_info={
        "construction_id": "copula_equative_classification",
        "renderer_backend": "gf",
        "lang_code": "fr",
        "fallback_used": False,
        "resolved_language": "WikiFre",
    },
)
```

---

## 18. Required migration rule

Every existing and future construction must follow this chain:

```text
frame -> PlannedSentence -> ConstructionPlan -> SurfaceResult
```

Not:

```text
frame -> renderer-specific generation
```

This is the rule that prevents drift between planner logic, construction logic, and backend logic.

---

## 19. Open extension points

The following may evolve without breaking this contract:

* richer `LexemeRef.features`
* richer `EntityRef.metadata`
* multi-sentence planning metadata
* backend-specific timing detail
* richer fallback policy controls
* parser-facing interfaces in the future

The following are **contract-stable** and may not drift casually:

* `construction_id`
* `slot_map`
* `lang_code`
* `renderer_backend`
* `text`
* `debug_info` minimum keys
* planner vs realizer responsibility boundary

---

## 20. Acceptance criteria

This contract is considered adopted when:

1. new runtime generation code consumes `ConstructionPlan`,
2. planner output is converted into renderer-ready plans explicitly,
3. GF and family backends both implement `realize(construction_plan)`,
4. debug output is standardized,
5. at least one migrated construction runs end-to-end through the canonical path,
6. direct frame-driven rendering is demoted to compatibility-only status.

---

## 21. Summary

This contract makes planning authoritative and realization replaceable.

It keeps SKA’s existing architecture intact while fixing the missing runtime boundary between:

* semantic intent,
* sentence planning,
* lexical normalization,
* multilingual realization.

The result is one stable runtime contract across:

* planner,
* construction-plan building,
* construction modules,
* GF backend,
* family-engine backends,
* safe-mode fallback.

