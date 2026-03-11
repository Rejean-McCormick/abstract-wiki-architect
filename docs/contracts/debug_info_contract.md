# Debug Info Contract

Status: normative for planner-centered runtime; backward-compatible with legacy response payloads
Applies to: API generation responses, internal `SurfaceResult` objects, legacy `Sentence`-compatible payloads, frontend generation result payloads, test fixtures

---

## 1. Purpose

`debug_info` is the machine-readable diagnostics payload attached to a generated sentence/result.

It exists to support:

* runtime debugging,
* planner/construction tracing,
* lexical-resolution tracing,
* renderer comparison,
* QA assertions,
* frontend developer tooling,
* safe observability without leaking secrets.

`debug_info` is diagnostic metadata, not user-facing content.

---

## 2. Where it appears

### 2.1 API response

`debug_info` may be attached to sentence-like responses returned by generation endpoints.

Example response shape:

```json
{
  "text": "Alan Turing is a mathematician.",
  "lang_code": "en",
  "debug_info": {
    "schema_version": "1.0",
    "producer": "gf_construction_adapter",
    "renderer_backend": "gf",
    "construction_id": "copula_equative_simple"
  }
}
```

### 2.2 Internal domain/result objects

For the aligned runtime, `debug_info` is attached to:

* `SurfaceResult`
* API response DTOs derived from `SurfaceResult`
* test doubles / fake generation outputs

During migration, it may also appear on:

* legacy `Sentence` objects
* legacy `GenerationResult`-style wrappers

---

## 3. Core rules

### 3.1 Presence rules

For new planner-centered runtime producers, `debug_info` **MUST** be present on internal `SurfaceResult` outputs.

For public API responses, `debug_info` **SHOULD** be present when diagnostics are enabled or when runtime tracing is required.

Legacy compatibility responses may omit `debug_info`, but new code must not rely on omission as the default design.

### 3.2 Object only

If present, `debug_info` **MUST** be a JSON object / dictionary.

It must never be:

* a string,
* a list,
* a number,
* nested under another arbitrary wrapper.

### 3.3 Safe for logs and UI diagnostics

`debug_info` **MUST NOT** contain:

* API keys,
* bearer tokens,
* raw credentials,
* auth headers,
* full secrets,
* raw secret-bearing exception context,
* full unredacted PII beyond already-public labels,
* full env dumps,
* internal filesystem paths in public production responses unless explicitly allowed in development mode,
* full upstream payloads if they may contain sensitive data.

### 3.4 Machine-readable first

Values should be structured and stable.

Prefer:

```json
{ "renderer_backend": "gf", "fallback_used": false }
```

Over:

```json
{ "note": "GF worked fine and no fallback was needed" }
```

### 3.5 Forward-compatible readers

Readers **MUST** tolerate:

* missing keys,
* unknown keys,
* partial payloads,
* legacy payloads from older engines.

### 3.6 Additive evolution only

New keys may be added.

Existing keys must not be silently repurposed.

---

## 4. Canonical shape

New producers should emit this canonical envelope when `debug_info` is present.

```json
{
  "schema_version": "1.0",
  "producer": "gf_construction_adapter",
  "renderer_backend": "gf",
  "construction_id": "copula_equative_simple",
  "lang_code_resolved": "WikiEng",
  "input_kind": "construction_plan",
  "trace_id": "optional-trace-id",
  "fallback_used": false,
  "planning": {},
  "lexical_resolution": {},
  "realization": {},
  "timings_ms": {},
  "warnings": [],
  "errors": []
}
```

Rules:

* `renderer_backend` is the canonical backend field name.
* `construction_id` should reflect the planner-selected construction.
* `input_kind` should identify the contract consumed by the producer.
* nested sections should be preferred over unstructured top-level debug sprawl.

---

## 5. Required keys for new producers

If a new planner-centered producer emits `debug_info`, the following keys are required.

### 5.1 `schema_version`

* Type: `string`
* Example: `"1.0"`

Version of this contract used by the payload.

### 5.2 `producer`

* Type: `string`
* Example: `"gf_construction_adapter"`, `"family_construction_adapter"`, `"safe_mode_construction_adapter"`

Name of the component that assembled the payload.

### 5.3 `renderer_backend`

* Type: `string`
* Allowed examples:

  * `"gf"`
  * `"family"`
  * `"safe_mode"`

Logical backend category used for realization.

### 5.4 `construction_id`

* Type: `string`
* Example: `"copula_equative_simple"`, `"copula_locative"`, `"topic_comment_eventive"`

Planner-selected construction identifier for the realized sentence.

---

## 6. Recommended top-level keys

These are strongly recommended for all new producers.

### 6.1 `lang_code_resolved`

* Type: `string | null`
* Example: `"WikiEng"`, `"WikiFre"`, `"en"`

Final resolved runtime language identifier.

Use this instead of ambiguous fields like `resolved_language` as the canonical top-level field.

### 6.2 `input_kind`

* Type: `string`
* Allowed examples:

  * `"frame"`
  * `"planned_sentence"`
  * `"construction_plan"`
  * `"ninai_tree"`

Specifies the input contract consumed by the producer.

### 6.3 `trace_id`

* Type: `string | null`

Optional request or tool trace identifier when available.

### 6.4 `fallback_used`

* Type: `boolean`

Indicates whether the backend had to fall back from its preferred path.

### 6.5 `warnings`

* Type: `array[string]`

Compact warning codes or stable warning messages.

### 6.6 `errors`

* Type: `array[object|string]`

Structured non-fatal diagnostic errors, if any.

---

## 7. Nested sections

To avoid top-level key sprawl, new debug payloads should prefer these nested sections.

### 7.1 `planning`

Planning-stage metadata.

Example:

```json
{
  "planning": {
    "planner": "discourse.planner",
    "construction_id": "copula_equative_simple",
    "topic_entity_id": "Q7251",
    "focus_role": "predicate_nominal",
    "sentence_kind": "definition",
    "domain": "generic"
  }
}
```

Recommended keys:

* `planner`
* `construction_id`
* `topic_entity_id`
* `focus_role`
* `sentence_kind`
* `domain`

### 7.2 `lexical_resolution`

Lexeme/entity normalization metadata.

Example:

```json
{
  "lexical_resolution": {
    "resolved_slots": {
      "subject": "entity_ref",
      "predicate_nominal": "lexeme_ref"
    },
    "sources": {
      "subject": "frame.subject",
      "predicate_nominal": "local_lexicon"
    },
    "fallback_slots": [],
    "confidence": 0.91
  }
}
```

Recommended keys:

* `resolved_slots`
* `sources`
* `fallback_slots`
* `confidence`
* `notes`

### 7.3 `realization`

Renderer-specific realization metadata.

Example:

```json
{
  "realization": {
    "renderer_backend": "gf",
    "ast": "mkCopulaEquativeSimple (...)",
    "template_used": null,
    "surface_strategy": "gf_linearization",
    "lang_code_resolved": "WikiEng",
    "family": null,
    "profile": null
  }
}
```

Recommended keys:

* `renderer_backend`
* `ast`
* `template_used`
* `surface_strategy`
* `lang_code_resolved`
* `family`
* `profile`
* `backend_trace`

### 7.4 `timings_ms`

Timing breakdown in milliseconds.

Example:

```json
{
  "timings_ms": {
    "planning": 0.2,
    "lexical_resolution": 0.4,
    "realization": 1.8,
    "total": 2.7
  }
}
```

---

## 8. Legacy key compatibility

Older parts of the system already emit ad hoc debug fields such as:

* `backend`
* `engine`
* `resolved_language`
* `ast`
* `template_used`
* `source`

These are still accepted for backward compatibility.

### 8.1 Reader requirements

All readers must accept payloads like:

```json
{
  "ast": "mkCopulaEquativeSimple (...)",
  "resolved_language": "WikiFre"
}
```

or:

```json
{
  "engine": "python_fast",
  "template_used": "{name} is a {profession}"
}
```

or:

```json
{
  "source": "dummy-test"
}
```

### 8.2 Normalized interpretation

When consuming legacy payloads, map them conceptually as follows:

| Legacy key          | Canonical meaning                                        |
| ------------------- | -------------------------------------------------------- |
| `backend`           | `renderer_backend`                                       |
| `engine`            | `renderer_backend` or `realization.renderer_backend`     |
| `source`            | `producer`                                               |
| `resolved_language` | `lang_code_resolved` or `realization.lang_code_resolved` |
| `ast`               | `realization.ast`                                        |
| `template_used`     | `realization.template_used`                              |

### 8.3 Producer guidance

Do not remove legacy keys in one step if older tests or frontend tools still depend on them.

During migration, producers may emit both forms:

```json
{
  "schema_version": "1.0",
  "producer": "gf_construction_adapter",
  "renderer_backend": "gf",
  "lang_code_resolved": "WikiFre",
  "realization": {
    "ast": "mkCopulaEquativeSimple (...)",
    "lang_code_resolved": "WikiFre"
  },
  "backend": "gf",
  "resolved_language": "WikiFre",
  "ast": "mkCopulaEquativeSimple (...)"
}
```

This duplication is acceptable temporarily during migration, but the canonical keys above are the long-term contract.

---

## 9. Backend-specific guidance

### 9.1 GF backend

GF-based producers should normally include:

* `producer`
* `renderer_backend = "gf"`
* `lang_code_resolved`
* `construction_id`
* `realization.ast`
* `realization.lang_code_resolved`
* `fallback_used`

### 9.2 Family renderer backend

Family renderers should normally include:

* `producer`
* `renderer_backend = "family"`
* `construction_id`
* `realization.family`
* `realization.profile`
* `realization.surface_strategy`
* `fallback_used`

### 9.3 Safe-mode backend

Safe-mode producers should normally include:

* `producer`
* `renderer_backend = "safe_mode"`
* `construction_id`
* `realization.template_used`
* `realization.surface_strategy`
* `fallback_used`

---

## 10. Error handling rules

### 10.1 Fatal generation failure

If generation fails fatally, the API should use standard error responses.

Do not rely on `debug_info` as the only error carrier.

### 10.2 Non-fatal degradation

If generation succeeds with degraded quality, use:

* `fallback_used = true`
* a `warnings` entry
* optional structured `errors` entries

Example:

```json
{
  "schema_version": "1.0",
  "producer": "family_construction_adapter",
  "renderer_backend": "family",
  "construction_id": "copula_equative_classification",
  "fallback_used": true,
  "warnings": [
    "predicate_nominal_lexeme_unresolved"
  ]
}
```

---

## 11. Size and stability constraints

### 11.1 Size budget

`debug_info` should stay small enough for API responses and frontend rendering.

Recommended soft limit:

* target: under 4 KB
* hard warning threshold: 16 KB

### 11.2 Stable keys

Prefer stable identifiers/codes to prose.

Examples:

* use `construction_id: "copula_locative"`
* avoid `message: "Used the location sentence thing"`

### 11.3 Deterministic ordering

When possible, emit keys in a stable order for easier snapshot testing and log diffing.

Suggested order:

1. `schema_version`
2. `producer`
3. `renderer_backend`
4. `construction_id`
5. `lang_code_resolved`
6. `input_kind`
7. `trace_id`
8. `fallback_used`
9. `planning`
10. `lexical_resolution`
11. `realization`
12. `timings_ms`
13. `warnings`
14. `errors`

---

## 12. Privacy and security

`debug_info` must never contain:

* API keys
* auth headers
* full env dumps
* raw secret-bearing exception context
* internal filesystem paths in public production responses unless explicitly allowed in development mode
* full upstream payloads if they may contain sensitive data

Safe examples:

* language codes
* construction IDs
* template IDs
* AST strings
* test/mock producer labels
* non-sensitive trace IDs

---

## 13. JSON Schema sketch

This is an informal sketch for implementers.

```json
{
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "schema_version": { "type": "string" },
    "producer": { "type": "string" },
    "renderer_backend": { "type": "string" },
    "construction_id": { "type": ["string", "null"] },
    "lang_code_resolved": { "type": ["string", "null"] },
    "input_kind": { "type": "string" },
    "trace_id": { "type": ["string", "null"] },
    "fallback_used": { "type": "boolean" },
    "planning": { "type": "object" },
    "lexical_resolution": { "type": "object" },
    "realization": { "type": "object" },
    "timings_ms": { "type": "object" },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    },
    "errors": {
      "type": "array",
      "items": {}
    },

    "backend": { "type": ["string", "null"] },
    "engine": { "type": ["string", "null"] },
    "source": { "type": ["string", "null"] },
    "ast": { "type": ["string", "null"] },
    "resolved_language": { "type": ["string", "null"] },
    "template_used": { "type": ["string", "null"] }
  }
}
```

---

## 14. Examples

### 14.1 Current-style GF response

```json
{
  "text": "Alan Turing est un mathématicien britannique.",
  "lang_code": "fr",
  "debug_info": {
    "ast": "mkCopulaEquativeSimple (...)",
    "resolved_language": "WikiFre"
  }
}
```

### 14.2 Current-style template/safe-mode response

```json
{
  "text": "Shaka is a warrior.",
  "lang_code": "en",
  "debug_info": {
    "engine": "safe_mode",
    "template_used": "{name} is a {profession}"
  }
}
```

### 14.3 Canonical future response

```json
{
  "text": "Victor Hugo est un écrivain français.",
  "lang_code": "fr",
  "debug_info": {
    "schema_version": "1.0",
    "producer": "gf_construction_adapter",
    "renderer_backend": "gf",
    "construction_id": "copula_equative_classification",
    "lang_code_resolved": "WikiFre",
    "input_kind": "construction_plan",
    "trace_id": "req-9d7a3c",
    "fallback_used": false,
    "planning": {
      "planner": "discourse.planner",
      "construction_id": "copula_equative_classification",
      "topic_entity_id": "Q535",
      "focus_role": "predicate_nominal",
      "sentence_kind": "definition",
      "domain": "generic"
    },
    "lexical_resolution": {
      "resolved_slots": {
        "subject": "entity_ref",
        "predicate_nominal": "lexeme_ref"
      },
      "sources": {
        "subject": "frame.subject",
        "predicate_nominal": "local_lexicon"
      },
      "fallback_slots": [],
      "confidence": 0.54
    },
    "realization": {
      "renderer_backend": "gf",
      "ast": "mkCopulaEquativeClassification (...)",
      "lang_code_resolved": "WikiFre",
      "surface_strategy": "gf_linearization"
    },
    "timings_ms": {
      "planning": 0.2,
      "lexical_resolution": 0.4,
      "realization": 1.9,
      "total": 2.8
    },
    "warnings": [],
    "errors": []
  }
}
```

---

## 15. Conformance requirements

A producer is conformant if:

1. it emits `debug_info` on new internal planner-centered runtime results,
2. emitted `debug_info` is always an object,
3. it never includes secrets,
4. it uses `renderer_backend` as the canonical backend field,
5. it includes at least:

   * `schema_version`
   * `producer`
   * `renderer_backend`
   * `construction_id`
6. renderer-specific details live under nested sections when possible.

A reader is conformant if:

1. it accepts missing `debug_info` on legacy payloads,
2. it accepts unknown keys,
3. it accepts legacy top-level keys,
4. it does not crash on partial payloads.

---

## 16. Migration policy

### Phase 1

Allow legacy and canonical keys side by side.

### Phase 2

Update frontend, tools, and tests to prefer canonical keys.

### Phase 3

Require canonical keys for all new planner-centered runtime producers.

### Phase 4

Keep legacy keys only where compatibility is still required.

### Phase 5

Do not remove legacy keys without explicit release-note coverage.

---

## 17. Summary

`debug_info` is the stable diagnostics envelope for planner-centered runtime generation.

It must be:

* structured,
* machine-readable,
* safe,
* comparable across backends,
* backward-compatible for legacy readers,
* aligned to `SurfaceResult`,
* centered on `construction_id` and `renderer_backend`.

New code should emit the canonical envelope.

