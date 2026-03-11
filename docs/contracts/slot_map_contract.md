# Slot Map Contract

Status: normative
Owner: runtime / planning / construction layer
Last updated: 2026-03-10
Applies to: construction-plan building, lexical resolution, renderer backends, morphology adapters

---

## 1. Purpose

This document defines the **Slot Map Contract** used inside the aligned construction runtime.

It is the contract between:

* planning / construction selection,
* frame-to-slot mapping,
* lexical resolution,
* renderer backends,
* morphology adapters.

The goal is to make slot-based realization **explicit, typed, stable, and reusable** across constructions and languages.

This contract is **generic**. It is not biography-specific.

---

## 2. Position in the runtime

The canonical runtime flow is:

```text
normalized frame
  -> planner
  -> PlannedSentence
  -> ConstructionPlan
  -> lexical resolution
  -> renderer backend
  -> SurfaceResult
```

Within that flow:

* `ConstructionPlan` is the canonical renderer-facing handoff object.
* `slot_map` is the semantic role/value payload carried inside `ConstructionPlan`.
* lexical resolution enriches slot values but does not change slot meaning.
* renderers consume `slot_map`; they do not redefine it.  

---

## 3. Core rule

A `slot_map` is **not** a full plan envelope.

A `slot_map` does **not** own:

* `construction_id`
* `lang_code`
* `generation_options`
* `topic_entity_id`
* `focus_role`
* `renderer_backend`
* `debug_info`

Those belong to the surrounding `ConstructionPlan` or `SurfaceResult`.

A `slot_map` owns only:

* canonical slot names
* normalized slot values
* construction-local semantic payloads needed for realization

This is the most important correction in the aligned Batch 1 model. The renderer contract defines `ConstructionPlan` as the canonical input, with `slot_map` as one field inside it. 

---

## 4. Design goals

The slot map must be:

1. **Construction-oriented**
   It expresses what a construction needs, not what one backend happens to consume.

2. **Renderer-agnostic**
   The same slot map must work for:

   * family renderers,
   * GF renderers,
   * safe-mode renderers.

3. **Language-independent at the semantic level**
   Slot maps carry semantic roles and normalized lexical/entity references, not hard-coded English templates.

4. **Stable across runtime layers**
   The same slot names and slot meanings must survive planning, lexical resolution, and rendering unchanged.

5. **Easy to validate and debug**
   It must be obvious which roles were supplied, which were missing, and which values required fallback. 

---

## 5. Canonical shape

A `slot_map` is a JSON-like mapping from **semantic slot name** to **normalized slot value**.

Canonical shape:

```json
{
  "subject": {
    "label": "Marie Curie",
    "entity_id": "Q7186",
    "qid": "Q7186",
    "entity_type": "person"
  },
  "profession": {
    "lemma": "physicist",
    "pos": "NOUN",
    "source": "lexicon",
    "confidence": 0.92,
    "features": {
      "number": "sg"
    }
  },
  "nationality": {
    "lemma": "Polish",
    "pos": "ADJ",
    "source": "lexicon",
    "confidence": 0.95
  }
}
```

Runtime type:

```python
SlotMap = dict[str, Any]
```

Rules:

* keys MUST be canonical semantic slot names,
* values MUST be normalized references, normalized literals, or explicitly allowed scalar fallbacks,
* slot maps MUST be JSON-serializable for debugging, tests, and schemas.  

---

## 6. Relationship to `ConstructionPlan`

`slot_map` is carried by `ConstructionPlan`.

Canonical plan shape:

```json
{
  "construction_id": "copula_equative_classification",
  "lang_code": "fr",
  "slot_map": {
    "subject": {
      "label": "Victor Hugo",
      "entity_id": "Q535",
      "qid": "Q535",
      "entity_type": "person"
    },
    "profession": {
      "lemma": "écrivain",
      "pos": "NOUN",
      "source": "lexicon",
      "confidence": 0.94
    },
    "nationality": {
      "lemma": "français",
      "pos": "ADJ",
      "source": "lexicon",
      "confidence": 0.95
    }
  },
  "generation_options": {
    "tense": "present",
    "register": "neutral",
    "allow_fallback": true
  },
  "topic_entity_id": "Q535",
  "focus_role": "profession"
}
```

Required `ConstructionPlan` fields are:

* `construction_id`
* `lang_code`
* `slot_map`
* `generation_options`

Optional plan-level fields include:

* `topic_entity_id`
* `focus_role`
* `lexical_bindings`
* `provenance` 

---

## 7. What does **not** belong in `slot_map`

The following are **not canonical slot-map fields** and must not be embedded inside runtime `slot_map` objects:

* `construction_id`
* `lang_code`
* `slot_map_version`
* `frame_ref`
* `discourse`
* `generation`
* `generation_options`
* `lexical_requirements`
* `metadata`
* `renderer_backend`
* `debug_info`

Those belong to:

* `ConstructionPlan`
* construction registry/spec metadata
* lexical-resolution metadata
* renderer output metadata

A legacy serialized envelope may still exist in old docs or compatibility tooling, but new runtime code must treat `slot_map` as the inner role/value object only. This change aligns the slot-map contract with the architecture and renderer contracts.  

---

## 8. Canonical naming rules

### 8.1 Naming style

All slot keys must use:

* `snake_case`
* semantic role names
* stable, backend-independent names

Examples:

* `subject`
* `predicate`
* `predicate_nominal`
* `predicate_adjective`
* `location`
* `possessor`
* `possessed`
* `topic`
* `comment`
* `time`
* `quantity`
* `profession`
* `nationality`

### 8.2 Avoid renderer-specific names

Do **not** use names tied to one backend’s internal implementation.

Invalid as canonical slot keys:

* `SUBJ`
* `PRED_NP`
* `COP`
* `GF_ARG`
* `AST_NODE`

These may appear only inside backend-private intermediate objects.

### 8.3 Construction IDs

`construction_id` values are selected by the planner and live on `ConstructionPlan`, not in `slot_map`.

New runtime examples should use canonical snake_case construction IDs such as:

* `copula_equative_simple`
* `copula_equative_classification`
* `copula_locative`
* `topic_comment_eventive`
* `transitive_event`

Legacy dotted IDs are migration-only and should not be introduced into new slot-map examples. The frame-to-construction mapping and GF-alignment docs already use snake_case IDs across migrated construction families.  

---

## 9. Canonical slot value types

A slot value should be one of:

1. `EntityRef`
2. `LexemeRef`
3. a normalized literal-like value
4. a structured time or quantity value
5. a raw scalar fallback only when explicitly allowed

---

## 10. Canonical reference objects

### 10.1 `EntityRef`

Used for entity-like participants.

Recommended stable shape:

```json
{
  "label": "Alan Turing",
  "entity_id": "Q7251",
  "qid": "Q7251",
  "surface_key": "alan_turing",
  "entity_type": "person",
  "gender": "m",
  "number": "sg",
  "person": "3",
  "animacy": "animate",
  "features": {},
  "metadata": {}
}
```

Rules:

* `label` SHOULD be present for named entities.
* `entity_id` SHOULD be used when a stable internal or canonical ID exists.
* `qid` MAY be carried when Wikidata identity is known.
* `surface_key` MAY be used for planner-stable participant identity.
* renderers MUST treat `EntityRef` as semantic input, not as permission to invent a different participant. 

### 10.2 `LexemeRef`

Used for lexical items that require realization.

Recommended stable shape:

```json
{
  "lemma": "mathematician",
  "lexeme_id": null,
  "qid": null,
  "lang_code": "en",
  "pos": "NOUN",
  "source": "lexicon",
  "confidence": 0.92,
  "surface_hint": null,
  "features": {}
}
```

Rules:

* `lemma` is required.
* `pos` is strongly recommended.
* `source` and `confidence` should always be present after lexical resolution.
* `surface_hint` is optional and must never replace `lemma` as canonical lexical identity.  

### 10.3 `TimeRef`

Suggested shape:

```json
{
  "start": "1995-01-01",
  "end": null,
  "point": null,
  "precision": "day"
}
```

### 10.4 `QuantityRef`

Suggested shape:

```json
{
  "value": 10,
  "unit": "km",
  "approximate": false,
  "lower_bound": null,
  "upper_bound": null,
  "time": null,
  "extra": {}
}
```

---

## 11. Slot categories

### 11.1 Core participant slots

Common role names used across constructions:

* `subject`
* `predicate`
* `predicate_nominal`
* `predicate_adjective`
* `object`
* `agent`
* `patient`
* `recipient`
* `theme`
* `instrument`
* `experiencer`
* `possessor`
* `possessed`

### 11.2 Circumstantial slots

* `location`
* `source`
* `goal`
* `time`
* `manner`
* `cause`
* `purpose`
* `condition`
* `comparison_target`
* `quantity`

### 11.3 Information-structure slots

* `topic`
* `comment`
* `focus`
* `background`

### 11.4 Construction-local semantic slots

Some constructions require stable local names beyond the shared base set, for example:

* `profession`
* `nationality`
* `event_subject`
* `event_predicate`
* `event_object`

Construction-local names are valid when:

* they are documented by the construction spec,
* they remain semantic,
* they are not backend-specific,
* they are reused consistently across renderers.  

---

## 12. Construction-specific slot rules

Every construction must define:

1. required slots,
2. optional slots,
3. accepted slot value types,
4. slot-local feature expectations,
5. defaulting rules,
6. fallback behavior.

These rules live in the construction registry and construction spec, not inside each runtime `slot_map`. The slot map carries the values; the registry defines the contract. 

---

## 13. Canonical slot value rules

### 13.1 Prefer structured values over bare strings

Preferred:

```json
{
  "subject": {
    "label": "Marie Curie",
    "qid": "Q7186",
    "entity_type": "person"
  }
}
```

Allowed fallback:

```json
{
  "subject": "Marie Curie"
}
```

### 13.2 Raw strings are controlled fallback only

Bare strings are allowed only when:

* lexical resolution is unavailable or incomplete,
* the construction allows raw fallback,
* fallback is visible in lexical-resolution metadata or `debug_info`,
* the renderer documents how such fallback is realized. 

### 13.3 Features stay attached to the slot value they modify

Preferred:

```json
{
  "profession": {
    "lemma": "physicist",
    "pos": "NOUN",
    "features": {
      "gender": "f",
      "number": "sg"
    }
  }
}
```

Avoid:

```json
{
  "profession": "physicist",
  "global_gender": "f"
}
```

### 13.4 Slot values must not contain backend payloads

Invalid examples include:

* GF AST fragments
* already-linearized sentence text
* renderer-private node types
* engine-specific token arrays as canonical slot content

The slot builder contract explicitly forbids renderer-specific strings and already-linearized sentence text in slot output. 

---

## 14. Lexical resolution boundary

Lexical resolution consumes the `ConstructionPlan` and enriches slot values without changing slot identity.

It may:

* turn raw strings into `EntityRef`,
* turn raw profession strings into `LexemeRef`,
* attach `source`, `confidence`, and `features`,
* apply construction-sensitive lexical behavior.

It must not:

* rename slots,
* choose a different construction,
* silently drop required meaning,
* move plan-level options into the slot map.  

---

## 15. Examples

### 15.1 `copula_equative_classification`

`ConstructionPlan`:

```json
{
  "construction_id": "copula_equative_classification",
  "lang_code": "en",
  "slot_map": {
    "subject": {
      "label": "Marie Curie",
      "entity_id": "Q7186",
      "qid": "Q7186",
      "entity_type": "person"
    },
    "profession": {
      "lemma": "physicist",
      "pos": "NOUN",
      "source": "lexicon",
      "confidence": 0.92,
      "features": {
        "number": "sg"
      }
    }
  },
  "generation_options": {
    "tense": "present",
    "polarity": "affirmative",
    "register": "neutral"
  },
  "topic_entity_id": "Q7186",
  "focus_role": "profession"
}
```

### 15.2 `copula_locative`

`slot_map`:

```json
{
  "subject": {
    "label": "Paris",
    "entity_id": "Q90",
    "qid": "Q90",
    "entity_type": "city"
  },
  "location": {
    "label": "France",
    "entity_id": "Q142",
    "qid": "Q142",
    "entity_type": "country"
  }
}
```

### 15.3 `topic_comment_eventive`

`slot_map`:

```json
{
  "topic": {
    "label": "Marie Curie",
    "entity_id": "Q7186",
    "qid": "Q7186",
    "entity_type": "person"
  },
  "event_subject": {
    "label": "she",
    "entity_type": "pronoun"
  },
  "event_predicate": {
    "lemma": "discover",
    "pos": "VERB",
    "source": "lexicon",
    "confidence": 0.95,
    "features": {
      "tense": "past"
    }
  },
  "event_object": {
    "label": "polonium",
    "entity_id": "Q979",
    "qid": "Q979",
    "entity_type": "chemical_element"
  }
}
```

### 15.4 Biography-compatible plan without a bio-only slot-map format

`ConstructionPlan`:

```json
{
  "construction_id": "copula_equative_classification",
  "lang_code": "fr",
  "slot_map": {
    "subject": {
      "label": "Victor Hugo",
      "entity_id": "Q535",
      "qid": "Q535",
      "entity_type": "person"
    },
    "profession": {
      "lemma": "écrivain",
      "pos": "NOUN",
      "source": "lexicon",
      "confidence": 0.94,
      "features": {
        "number": "sg"
      }
    },
    "nationality": {
      "lemma": "français",
      "pos": "ADJ",
      "source": "lexicon",
      "confidence": 0.95
    }
  },
  "generation_options": {
    "tense": "present",
    "sentence_kind": "definition",
    "register": "neutral",
    "allow_fallback": true
  },
  "topic_entity_id": "Q535",
  "focus_role": "profession"
}
```

This preserves biography behavior without creating a second biography-shaped slot-map contract. 

---

## 16. Validation rules

A valid `slot_map` must satisfy all of the following:

1. it is an object / mapping,
2. all keys are non-empty canonical slot names,
3. required construction slots are present,
4. slot values are normalized references, normalized structured values, or explicitly allowed scalar fallbacks,
5. no renderer-specific internal keys appear as canonical slot names,
6. no plan-level fields are duplicated inside the slot map.

A `slot_map` is invalid if:

* required slots are missing,
* slot names are backend internals,
* slot values are only free-form prose with no structured role assignment,
* required lexical values are missing and fallback is forbidden,
* it embeds `construction_id`, `lang_code`, `generation_options`, or `debug_info` as if they were slot keys.

Before realization, the runtime must validate the construction, required roles, role value types, normalized `lang_code`, and backend capability. 

---

## 17. Compatibility policy

### 17.1 Backward compatibility

Legacy code may still build or consume plain dict slot maps during migration.

That is acceptable only when those dicts still obey the canonical slot-naming and slot-value rules.

### 17.2 Legacy serialized envelopes

Older docs may show a full serialized “slot map” envelope containing fields such as:

* `slot_map_version`
* `construction_id`
* `lang_code`
* `frame_ref`
* `discourse`
* `generation`
* `slots`
* `lexical_requirements`
* `metadata`

That format should be treated as a legacy documentation shape, not the canonical runtime object.

### 17.3 Forward compatibility

New constructions may add new semantic slot names if they:

* document them,
* keep them semantic,
* keep plan-level fields outside the slot map,
* do not break existing constructions.

### 17.4 Deprecation policy

The following patterns are legacy and should be phased out:

* full-envelope slot maps used as the canonical runtime object,
* duplicated plan fields inside slot maps,
* renderer-specific keys in slot maps,
* hidden frame-to-renderer shortcuts that bypass slot-map construction.

---

## 18. Reserved and recommended names

### 18.1 Reserved plan-level fields

These are reserved by `ConstructionPlan`, not by `slot_map`:

* `construction_id`
* `lang_code`
* `generation_options`
* `topic_entity_id`
* `focus_role`
* `lexical_bindings`
* `provenance`

### 18.2 Recommended shared slot names

These are recommended as shared semantic slot names:

* `subject`
* `predicate`
* `predicate_nominal`
* `predicate_adjective`
* `object`
* `agent`
* `patient`
* `recipient`
* `theme`
* `location`
* `time`
* `quantity`
* `topic`
* `comment`
* `profession`
* `nationality`

---

## 19. Debugging and observability

`debug_info` is not part of the slot map itself.

It is derived from:

* `construction_id`
* `lang_code`
* `slot_map`
* lexical-resolution metadata
* backend selection
* fallback behavior

Recommended debug fields include:

```json
{
  "construction_id": "copula_equative_classification",
  "renderer_backend": "family",
  "lang_code": "fr",
  "slot_keys": ["subject", "profession", "nationality"],
  "fallback_used": false,
  "lexical_resolution": {
    "profession": {
      "source": "lexicon",
      "confidence": 0.94
    },
    "nationality": {
      "source": "lexicon",
      "confidence": 0.95
    }
  },
  "warnings": []
}
```

The debug contract requires stable top-level diagnostics, but `debug_info` itself remains separate from the slot map. 

---

## 20. Relationship to other contracts

This document is aligned with:

* `construction_runtime_contract.md`
* `planner_realizer_interfaces.md`
* `lexical_resolution_contract.md`
* `frame_to_construction_mapping.md`
* `debug_info_contract.md`
* `construction_renderer_contract.md`

Conflict rule:

* if the issue is about plan-level fields, `ConstructionPlan` and renderer-contract docs win;
* if the issue is about slot naming or slot value shape, this document wins;
* if the issue is about lexical provenance or fallback, the lexical-resolution contract wins.

Any disagreement must be corrected immediately. Slot naming drift is a contract error.  

---

## 21. Implementation guidance

### 21.1 Frame-to-slots bridge

The bridge layer should:

* read a `PlannedSentence`,
* inspect `construction_id`,
* extract semantic values from the normalized frame,
* normalize them into canonical slot names,
* emit one valid `slot_map`.

### 21.2 Lexical-resolution step

The lexical resolver should:

* consume the `ConstructionPlan`,
* enrich slot values in place or in a lexicalized copy,
* preserve slot identity,
* attach provenance and confidence.

### 21.3 Renderer behavior

Renderers must:

* accept a validated `ConstructionPlan`,
* consume the canonical `slot_map`,
* reject unsupported constructions explicitly,
* never silently reinterpret slot names,
* never require hidden planner state outside the plan contract.

### 21.4 Construction modules

Each construction module must publish:

* its `construction_id`,
* required slots,
* optional slots,
* accepted value types,
* slot-local feature expectations,
* defaulting behavior.

---

## 22. Final rule

The slot map is the **single semantic role/value payload** shared across planning, lexical resolution, and realization.

It is not a second plan object.

If a renderer or construction needs data not available in the slot map, then one of two things is true:

1. that data belongs in `ConstructionPlan` and must be added there, or
2. the slot map needs a new semantic slot.

No hidden contract is allowed.

