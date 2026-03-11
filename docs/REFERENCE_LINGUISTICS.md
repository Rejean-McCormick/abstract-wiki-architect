# THEORY_NOTES.md

SemantiK Architect – Theoretical Positioning

This document explains how the architecture in this repository relates to
existing ideas in NLG and linguistic theory. It is **not** an implementation
spec, API contract, or schema definition. It is a conceptual map of:

* where the design is coming from,
* what theoretical traditions it is compatible with,
* what kind of multilingual NLG system it is trying to become.

It also clarifies a central architectural point:

> SemantiK Architect is **not** fundamentally a biography generator.

Biography is only one early domain. The intended architecture is
**planner-first**, **construction-centered**, **lexically mediated**,
and **multi-backend**.

The core runtime picture is:

```text
semantic input
  -> normalization
  -> frame-to-construction bridging
  -> planning
  -> ConstructionPlan
  -> lexical resolution
  -> realization backend
  -> SurfaceResult
  -> API response
```

That theoretical stance matters because it defines what the system is
allowed to become as it scales across domains, languages, and realization
technologies.

---

## 1. Purpose

SemantiK Architect is designed as a **practical multilingual NLG stack**
for Abstract Wikipedia and related structured-content workflows.

Its internal design is informed by:

* **grammar engineering**
* **construction grammar**
* **frame semantics**
* **abstract semantic representations**
* **typological and language-family modeling**
* **hybrid symbolic generation architectures**
* **microplanning / discourse-aware NLG**

The goal is to be:

* **engineered enough** for large-scale deployment,
* **theory-aware enough** to stay compatible with research-grade ideas,
* **modular enough** to support many languages and multiple realization backends.

The project is therefore best understood as a **construction-centered runtime**
with:

* semantic inputs,
* planner/discourse decisions,
* reusable constructions,
* explicit slot mapping,
* lexical resolution,
* family-aware realization,
* optional GF-based realization where it is strong.

---

## 2. High-level analogy: where this sits

Very roughly, SemantiK Architect sits near several known traditions,
without being reducible to any one of them.

* Like **Grammatical Framework (GF)**:

  * it separates language-independent structural intent from language-specific realization,
  * it treats many sentence patterns as reusable across languages,
  * it benefits from explicit abstract-to-concrete separation.

* Like a **Grammar Matrix** style project:

  * it factors cross-language regularities into reusable machinery,
  * it assumes many languages share deeper structural behavior,
  * it uses configuration and structured linguistic data rather than rewriting everything per language.

* Like **construction grammar** and **frame semantics**:

  * it treats recurrent clause and sentence patterns as reusable constructions,
  * it assumes meaning is realized through structural packaging, not isolated words alone,
  * it allows the same content to surface differently across constructions and languages.

* Like **AMR / UMR / Ninai-style abstract representations**:

  * it assumes there is a meaning layer distinct from wording,
  * it allows input notation to evolve independently from realization code,
  * it treats normalization and bridging as explicit architectural responsibilities.

What SemantiK Architect does **not** try to do is reproduce any one of these
traditions in pure form.

Instead, it borrows their core strengths:

* separation of concerns,
* explicit interfaces,
* reusable abstractions,
* cross-linguistic scaling,
* traceable runtime structure.

---

## 3. What kind of system this is

At the theoretical level, the intended architecture is:

```text
semantic input
  -> normalization
  -> frame-to-construction bridge
  -> planning
  -> ConstructionPlan / slot_map
  -> lexical resolution
  -> realization backend
  -> SurfaceResult
```

This is important.

The central unit is **not** a bio payload and **not** a specific grammar engine.
The central unit is a **planned constructional sentence**:
a sentence whose semantic roles, information structure, and construction choice
have already been determined before realization begins.

That means the system should be understood as:

* **planner-first**, not renderer-first,
* **construction-centric**, not domain-centric,
* **backend-agnostic**, not GF-only,
* **family-scalable**, not per-language handcrafted only,
* **lexically mediated**, not raw-string driven.

---

## 4. Relation to specific ideas and traditions

### 4.1 Grammatical Framework (GF)

GF separates:

* **abstract syntax**

  * language-independent structures,
  * typed constructors,
  * compositional meaning-to-form mapping,

from:

* **concrete syntax**

  * language-specific realization,
  * morphology,
  * word order,
  * agreement.

SemantiK Architect is strongly compatible with that way of thinking.

In SKA terms, the nearest equivalents are:

* normalized semantic frames,
* construction classes,
* planner output,
* `ConstructionPlan`,
* language-family and language-specific realization logic.

#### Similarities to GF

* There is an effort to keep meaning separate from realization.
* There is a desire to reuse structural patterns across languages.
* There is room for language-specific grammars or realizers.
* GF can function as one realization backend.

#### Differences from GF

* SKA is not built around a single abstract-syntax formalism.
* SKA allows multiple realization backends, not one privileged formalism.
* SKA uses Python, structured runtime objects, and explicit contracts as primary engineering media.
* SKA is intended to stay accessible to mixed teams of engineers and linguistically informed contributors.

So the correct theoretical stance is:

> SKA is **GF-compatible in spirit**, but not a pure GF system.

GF is best treated as:

* a powerful grammar-engineering tool,
* a strong realization backend for some constructions and languages,
* not the sole architectural center of the system.

---

### 4.2 Grammar Matrix and configurable grammar engineering

Broad-coverage grammar matrix projects usually separate:

* a cross-linguistic core,
* a structured parameter space,
* language-specific configurations and lexica.

This is one of the strongest analogies for SKA.

In SemantiK Architect:

* family engines act like reusable realization sketches,
* language cards and configs act like parameter sets,
* constructions act like reusable structural templates,
* lexical subsystems capture per-language and per-lexeme variation.

SKA is not a full HPSG-style grammar matrix and not a typed feature-structure workbench.
But it is aligned with the grammar-matrix idea in one important sense:

> many languages should be derivable from shared machinery plus structured variation.

That is one of the project’s central scaling ideas.

---

### 4.3 Construction Grammar

The closest linguistic affinity of the architecture is probably **construction grammar**.

Why:

* sentence patterns are treated as reusable units,
* constructions package structure and discourse choices together,
* the same semantic content can be realized via different constructions,
* reusable sentence logic lives in a construction inventory rather than in flat templates or individual lexemes.

Examples of constructional thinking in SKA include:

* equative and classificatory patterns,
* attributive copular patterns,
* locatives,
* existentials,
* possession structures,
* relative clauses,
* topic-comment structures,
* eventive clause patterns,
* biography-lead patterns as one construction family among many.

This matters theoretically because it means the system is not best described as:

* a lexicon plus morphology stack,
* a flat template engine,
* or raw semantic frames mapped directly to wording.

A better description is:

> **frame-informed constructional NLG**

Frames provide content and semantic roles.
Constructions decide how that content is packaged as a sentence.

---

### 4.4 Frame Semantics

Frame semantics is relevant because SKA assumes that structured semantic roles matter.

The architecture expects inputs that distinguish things like:

* actor / patient,
* possessor / possessed,
* theme / location,
* subject / predicate nominal,
* topic / focus,
* event / participant / circumstance.

That is close to the core intuition of frame semantics:

* meaning comes with participant structure,
* grammatical realization depends on that structure,
* multiple surface forms may express overlapping frame content.

However, SKA uses frame semantics in a practical engineering sense:

* roles are simplified,
* frame objects are designed for runtime use,
* internal structures need not mirror any published framebank exactly.

So the correct claim is:

> SKA is **compatible with frame semantics**, but not bound to a single external frame inventory.

---

### 4.5 AMR, UMR, Ninai, and other abstract notations

Abstract semantic notations matter because the architecture assumes:

* meaning can be represented before wording,
* input notation can evolve,
* realization should not be permanently tied to one external formalism.

That makes systems such as:

* Ninai,
* UMR,
* AMR-like graphs,
* Abstract Wikipedia internal semantic forms,

relevant upstream inputs.

Their correct place in SKA is **before planning**.

That means:

* external semantic notations should be normalized,
* planning should operate on normalized semantic content,
* realization should consume a sentence-level constructional plan rather than raw external notation.

The theoretical position is:

> input formalisms are replaceable;
> the constructional runtime architecture should remain stable.

That is a strong commitment to separation of concerns.

---

## 5. Internal abstractions and why they look like this

### 5.1 Family engines

A major design assumption is that many languages share **deep structural tendencies**.

Not perfectly, and not without exceptions, but enough to justify reusable family-level logic.

Examples include:

* analytic vs fusional vs agglutinative tendencies,
* case-heavy vs adposition-heavy marking,
* noun-class agreement,
* topic-prominent packaging,
* article systems,
* adjective placement patterns,
* possession strategies,
* relative clause strategies.

These families are partly genealogical, partly typological, and above all
**engineering abstractions**.

This is not a claim that every language in a family behaves the same.
It is a claim that:

> many realization decisions can be shared above the individual-language level.

That is essential for scale.

So family engines are theoretically justified as:

* a practical typological abstraction layer,
* a middle ground between universalism and per-language handcrafting,
* a reusable realization layer behind one construction runtime contract.

---

### 5.2 Constructions vs engines

This split is fundamental.

* **Constructions** decide what sentence configuration is needed.
* **Engines / realizers** decide how that configuration is expressed in a given language.

Constructions answer questions like:

* Is this an equative?
* Is this a classification?
* Is this an attributive copular clause?
* Is this a locative?
* Is this an existential?
* Is this a possession structure?
* Is this a topic-comment clause?
* Is this a bio-lead identity sentence?

Engines answer questions like:

* Is there an article?
* How is agreement marked?
* What is the default word order?
* How is possession expressed in this language?
* How are topic and focus surfaced?
* What morphology or function words are required?

Without this split, multilingual generation collapses into either:

* too much language-specific logic inside every construction,
* or too much semantic logic hidden inside realization backends.

So this separation is both:

* linguistically motivated,
* architecturally necessary.

---

### 5.3 Planning and discourse

The architecture also implies a planner/discourse layer.

This matters because sentence generation is not just:

* selecting words,
* inflecting them,
* placing them in order.

It also includes:

* deciding which construction to use,
* choosing canonical vs topic-prominent packaging,
* deciding which entity is discourse-prominent,
* deciding which role should be foregrounded,
* determining how the same semantic content should become a sentence.

This makes the system compatible with ideas from:

* information structure,
* discourse planning,
* centering-style approaches,
* microplanning in NLG.

The system does not need a full discourse theory to justify this.
Even a light planner already changes the architecture substantially.

The key theoretical point is:

> planning belongs between semantics and realization.

---

### 5.4 Slot mapping as an explicit layer

The architecture also benefits from making **slot mapping** explicit.

A construction is not just a label.
It expects semantically named inputs such as:

* `subject`
* `predicate_nominal`
* `predicate_adjective`
* `location`
* `agent`
* `patient`
* `theme`
* `topic`
* `comment`

This matters theoretically because it avoids collapsing:

* frame roles,
* construction roles,
* lexical items,
* backend arguments

into one undifferentiated structure.

Explicit slot mapping makes it clearer that:

* semantics provides role content,
* constructions define the packaging,
* realization consumes already-packaged inputs.

That is good both linguistically and architecturally.

---

### 5.5 Lexical resolution as a separate layer

The architecture also assumes that lexical choice and lexical normalization
must not be hidden inside whichever renderer happens to run.

This is theoretically important because:

* semantic content is not identical to lexical form,
* raw strings are not enough for high-quality multilingual realization,
* lexical provenance matters,
* lexical uncertainty matters,
* language-specific realization often depends on more than a label.

So lexical resolution is not just preprocessing.
It is a proper layer between construction planning and surface realization.

That makes the system more compatible with both:

* classical lexicalist insights,
* practical multilingual NLG requirements.

---

### 5.6 Realization backends as interchangeable surface technologies

Another important abstraction is that realization technology is not the same thing
as architecture.

SKA allows multiple backends, such as:

* family-oriented realizers,
* GF-based realizers,
* safe-mode fallback realization,
* future hybrid systems.

This means the system’s conceptual center cannot be any one backend.
The stable architectural object is the construction-level plan,
not the backend’s internal representation.

So the correct theoretical reading is:

> realization backends are interchangeable surface technologies operating over one shared construction runtime.

---

## 6. What this system is not

It is useful to state clearly what SemantiK Architect is **not** trying to be.

### 6.1 Not a pure template system

It can contain templates and reusable surface patterns,
but the intended architecture is richer than static string templating.

### 6.2 Not a pure semantic formalism

It is not trying to be a full logical language or graph formalism in itself.

### 6.3 Not a pure grammar formalism

It is not a GF clone, not an HPSG workbench, not an LFG implementation,
and not a single-formalism grammar laboratory.

### 6.4 Not an LLM-only generation stack

Learned components may become useful later,
but the architecture is fundamentally built around explicit structure,
traceability, and deterministic runtime behavior.

### 6.5 Not a biography-only system

Biography is one early domain and one useful test case.
It must not become the hidden architectural center.

This point is crucial.

### 6.6 Not a renderer-first architecture

No renderer should become the place where sentence meaning,
construction choice, and discourse packaging are secretly decided.

That would undo the central architectural separation.

---

## 7. Core theoretical tradeoffs

### 7.1 Expressiveness vs maintainability

The architecture deliberately avoids:

* maximal formal elegance,
* maximal notational purity,
* maximal linguistic detail everywhere.

Instead it chooses:

* explicit layers,
* typed-enough structures,
* configurable data,
* readable runtime code,
* testable constructions,
* debuggable contracts.

This is a standard engineering tradeoff:
less theoretical purity, more maintainable multilingual infrastructure.

---

### 7.2 Family-level generalization vs per-language accuracy

Family engines risk overgeneralization.

That risk is real.

But the alternative is also costly:
fully bespoke logic per language does not scale.

So the system adopts a pragmatic compromise:

* share what can be shared,
* isolate what must be language-specific,
* allow override points,
* keep capability tiering explicit.

The theory here is practical:
typological reuse is worth it if the override model is real.

---

### 7.3 Planner-first vs renderer-first architecture

This is one of the most important theoretical choices in the repository.

A renderer-first system tends to collapse:

* semantics,
* construction choice,
* lexical assumptions,
* and wording

into one backend.

A planner-first system keeps them apart.

SKA is more coherent when understood as planner-first.

That means:

* sentence structure should be selected before realization,
* renderers should realize plans, not invent them,
* no backend should become the semantic center of the system.

---

### 7.4 Generic runtime vs domain-specific shortcuts

There is always pressure in multilingual systems to special-case a successful early domain.
Biography is the obvious example.

Theoretical caution:

* domain-specific shortcuts are tempting,
* but when they become architecture, they distort the whole system.

So early domains should be treated as:

* motivating examples,
* coverage targets,
* not architectural masters.

---

### 7.5 Strong contracts vs implementation flexibility

The architecture benefits from strong shared contracts:

* normalized frames,
* `ConstructionPlan`,
* `slot_map`,
* lexical references,
* `SurfaceResult`.

At the same time, it needs implementation flexibility underneath those contracts.

This tradeoff is central:

* contracts should be stable enough to prevent architectural drift,
* implementations should be flexible enough to support multiple backends and gradual migration.

That combination is what allows both rigor and evolution.

---

## 8. Theoretical view of the target runtime

The most coherent theoretical reading of the intended system is:

### 8.1 Semantic layer

Represents content and role structure.

### 8.2 Normalization layer

Converts upstream payloads or notations into stable internal frame objects.

### 8.3 Frame-to-construction bridge

Maps normalized semantic content toward construction-oriented planning.

### 8.4 Planning layer

Selects information packaging, topic/focus behavior, and construction choice.

### 8.5 Construction layer

Defines reusable sentence patterns independent of any single language.

### 8.6 Slot-mapping layer

Assigns construction-specific semantic inputs into explicit realization slots.

### 8.7 Lexical resolution layer

Connects planned slots to lexical identities, lexical features, and provenance.

### 8.8 Realization layer

Implements family- and language-specific wording, morphology, and surface order.

### 8.9 Backend layer

Allows different realization technologies:

* GF,
* family engines,
* safe-mode fallback,
* future hybrid systems.

This layered reading best matches both:

* the design intent,
* the practical needs of a multilingual NLG system,
* the need to keep architecture stable while implementations evolve.

---

## 9. Future theoretical directions

This architecture can grow in several research-compatible directions.

### 9.1 Richer frame inventories

Expand beyond narrow early domains into broader semantic frame families.

### 9.2 Stronger construction inventories

Make construction classes, slot contracts, and construction capabilities more explicit and reusable.

### 9.3 Better discourse models

Add more principled topic, salience, anaphora, aggregation, and sentence-ordering models.

### 9.4 Stronger lexical semantics

Use richer lexical references, lexical typing, provenance tracking, and confidence-aware fallback.

### 9.5 Hybrid symbolic and learned systems

Use learned components for ranking, lexical choice, or variation,
while preserving explicit constructional planning and debuggable runtime structure.

### 9.6 Closer GF and grammar-engineering interoperability

Use GF where it is a strong backend, without turning the entire architecture into a single-formalism system.

### 9.7 Stronger contract-centered evaluation

Evaluate systems not only by output quality, but also by whether they preserve:

* construction identity,
* slot integrity,
* lexical traceability,
* fallback transparency,
* backend-independent semantics.

---

## 10. Summary

SemantiK Architect should be understood as:

* a **construction-centered multilingual NLG architecture**,
* informed by **GF**, **grammar matrix thinking**, **construction grammar**, **frame semantics**, and **abstract semantic formalisms**,
* implemented in a pragmatic, runtime-oriented way,
* with explicit separation between:

  * semantics,
  * normalization,
  * planning,
  * constructions,
  * slot mapping,
  * lexical resolution,
  * realization.

Its theoretical identity is therefore not:

* just templates,
* not just GF,
* not just semantic frames,
* not just language-family rules,

but rather:

> a practical multilingual NLG system whose central abstraction is the
> **planned constructional sentence**, expressed as a stable construction-level plan
> and realized through configurable, family-aware, backend-agnostic mechanisms.

These notes exist to make that theoretical identity explicit,
so the system can evolve without losing its conceptual center.
