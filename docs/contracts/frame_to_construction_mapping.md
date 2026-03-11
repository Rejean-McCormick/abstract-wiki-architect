# Frame-to-Construction Mapping Contract

Status: authoritative
Owner: runtime architecture / discourse planning / generation
Last updated: 2026-03-10

---

## 1. Purpose

This document defines the **normative mapping** from semantic frames to planner-owned construction plans.

It is the contract between:

* frame normalization,
* construction selection,
* discourse planning,
* slot building,
* lexical resolution,
* renderer backends (`gf`, `family`, `safe_mode`).

This document exists to prevent drift between:

* frame schemas,
* planner logic,
* construction modules,
* lexical resolution,
* runtime renderers,
* tests.

---

## 2. Scope

This contract applies to all runtime generation paths that transform a normalized semantic frame into a planner-owned sentence plan and, from there, a renderer-facing construction plan.

It covers:

* canonical frame-family to construction mapping,
* canonical `construction_id` values,
* wrapper selection,
* slot-building responsibilities,
* fallback behavior,
* compatibility rules for unmigrated or partially supported frame types.

It does **not** define:

* exact morphology,
* lexicon lookup internals,
* language-specific wording,
* punctuation policy,
* GF AST internals,
* backend-specific template details.

Those belong to other contracts.

---

## 3. Architectural rule

The authoritative runtime flow is:

`frame -> normalized_frame -> construction selection -> slot building -> planned_sentence -> construction_plan -> lexical resolution -> renderer -> text`

### Hard rule

A backend **MUST NOT** invent its own construction choice from raw frame data when a planner-produced `construction_id` is present.

Backends may realize a plan.
They may not redefine the plan.

---

## 4. Canonical terms

### 4.1 Frame

A semantic object with a canonical `frame_type`, normalized entity / predicate / event fields, and optional metadata.

### 4.2 Construction

A language-agnostic sentence structure identified by a canonical snake_case `construction_id`.

### 4.3 Slot map

A construction-shaped payload containing only the semantic information required by that construction.

### 4.4 Planned sentence

A sentence-level planner object containing at least:

* `construction_id`
* `slot_map`
* `topic_entity_id`
* `focus_role`
* `generation_options`
* `metadata`

### 4.5 Construction plan

The renderer-facing runtime object derived from the planned sentence. It carries the same construction semantics plus renderer-ready fields such as `lang_code`.

---

## 5. Authoritative migrated construction inventory

This mapping contract is authoritative for the currently aligned construction inventory:

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_attributive_adj`
* `copula_attributive_np`
* `copula_existential`
* `copula_locative`
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

The following are **not** authoritative migrated construction IDs in this contract version and therefore MUST NOT be used as default mapping targets:

* `apposition_np`
* `comparative_superlative`
* `causative_event`

If equivalent semantics are needed before those constructions are migrated, the planner MUST use a supported construction plus explicit fallback metadata.

---

## 6. Mapping precedence

Construction selection follows this precedence, highest first.

### 6.1 Explicit override

Use `frame.meta.construction_id` if present and valid.

This is allowed only for:

* migration,
* diagnostics,
* human-in-the-loop correction,
* specialized authoring.

### 6.2 Canonical direct mapping

If the canonical `frame_type` has an explicit mapping in this document, use it.

### 6.3 Family default mapping

If there is no direct mapping, map by frame-family default.

### 6.4 Wrapper mapping

If discourse packaging is required, wrap the base construction in:

* `topic_comment_copular`, or
* `topic_comment_eventive`

### 6.5 Safety fallback

If nothing else applies:

* relation-like frames fall back to `copula_equative_simple`
* event-like frames fall back to `intransitive_event`
* aggregate / meta frames fall back to `topic_comment_eventive`

A fallback **MUST** be recorded in:

* `metadata.fallback_used = true`
* `metadata.fallback_reason`
* `metadata.original_frame_type`

---

## 7. Canonical slot model

### 7.1 Rule

`slot_map` is semantic and construction-shaped. It is **not** a place for backend-specific payloads.

### 7.2 Shared semantic slot names

Unless a construction documents a narrower shape, shared slot names SHOULD come from this inventory:

* `subject`
* `predicate`
* `object`
* `agent`
* `patient`
* `recipient`
* `theme`
* `location`
* `source`
* `target`
* `time`
* `manner`
* `quantity`
* `topic`
* `comment`
* `event`
* `profession`
* `nationality`
* `extras`

### 7.3 Realization controls are not slot keys

Realization controls such as these do **not** belong as top-level semantic slots:

* `tense`
* `aspect`
* `polarity`
* `register`
* `voice`
* `style`

They belong in `generation_options`.

### 7.4 Shared value shape guidance

Before lexical resolution, slot values MAY be raw or lightly normalized. After lexical resolution, they SHOULD converge toward stable `EntityRef` / `LexemeRef`-like objects.

Example entity-like slot value:

```json
{
  "entity_id": "Q7251",
  "label": "Alan Turing",
  "qid": "Q7251",
  "features": {
    "entity_type": "person"
  }
}
```

Example predicate-like slot value:

```json
{
  "lemma": "mathematician",
  "pos": "NOUN",
  "source": "raw",
  "confidence": 0.0,
  "features": {}
}
```

### 7.5 Hard naming rules

Use canonical slot names such as:

* `subject`
* `predicate`
* `object`
* `location`
* `time`
* `topic`
* `event`

Do **not** create parallel ad hoc keys such as:

* `main_entity`
* `thing`
* `entityA`
* `entityB`
* `prof`
* `nat`
* `obj1`
* `obj2`

Compatibility shims may read legacy names, but planner output MUST normalize them.

---

## 8. Canonical family defaults

| Frame family | Default construction             | Notes                                    |
| ------------ | -------------------------------- | ---------------------------------------- |
| `entity`     | `copula_equative_classification` | entity intro / identity / type           |
| `relation`   | `copula_equative_simple`         | overridden by specific relation subtypes |
| `event`      | `intransitive_event`             | overridden by valency when known         |
| `aggregate`  | `topic_comment_eventive`         | summary / sequence / list wrapper        |
| `meta`       | `topic_comment_copular`          | document / section / source statements   |

---

## 9. Canonical frame-to-construction mapping

This section is authoritative.

### 9.1 Entity family

| Canonical frame type                                         | Construction                     | Notes                                    |
| ------------------------------------------------------------ | -------------------------------- | ---------------------------------------- |
| `bio`                                                        | `copula_equative_classification` | person identity lead                     |
| `entity.organization`                                        | `copula_equative_classification` | organization type                        |
| `entity.gpe`                                                 | `copula_equative_classification` | geopolitical type                        |
| `entity.place`                                               | `copula_equative_classification` | place class                              |
| `entity.facility`                                            | `copula_equative_classification` | facility class                           |
| `entity.astronomical`                                        | `copula_equative_classification` | astronomical object type                 |
| `entity.species`                                             | `copula_equative_classification` | species classification                   |
| `entity.chemical_or_material`                                | `copula_equative_classification` | material type                            |
| `entity.artifact`                                            | `copula_equative_classification` | artifact class                           |
| `entity.vehicle`                                             | `copula_equative_classification` | vehicle class                            |
| `entity.creative_work`                                       | `copula_equative_classification` | work type                                |
| `entity.language`                                            | `copula_equative_classification` | language type                            |
| any entity frame with locative predicate as main assertion   | `copula_locative`                | only when location is the main predicate |
| any entity frame with adjectival predicate as main assertion | `copula_attributive_adj`         | e.g. “X is famous”                       |
| any entity frame with nominal attribute as main assertion    | `copula_attributive_np`          | e.g. “X is a legend”                     |

### 9.2 Relation family

| Canonical frame type       | Construction                                        | Notes                                            |
| -------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| `relation.definition`      | `copula_equative_classification`                    | class / type membership                          |
| `relation.attribute`       | `copula_attributive_adj` or `copula_attributive_np` | chosen by normalized predicate kind              |
| `relation.quantitative`    | `copula_attributive_np`                             | quantity as predicate nominal / measure phrase   |
| `relation.membership`      | `copula_equative_simple`                            | affiliation / membership                         |
| `relation.role`            | `copula_equative_simple`                            | role / position / office                         |
| `relation.part_whole`      | `possession_have` or `possession_existential`       | chosen by language / family policy               |
| `relation.ownership`       | `possession_have` or `possession_existential`       | chosen by language / family policy               |
| `relation.spatial`         | `copula_locative`                                   | in / at / on / near relation                     |
| `relation.temporal`        | `copula_attributive_np`                             | time-as-predicate relation                       |
| `relation.causal`          | `transitive_event`                                  | cause / influence predicate expressed eventively |
| `relation.change_of_state` | `intransitive_event` or `transitive_event`          | depends on agentivity                            |
| `relation.communication`   | `transitive_event`                                  | say / state / announce                           |
| `relation.opinion`         | `transitive_event`                                  | evaluate / consider                              |
| `relation.bundle`          | `coordination_clauses`                              | multi-fact bundle                                |

### 9.3 Event family

| Canonical frame type               | Construction         | Notes                                                   |
| ---------------------------------- | -------------------- | ------------------------------------------------------- |
| event with no object               | `intransitive_event` | default event case                                      |
| event with one object / patient    | `transitive_event`   | standard transitive event                               |
| event with recipient / beneficiary | `ditransitive_event` | give / send / award style                               |
| event with passive discourse focus | `passive_event`      | only when planner explicitly requests passive packaging |

#### Event subtype convention

These event subtypes map by valency and discourse packaging, not by domain label alone:

* `event.conflict`
* `event.cultural`
* `event.disaster`
* `event.economic`
* `event.election`
* `event.exploration`
* `event.generic`
* `event.historical`
* `event.life`

### 9.4 Aggregate family

| Canonical frame type       | Construction             | Notes                                                                                              |
| -------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------- |
| `aggregate.timeline`       | `topic_comment_eventive` | ordered event sequence                                                                             |
| `aggregate.career_summary` | `topic_comment_eventive` | biography summary wrapper                                                                          |
| `aggregate.development`    | `topic_comment_eventive` | evolution / development                                                                            |
| `aggregate.reception`      | `topic_comment_eventive` | reactions / impact                                                                                 |
| `aggregate.structure`      | `coordination_clauses`   | component listing                                                                                  |
| `aggregate.list`           | `coordination_clauses`   | enumeration                                                                                        |
| `aggregate.comparison_set` | `coordination_clauses`   | comparison expressed as coordinated contrast until a dedicated comparison construction is migrated |

### 9.5 Meta family

| Canonical frame type | Construction            | Notes                          |
| -------------------- | ----------------------- | ------------------------------ |
| `article`            | `topic_comment_copular` | article / document description |
| `section`            | `topic_comment_copular` | section summary                |
| `source`             | `topic_comment_copular` | source / citation packaging    |

---

## 10. Wrapper rules

Wrappers are not free-form alternatives. They package a base construction.

### 10.1 `topic_comment_copular`

Use when:

* a stable discourse topic is known,
* the comment is copular / classificatory / attributive,
* the language family benefits from explicit topic packaging,
* article / section / meta generation needs topical framing.

Wraps:

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_attributive_adj`
* `copula_attributive_np`
* `copula_locative`
* `copula_existential`
* `possession_have`
* `possession_existential`

### 10.2 `topic_comment_eventive`

Use when:

* a stable discourse topic is known,
* the comment is eventive or summary-like,
* multiple related facts are grouped under a topic.

Wraps:

* `intransitive_event`
* `transitive_event`
* `ditransitive_event`
* `passive_event`
* `coordination_clauses`

### 10.3 Wrapper metadata

If a wrapper is used, planner metadata MUST contain:

```json
{
  "wrapper_construction_id": "topic_comment_copular",
  "base_construction_id": "copula_equative_simple"
}
```

`construction_id` MUST remain the outer wrapper construction.

---

## 11. Slot-building contract

Each mapping in this document implies a slot-building path.

A slot builder:

1. accepts a normalized frame,
2. returns a valid `slot_map` for exactly one construction,
3. does not perform language-specific linearization,
4. may request lexical resolution later through the runtime pipeline,
5. may attach planner metadata.

### 11.1 Required slot-builder signature

```python
def build_slots(
    frame: dict,
    *,
    lang_code: str,
    topic_entity_id: str | None = None,
    focus_role: str | None = None,
) -> dict:
    ...
```

### 11.2 Required guarantees

A slot builder MUST:

* return a JSON-serializable dict,
* use canonical slot names,
* normalize missing optional fields to omission or `null`,
* never emit renderer-specific payloads such as GF AST fragments,
* never emit already-linearized sentence text.

### 11.3 Planner surface rule

`slot_builder_id` MAY exist as planner / registry metadata for diagnostics and traceability, but it is **not** a required top-level field of the shared renderer-facing `construction_plan`.

If exposed, it SHOULD live under planner metadata, for example:

```json
{
  "metadata": {
    "slot_builder_id": "build_entity_classification_slots"
  }
}
```

---

## 12. Bio compatibility rule

`bio` remains a valid canonical entrypoint for person-style generation.

However:

* `bio` is a frame type, not a privileged runtime architecture,
* `bio` maps into the same construction runtime as every other frame family,
* bio-specific first-sentence behavior is implemented through planner packaging and metadata, not through a parallel runtime.

For biography leads:

* default base construction: `copula_equative_classification`
* optional wrapper: `topic_comment_copular`
* follow-up event facts: eventive constructions selected by valency and focus

---

## 13. Relative-clause attachment rule

If a frame is not meant to become a root sentence but rather a modifier of another noun phrase, the planner may select:

* `relative_clause_subject_gap`
* `relative_clause_object_gap`

This MUST be expressed explicitly in `construction_id`.

It must not be inferred ad hoc by the renderer.

### 13.1 Appositional compatibility note

Appositional packaging is not an authoritative migrated construction in this contract version.

If appositional behavior is needed before a dedicated construction is migrated, the planner MUST either:

* realize the content as a root sentence through a supported construction, or
* use an explicit fallback strategy recorded in metadata.

---

## 14. Fallback rules

### 14.1 Relation fallback

Unknown relation-like frames:

* `construction_id = "copula_equative_simple"`

### 14.2 Event fallback

Unknown event-like frames:

* `construction_id = "intransitive_event"`

### 14.3 Aggregate / meta fallback

Unknown aggregate or meta frames:

* `construction_id = "topic_comment_eventive"`

### 14.4 Last-resort fallback

If a frame cannot be mapped safely:

* planner MUST emit `construction_id = "copula_equative_simple"`
* metadata MUST include:

  * `fallback_used = true`
  * `fallback_reason`
  * `original_frame_type`

---

## 15. Validation rules

### 15.1 Planner validation

The planner MUST validate that every mapped sentence plan has:

* a non-empty `construction_id`,
* a canonical `frame_type`,
* a valid `slot_map`,
* either direct or fallback mapping justification.

### 15.2 Registry validation

The construction registry MUST validate that every `construction_id` named in this document exists in the runtime registry.

If planner metadata exposes `slot_builder_id`, the registry MUST also validate that the named builder exists for the chosen construction.

### 15.3 Test validation

There MUST be tests for:

* frame family to construction selection,
* wrapper selection,
* fallback behavior,
* slot-shape validation,
* unmigrated-frame compatibility.

---

## 16. Migration policy

### 16.1 During migration

Legacy direct frame-to-engine generation may remain as a compatibility path.

### 16.2 Final-state rule

Final runtime behavior MUST treat this mapping contract as authoritative.

That means:

* routers do not choose constructions,
* renderers do not guess constructions from raw frames,
* GF adapters do not own sentence planning,
* family engines do not bypass slot-map normalization.

---

## 17. Examples

### 17.1 Biography lead

Input frame:

```json
{
  "frame_type": "bio",
  "subject": { "id": "Q7251", "name": "Alan Turing" },
  "profession": "mathematician",
  "nationality": "British"
}
```

Mapped planned sentence:

```json
{
  "construction_id": "copula_equative_classification",
  "topic_entity_id": "Q7251",
  "focus_role": "predicate",
  "generation_options": {
    "tense": "present",
    "register": "neutral"
  },
  "metadata": {
    "sentence_kind": "definition",
    "slot_builder_id": "build_entity_classification_slots"
  }
}
```

### 17.2 Spatial relation

Input frame:

```json
{
  "frame_type": "relation.spatial",
  "subject": { "name": "The laboratory" },
  "location": { "name": "Paris" }
}
```

Mapped planned sentence:

```json
{
  "construction_id": "copula_locative",
  "generation_options": {
    "tense": "present"
  },
  "metadata": {
    "sentence_kind": "spatial_relation",
    "slot_builder_id": "build_spatial_slots"
  }
}
```

### 17.3 Eventive statement

Input frame:

```json
{
  "frame_type": "event.generic",
  "subject": { "name": "Marie Curie" },
  "verb_lemma": "discover",
  "object": { "name": "polonium" }
}
```

Mapped planned sentence:

```json
{
  "construction_id": "transitive_event",
  "generation_options": {
    "tense": "past"
  },
  "metadata": {
    "sentence_kind": "event",
    "slot_builder_id": "build_event_slots"
  }
}
```

### 17.4 Ownership fallback by language policy

Input frame:

```json
{
  "frame_type": "relation.ownership",
  "subject": { "name": "The museum" },
  "object": { "name": "a collection" }
}
```

Mapped planned sentence:

```json
{
  "construction_id": "possession_have",
  "metadata": {
    "sentence_kind": "ownership",
    "selection_policy": "family_default",
    "slot_builder_id": "build_ownership_slots"
  }
}
```

---

## 18. Non-goals

This document does not decide:

* tense policy per article genre,
* article insertion policy,
* pronoun selection,
* passive-vs-active discourse strategy,
* lexical choice among synonyms,
* punctuation templates,
* GF-specific function naming.

Those belong to:

* planner heuristics,
* lexical resolution,
* language profiles,
* renderer contracts.

---

## 19. Change control

Any new frame type or construction must update:

1. this file,
2. the construction registry,
3. the relevant slot-building path,
4. planner tests,
5. runtime tests.

A PR that changes runtime construction behavior without updating this mapping is incomplete.

---

## 20. Short version

If you only remember one rule:

> Frames do not render directly.
> Frames map to constructions.
> Constructions consume slot maps.
> Renderers realize plans.
