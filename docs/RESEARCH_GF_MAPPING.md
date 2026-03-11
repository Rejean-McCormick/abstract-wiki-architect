# GF Integration Design

Status: proposed
Owner: SKA runtime maintainers
Scope: integrate selected parts of **Grammatical Framework (GF)** into **SemantiK Architect (SKA)** while preserving SKA’s planner-first, construction-centered runtime.

---

## 1. Purpose

This document defines how GF fits into SKA’s runtime and tooling model.

The key decision is:

> **GF is a renderer backend and an offline enrichment source, not the architecture itself.**

This document exists to remove drift between:

* the documented planner/construction architecture,
* the current runtime generation stack,
* GF-backed realization,
* family-engine realization,
* safe-mode fallback,
* offline GF-derived morphology, syntax, and QA assets.

It makes explicit what is already true in the repository:

* GF/PGF is already part of the generation stack,
* family engines remain first-class,
* lexical resolution remains a shared SKA concern,
* runtime authority belongs to planner + construction contracts, not to a backend.

---

## 2. Goals and Non-Goals

## 2.1 Goals

1. **Use GF where it actually fits**

   * as an **optional runtime renderer backend** for selected constructions and languages,
   * as an **offline source** of morphology paradigms, syntactic patterns, and QA examples,
   * as a **grammar-engineering reference** for improving SKA’s constructions and family engines.

2. **Keep SKA’s architecture intact**

   SKA remains centered on:

   * semantic frames,
   * discourse/planning,
   * construction selection,
   * construction plans,
   * lexical resolution,
   * family engines,
   * language/morphology data.

3. **Keep planning authoritative**

   Runtime generation remains:

   ```text
   frame -> planner -> construction plan -> lexical resolution -> renderer backend -> surface result
   ```

   GF consumes the same runtime contract as other renderers.

4. **Support mixed backend capability**

   * some languages/constructions may use GF,
   * some may use family engines,
   * some may fall back to safe mode.

   All three must coexist without semantic drift.

5. **Make integration auditable**

   * clear capability metadata,
   * clear runtime traces when GF is selected,
   * versioned and reviewable offline imports,
   * explicit provenance on GF-derived artifacts.

6. **Keep GF optional**

   * runtime does not require GF unless the selected backend is GF,
   * offline tooling is isolated,
   * non-GF languages continue to work through family or safe-mode backends.

---

## 2.2 Non-Goals

This design does **not**:

* make GF the core architecture of SKA,
* make all runtime generation dependent on GF,
* adopt GF ASTs as SKA’s primary internal contract,
* require every language to have a GF runtime path,
* replace family engines, lexicon resolution, or JSON language/morphology data.

This design also does **not** require:

* parsing,
* reversible grammar support,
* full concrete GF coverage for every language,
* direct exposure of GF ASTs to API clients.

---

## 3. Executive Summary

GF has two valid roles in SKA:

1. **Runtime role**

   * GF is a renderer backend for selected `(lang_code, construction_id)` pairs.

2. **Offline role**

   * GF resources can be harvested into morphology data, syntax notes, QA material, and coverage/provenance artifacts.

GF is therefore:

* **not** the architecture,
* **not** offline-only,
* **not** mandatory,
* **not** the semantic or planning layer.

The authoritative SKA runtime remains:

```text
API payload
  -> frame normalization
  -> planner
  -> construction plan
  -> lexical resolution
  -> renderer backend
  -> surface result
```

GF participates inside the **renderer backend** layer at runtime and inside the **offline enrichment** layer outside runtime.

---

## 4. Current Architectural Position

SKA already contains the main ingredients required for this integration:

* semantic/domain frames,
* discourse/planning,
* `PlannedSentence`,
* `construction_id`,
* construction inventory,
* family-oriented engines,
* lexicon and lexical normalization,
* GF integration in the current generation stack.

The current architectural tension is that the repository contains both:

* the intended planner/construction architecture, and
* a still-existing direct generation path that can bypass the shared runtime contract.

This document resolves that tension by making GF subordinate to the same runtime boundary used by other backends.

---

## 5. Architectural Decision

## 5.1 Authoritative runtime contract

The authoritative runtime flow is:

```text
API payload
  -> normalized frame
  -> planner
  -> construction plan
  -> lexical resolution
  -> renderer backend
  -> surface result
```

This implies:

* GF must consume a `ConstructionPlan`, not raw API payloads as its primary contract.
* family engines must consume the same plan.
* safe mode must consume the same plan.
* direct frame-to-GF generation is compatibility behavior only.

## 5.2 GF’s place in the runtime

GF sits in the **renderer layer**.

GF is **not**:

* the planner,
* the semantic model,
* the API contract,
* the lexicon subsystem,
* the source of construction truth.

GF **is**:

* a renderer backend for supported `(lang_code, construction_id)` pairs.

## 5.3 GF’s place in offline tooling

GF also sits in the **offline enrichment layer**.

GF can provide:

* morphology paradigms,
* syntax references,
* example sets,
* test material,
* coverage data,
* provenance metadata.

---

## 6. Canonical Runtime Boundary for GF

GF integration must use the same canonical runtime objects as the rest of Batch 1.

## 6.1 Renderer input

GF consumes a `ConstructionPlan` with at least:

* `construction_id`
* `lang_code`
* `slot_map`
* optional `topic_entity_id`
* optional `focus_role`
* `metadata`

Renderer-safe realization options belong under:

```python
metadata["generation_options"]
```

Typical option families include:

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

GF may also consume normalized lexical content already prepared by lexical resolution.

## 6.2 Renderer output

GF returns a `SurfaceResult` with:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend = "gf"`
* `debug_info`

Required debug keys include:

* `construction_id`
* `renderer_backend`
* `lang_code`
* `fallback_used`

Typical optional GF-specific debug fields include:

* `resolved_language`
* `gf_function`
* `ast`
* `backend_trace`
* `warnings`
* `timings_ms`

## 6.3 Boundary rule

GF may choose:

* backend-specific AST construction,
* concrete grammar selection,
* local linearization strategy.

GF may **not**:

* change `construction_id`,
* reinterpret slot meanings,
* invent missing semantic structure,
* become the planner by stealth.

---

## 7. GF Integration Modes

GF is integrated in two distinct modes.

## 7.1 Mode A — Runtime renderer backend

In this mode, GF is used during request-time generation.

Requirements:

* compiled PGF is available,
* `(lang_code, construction_id)` capability is declared,
* renderer dispatch selects GF,
* the GF adapter consumes the shared `ConstructionPlan` contract.

Typical use:

* high-fidelity realization for selected constructions,
* controlled multilingual generation,
* deterministic output where GF support is strong.

## 7.2 Mode B — Offline knowledge provider

In this mode, GF is not used in request-time generation.

Requirements:

* GF tools are available offline or in CI,
* export/harvest scripts produce intermediate artifacts,
* SKA conversion tools transform them into JSON/CSV/Markdown artifacts,
* provenance is preserved.

Typical use:

* morphology enrichment,
* syntax notes,
* construction review,
* test generation,
* regression support.

---

## 8. High-Level Integration Architecture

## 8.1 Planning layer

Authoritative planner-side responsibilities:

* normalized frames,
* discourse/planning,
* construction selection,
* `construction_id`,
* sentence packaging,
* topic/focus metadata.

## 8.2 Construction runtime contract

Shared runtime objects include:

* `PlannedSentence`
* `ConstructionPlan`
* `SlotMap`
* `EntityRef`
* `LexemeRef`
* `SurfaceResult`

This layer is the required boundary between planning and realization.

## 8.3 Renderer layer

Runtime renderer backends are:

* family backend,
* GF backend,
* safe-mode backend.

All must implement the same logical runtime surface:

```python
async def realize(construction_plan: ConstructionPlan) -> SurfaceResult
```

## 8.4 Offline GF layer

Offline GF tooling includes:

* export scripts,
* conversion scripts,
* provenance capture,
* import into JSON/CSV/docs,
* capability review material,
* QA artifact generation.

---

## 9. Runtime Data Flow

## 9.1 Runtime path

```text
Request JSON
  -> semantic frame normalization
  -> planner
  -> construction plan
  -> lexical resolution
  -> renderer dispatch
       -> gf backend
       -> family backend
       -> safe_mode backend
  -> surface result
  -> API response
```

## 9.2 Offline path

```text
GF grammars / RGL / examples
   -> export scripts
   -> intermediate GF artifacts
   -> SKA conversion tools
   -> morphology data / syntax notes / QA datasets / provenance docs
```

## 9.3 Isolation rule

* runtime does not require GF unless GF is selected,
* languages without GF support continue to work,
* offline GF tooling remains isolated from normal runtime execution,
* generated artifacts are stored as normal SKA assets, not as hidden backend state.

---

## 10. Backend Selection Policy

## 10.1 Selection inputs

Renderer dispatch should be based on:

* `(lang_code, construction_id)` capability,
* backend health/readiness,
* configuration flags,
* allowed fallback policy,
* explicit debug/test overrides when requested.

## 10.2 Recommended priority

1. **GF backend**

   * when the requested `(lang_code, construction_id)` is supported and healthy.

2. **Family backend**

   * when family realization is supported.

3. **Safe-mode backend**

   * when deterministic fallback is allowed.

## 10.3 Semantic guarantee

Backend choice may change:

* phrasing quality,
* morphology richness,
* debug detail,
* local idiomatic realization.

Backend choice must **not** silently change:

* `construction_id`,
* semantic role assignment,
* truth-conditional content,
* planner-authorized information packaging.

---

## 11. GF Runtime Backend Requirements

## 11.1 Input requirements

The GF adapter must consume:

* `construction_id`
* `lang_code`
* normalized `slot_map`
* lexicalized or lexicalizable slot values
* optional planner metadata
* `metadata["generation_options"]`

The GF adapter must **not** require:

* raw API request shape,
* router-specific payload hacks,
* domain-specific direct frame flattening as its long-term contract.

## 11.2 Output requirements

The GF adapter must return a `SurfaceResult` with:

* `text`
* `lang_code`
* `construction_id`
* `renderer_backend = "gf"`
* truthful `debug_info`

Recommended GF debug fields:

* `resolved_language`
* `gf_function`
* `ast`
* `slot_keys`
* `fallback_used`
* `backend_trace`

## 11.3 Legacy compatibility rule

If direct frame-to-GF behavior exists in legacy code, it must be treated as:

* compatibility-only behavior,
* isolated adapter logic,
* temporary migration support.

It must not remain the canonical runtime boundary.

---

## 12. Construction-Centered GF Capability

GF support must be tracked by **construction**, not just by language.

Correct capability unit:

```text
(lang_code, construction_id)
```

Examples:

* `("fr", "copula_equative_simple")`
* `("fr", "copula_locative")`
* `("en", "topic_comment_eventive")`

This matters because:

* a language may have GF assets but only partial construction coverage,
* different constructions may require different mapping quality,
* backend choice must be explicit and testable.

GF presence for a language is therefore **not enough** to claim runtime support.

---

## 13. Relationship to Family Engines

## 13.1 Family engines remain first-class

GF integration does **not** replace family engines.

Family engines remain necessary because they:

* scale across larger language inventories,
* encode SKA-native morphology/configuration,
* work where GF coverage is absent,
* support constructions beyond current GF coverage.

## 13.2 Division of responsibility

* **Planner / construction layer**

  * chooses structure and semantic packaging.

* **Lexical resolution**

  * normalizes entities and lexemes for realization.

* **GF backend**

  * realizes supported constructions for supported languages.

* **Family backends**

  * realize supported constructions using family-native morphology and language data.

* **Safe-mode backend**

  * provides deterministic fallback when stronger backends are unavailable.

---

## 14. Relationship to Lexical Resolution

GF integration must not collapse lexical handling into a grammar-only model.

Lexical resolution remains a shared SKA concern because it is reused by:

* multiple constructions,
* multiple backends,
* multiple languages,
* QA/coverage tooling,
* entity/lexicon bridges.

GF may contribute lexical insights and examples, but runtime lexical normalization remains outside the GF adapter.

Practical rule:

* renderers consume lexical decisions,
* they do not own canonical lexical classification.

---

## 15. Offline Morphology Integration

## 15.1 Objective

Use GF morphology resources to enrich SKA morphology data without forcing GF at runtime for every language.

## 15.2 Target outputs

GF exports may enrich:

* language/family morphology configs,
* language cards,
* lexicon-side feature data where appropriate,
* construction capability metadata.

## 15.3 Intermediate representation

Intermediate export files should preserve:

* language,
* GF version,
* module provenance,
* category names,
* slot inventories,
* paradigm examples,
* transformation rules.

## 15.4 Conversion responsibilities

Conversion tooling should:

1. read GF exports,
2. map GF categories/features to SKA categories/features,
3. generate or merge SKA artifacts,
4. attach provenance metadata,
5. flag unmapped or suspicious items for review.

---

## 16. Offline Syntax Pattern Harvesting

## 16.1 Objective

Use GF analyses and examples to improve SKA constructions and family-engine defaults.

## 16.2 What is harvested

Potential harvest outputs include:

* construction insights,
* parameterization patterns,
* word-order options,
* feature interactions,
* curated examples,
* regression examples.

GF syntax code is **not** imported as SKA’s primary runtime logic.

## 16.3 Deliverables

* family-specific syntax notes,
* construction adjustments,
* updated language/family configuration where justified,
* regression example sets.

---

## 17. Offline Test Integration

## 17.1 Objective

Use GF grammars and generated examples to create high-value QA material.

## 17.2 Target outputs

* JSON/CSV QA rows,
* minimal pairs,
* agreement tests,
* construction-specific regression suites,
* backend parity checks where feasible.

## 17.3 Provenance requirements

Each GF-derived test artifact should record:

* source = GF/RGL
* GF version
* modules used
* language
* generation date
* transformation script version

---

## 18. Repo Alignment

GF integration work should align with the actual runtime adapter and grammar locations in the repository.

Relevant runtime/backend paths include:

```text
app/adapters/engines/construction_realizer.py
app/adapters/engines/family_construction_adapter.py
app/adapters/engines/gf_construction_adapter.py
app/adapters/engines/safe_mode_construction_adapter.py
app/adapters/engines/gf_wrapper.py
app/adapters/engines/gf_engine.py
app/adapters/engines/python_engine_wrapper.py
```

Relevant contract/runtime docs include:

```text
docs/RESEARCH_GF_MAPPING.md
docs/contracts/construction_runtime_contract.md
docs/contracts/planner_realizer_interfaces.md
docs/grammar/construction_renderer_contract.md
docs/architecture/construction_runtime_alignment.md
docs/architecture/construction_runtime_flow.md
```

Relevant grammar/runtime surface files include:

```text
gf/SemantikArchitect.gf
gf/WikiI.gf
gf/WikiEng.gf
gf/WikiFre.gf
```

This document is about how those areas fit together, not about creating a separate parallel architecture.

---

## 19. Implementation Plan

## Milestone 0 — Runtime alignment

1. make the shared construction runtime contract authoritative,
2. ensure planner output is authoritative,
3. adapt GF to consume `ConstructionPlan`,
4. isolate direct frame-to-GF generation as compatibility behavior only.

## Milestone 1 — First canonical runtime GF slice

1. pick one construction family,
2. support one or two languages through the GF backend,
3. add standardized debug/provenance fields,
4. validate semantic parity against family realization.

## Milestone 2 — Offline morphology and syntax harvesting

1. add or formalize GF export/conversion tooling,
2. export one language slice,
3. convert it into SKA-native artifacts,
4. document provenance and review workflow.

## Milestone 3 — QA integration

1. export GF-derived test cases,
2. convert them into SKA QA suites,
3. add construction-aware regression tests,
4. track backend parity where possible.

## Milestone 4 — Broader construction coverage

1. expand GF support by construction,
2. expand capability metadata,
3. expand offline harvest coverage where useful,
4. keep backend behavior explicit and reviewable.

---

## 20. Risks and Mitigations

## 20.1 Risk: GF becomes hidden architecture

If more logic drifts into the GF adapter, planner/construction authority erodes.

**Mitigation**

* keep `ConstructionPlan` authoritative,
* keep backend interfaces shared,
* forbid backend-private construction semantics.

## 20.2 Risk: mismatch between GF and SKA feature systems

GF categories and SKA feature inventories will not always align directly.

**Mitigation**

* use explicit mapping tables,
* allow partial imports,
* validate unmapped features,
* require human review for promoted changes.

## 20.3 Risk: semantic drift across backends

Different backends may realize the same construction differently enough to alter meaning or discourse packaging.

**Mitigation**

* compare outputs at the construction level,
* keep `slot_map` explicit,
* require debug traces showing construction and backend.

## 20.4 Risk: maintenance burden

GF updates, module changes, or grammar drift may create import or runtime instability.

**Mitigation**

* record GF version in every derived artifact,
* treat offline imports as reviewable diffs,
* isolate capability metadata per `(lang_code, construction_id)`.

## 20.5 Risk: overfitting to GF assumptions

GF is powerful, but not the only valid linguistic representation for SKA.

**Mitigation**

* treat GF as one backend and one source,
* preserve family-engine and lexicon-centered architecture,
* avoid baking GF-specific assumptions into public runtime contracts.

---

## 21. Licensing and Attribution

GF-derived artifacts and GF-backed runtime components must preserve attribution metadata.

At minimum, track:

* source
* GF version
* relevant modules
* license note
* generation timestamp

Example:

```json
{
  "_meta": {
    "source": "GF Resource Grammar Library",
    "license": "BSD-style",
    "gf_version": "3.12",
    "generated_at": "2026-03-10T00:00:00Z"
  }
}
```

Runtime debug info may also expose non-sensitive GF provenance when useful for testing or review.

---

## 22. Summary

SKA does **not** adopt GF’s architecture as SKA’s architecture.

SKA does **use GF in two roles**:

1. **runtime renderer backend** for selected `(lang_code, construction_id)` pairs,
2. **offline knowledge source** for morphology, syntax insights, and QA material.

The authoritative SKA runtime remains:

```text
frame -> planner -> construction plan -> lexical resolution -> renderer backend -> surface result
```

GF is therefore:

* useful,
* optional,
* construction-aware,
* runtime-valid,
* architecturally subordinate to SKA’s shared runtime contract.

The main design correction relative to the older draft is explicit:

* GF is **not** forced into an offline-only role,
* GF is already part of the actual generation stack,
* but GF still remains **one backend among several**, not the runtime center.
