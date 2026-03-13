# DESIGN_DECISIONS.md  
SemantiK Architect – Design Decisions

This document records the **key architectural choices** behind SemantiK Architect
and the alternatives that were considered. It is meant to be a concise “why we did it
this way” reference for reviewers and future contributors.

---

## 1. Overall System Shape

### Decision: Router → Family Engine → Constructions → Morphology → Lexicon

**What we do**

- The pipeline is:

  1. **Router** (`router.py`) chooses:
     - family engine,
     - language profile,
     - morphology config,
     - lexicon.
  2. **Semantics + Discourse** build a language-independent frame:
     - e.g. `BioFrame`, plus `DiscourseState`.
  3. **Constructions** choose a clause pattern for the frame.
  4. **Family Engine** realizes words + syntax using:
     - family matrix JSON,
     - language card JSON,
     - lexicon entries.
  5. **Morphology** handles inflection, agreement, phonology details.
  6. **Lexicon subsystem** provides lemma-level information and IDs.

**Alternatives considered**

1. **Per-language renderers** (one function per language, no shared engine)

   - Pros:
     - Simple to start with.
     - Easy to hack per-language behavior.
   - Cons:
     - Massive code duplication.
     - Hard to keep consistent across 100+ languages.
     - Any bug fix must be copied by hand many times.

2. **Single monolithic “universal” renderer**

   - Pros:
     - Centralized logic, no engine routing.
   - Cons:
     - Would quickly become unmaintainable.
     - Hard to reason about language-specific code paths.
     - Difficult for contributors to work in a huge file.

**Why we chose this**

- We want **maximum reuse** across languages with **clear modularity**.
- The pipeline matches how many NLG / grammar engineering systems are structured:
  - semantics → constructions → morphology/lexicon.
- It allows **family engines** to share heavy logic, while still giving languages a way to override via data.

---

## 2. Family Engines Instead of Language-Specific Engines

### Decision: ~15 family engines (Romance, Germanic, Slavic, Agglutinative, Bantu, etc.)

**What we do**

- Implement a small number of **family-level engines** in `engines/*.py`.
- Each engine is responsible for:
  - common morphosyntactic patterns for that family,
  - reading a shared family matrix JSON,
  - applying language-specific overrides via cards.

**Alternative**

- One engine per language (`engines/it.py`, `engines/es.py`, `engines/sw.py`, …).

**Why we chose this**

- Many languages share core behavior:
  - Romance: gender, articles, similar suffix morphology.
  - Slavic: case system, gendered past, similar declensional logic.
  - Bantu: noun class + concord across the clause.
- Factoring this at the family level:
  - **reduces code duplication**,
  - makes it easier to add new languages in that family,
  - encourages us to think in **typological terms** (which is how AW often reasons).
- Language-specific irregularities are encoded in:
  - JSON cards,
  - lexicon entries,
  - small overrides, not separate engines.

---

## 3. Constructions as a Separate Layer

### Decision: `constructions/*.py` are language-agnostic sentence patterns

**What we do**

- Constructions know about:
  - argument structure (subject, object, possessor, etc.),
  - information structure (topic/focus),
  - clause-level word order and connectors (copula, complementizers, etc.).
- They do **not** know how to inflect; they call the engine’s Morphology API.

**Alternative**

- Hard-code constructions inside each engine (or even each language).

**Why we chose this**

- Many constructions are cross-linguistic:
  - “X is a Y”, “X has Y”, “There is Y in X”, relative clauses, topic-comment.
- Having an explicit constructions layer:
  - Allows us to **reuse constructions** across families.
  - Makes the system easier to reason about for linguists (they can see “the set of constructions”).
  - Separates sentence patterns from morphophonology and low-level syntax.
- It also lines up well with:
  - **construction grammar** and **frame semantics** ideas,
  - where constructions are first-class objects.

---

## 4. Data-Driven Morphology and Configuration

### Decision: Morphology and configuration live in JSON matrices + cards

**What we do**

- Store morphosyntactic rules in JSON:

  - Family matrices in `data/morphology_configs/*.json`.
  - Per-language cards in `data/<family>/<lang>.json`.

- Engines read these and never hard-code suffixes, article maps, noun classes, etc., unless strictly necessary.

**Alternative**

- Store all morphology directly in Python code (if/else trees, hard-coded tables).

**Why we chose this**

- JSON is:
  - editable by non-programmers,
  - easier to version and diff for rules,
  - suitable for Wikifunctions / Z-data style representations.
- It enables the **“crowdsource the cards”** strategy:
  - A contributor can improve `ca.json` or `sw.json` without writing Python.
- It provides a clear path for:
  - exporting / importing configs to and from AW / Wikidata objects,
  - building UI tools for editing language behavior.

---

## 5. Separate Lexicon Subsystem

### Decision: Lexicon is its own package (`lexicon/*`) and data (`data/lexicon/*.json`)

**What we do**

- Lexicon functionality is not hidden in engines.
- We have:
  - `lexicon/types.py` – Lexeme and related structures,
  - `lexicon/loader.py`, `lexicon/index.py` – loading + indexing,
  - `lexicon/wikidata_bridge.py`, `lexicon/aw_lexeme_bridge.py` – integration with Wikidata/AW lexemes,
  - `data/lexicon/*.json` – actual lexicon files per language.

**Alternatives**

1. Lexicon integrated into engines (per-language dictionaries inside Python).
2. Use only Wikidata at runtime with no local lexicon.

**Why we chose this**

- Separating lexicon:
  - makes it reusable by **multiple engines and constructions**,
  - allows **large-scale** lexicon management (coverage reports, schemas),
  - makes integration with Wikidata lexemes explicit and testable.
- Local lexica:
  - avoid being strictly dependent on live network calls to Wikidata,
  - allow us to guarantee availability and performance,
  - can be built / refreshed offline from dumps.

---

## 6. Semantics and Discourse: Light but Real

### Decision: Minimal but explicit semantics (`semantics/*`) and discourse (`discourse/*`)

**What we do**

- Use small dataclasses like `BioFrame`, `Entity`, `Event`, `TimeSpan` for input.
- Maintain a `DiscourseState` for:
  - tracking mentioned entities,
  - salience and last mention,
  - topic selection.
- Provide modules for:
  - information structure (`discourse/info_structure.py`),
  - referring expressions (`discourse/referring_expression.py`),
  - simple discourse planning (`discourse/planner.py`).

**Alternative**

- Treat each sentence independently; no discourse model.
- Encode semantics as ad-hoc dicts with no consistent structure.

**Why we chose this**

- Multi-sentence texts (biography leads, short descriptions) **need** some discourse model:
  - pronouns vs full names,
  - topic markers vs canonical word order,
  - ordering of information.
- A fully formal semantic/discourse system (UMR, full AMR, etc.) would be heavy for the initial implementation.
- This “light but real” layer:
  - is enough to demonstrate **non-trivial discourse competence**,
  - stays simple enough for contributors to understand,
  - provides a bridge to more formal semantic inputs from AW.

---

## 7. Test-First and QA-Focused Design

### Decision: QA tools and test suites are first-class parts of the architecture

**What we do**

- `qa/test_runner.py` and `qa_tools/universal_test_runner.py` are the default way to validate engines.
- `qa_tools/test_suite_generator.py` helps create large CSV-based suites (often with LLM assistance).
- `qa_tools/lexicon_coverage_report.py` measures lexicon coverage against tests.
- Dedicated tests for lexicon loading and Wikidata bridges.

**Alternative**

- Rely primarily on manual testing and ad-hoc scripts.
- Only add tests at the very end, language by language.

**Why we chose this**

- Abstract Wikipedia needs **trustworthy** renderers:
  - changes can affect many languages at once.
- A structured QA pipeline:
  - catches regressions when modifying family matrices,
  - quantifies coverage and quality per language,
  - makes it easier to onboard new languages with confidence.
- CSV-based suites are:
  - easy to inspect,
  - easy to generate semi-automatically (e.g. via LLM prompts),
  - easy to extend by the community.

---

## 8. Implementation Language and Style

### Decision: Plain Python + JSON, with modest typing

**What we do**

- Use Python for:
  - engines, constructions, semantics, discourse, lexicon logic.
- Use JSON for:
  - morphology configs,
  - language cards,
  - lexicon files,
  - some datasets.
- Use simple type hints and dataclasses where helpful.

**Alternatives**

- A fully typed/compiled language (e.g. Haskell, OCaml, Rust).
- A DSL / custom language for grammars.

**Why we chose this**

- Python is:
  - accessible to many contributors,
  - already used in Wikimedia / AW-related tooling,
  - easy to prototype in and profile.
- JSON is:
  - compatible with Wikifunctions / Z-data style,
  - familiar to Wikimedia/MediaWiki ecosystem,
  - easy to manipulate from many languages and tools.

---

## 9. Scope and Non-Goals

### Explicit non-goals (for now)

- **Full coverage of all sentence types** in every language.
- **Complete semantic theory** or full alignment with any one formalism (UMR, AMR, Ninai).
- **Parsing**; the system is generation-focused.
- **End-to-end styling / register control**, beyond what basic discourse choices allow.

The design aims to:

- Solve the **architecture problem** for multilingual NLG in AW,
- Provide a serious, extensible base that can be:
  - critiqued,
  - improved,
  - specialized for particular language families.

---

## 10. Summary

The key design choices are:

- **Family engines** instead of per-language engines.
- A separate, **language-agnostic constructions layer**.
- **Data-driven morphology** via family matrices and language cards.
- A **distinct lexicon subsystem** integrated with Wikidata.
- A **light but explicit semantics + discourse layer**.
- A **test-first, QA-heavy** workflow.

Together, these choices are intended to make SemantiK Architect:

- scalable across many languages,
- understandable by both engineers and linguists,
- and robust enough for real-world Abstract Wikipedia use.
