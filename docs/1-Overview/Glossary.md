# Glossary (SemantiK Architect)

> **Naming note:** *SemantiK Architect* is the current name of the project (formerly **Abstract Wiki Architect** in earlier docs and some filenames).
>
> **Independence note:** SemantiK Architect is **not affiliated with** or developed in collaboration with **WMF / Abstract Wikipedia / Abstract Wiki**.

---

## Project + related tools (boundaries)

- **SemantiK Architect**: A multilingual **renderer** that turns structured meaning into readable natural-language text, designed to scale across high-resource and long-tail languages.
- **Abstract Wiki Architect (legacy name)**: Former project name that may still appear in v2 docs, historical notes, and some repo artifacts.
- **GF (Grammatical Framework)**: A grammar formalism/toolchain used (where available) to define and run high-quality grammars.
- **RGL (Resource Grammar Library)**: GF’s standard library for morphology/syntax in a set of languages; often the basis of the “high-quality” path when applicable.
- **UD (Universal Dependencies)**: A dependency-grammar standard used here mainly as a **validation/evaluation view** (often via CoNLL-U export).
- **Ninai (meaning representation)**: A recursive, constructor-tree style meaning representation that SemantiK Architect can accept (typically via an adapter/bridge).
- **Udiron / weighted-topology approach**: A coverage-oriented strategy that uses configurable ordering/topology rules to scale to many languages when full expert grammars are not available.

---

## Meaning representations (inputs)

- **Semantic Frame (Frame)**: A language-agnostic, usually flat JSON object expressing intent (e.g., “bio”, “event”) meant to be stable and easy to validate.
- **BioFrame / EventFrame**: Concrete frame “shapes” (types) used by the strict/production input path.
- **Recursive meaning tree**: A nested, tree-shaped input form (often Ninai-style) used for richer meaning composition and prototyping.
- **Adapter / Bridge**: A component that converts an external meaning format (e.g., Ninai-style trees) into the renderer’s internal representation.

---

## Core generation concepts

- **Lexicon**: Vocabulary entries (words/lemmas + properties) used during realization.
- **Grammar**: Rules that handle morphology (inflection) and syntax/word order.
- **Renderer**: The “assembly” layer that maps meaning to a sentence plan and realizes it into output text (and optional validation views).
- **Context**: Discourse/session state used to keep multi-sentence generation coherent (e.g., reference, repetition, pronouns). Implementation details may vary.

---

## GF / linguistics terms (only when relevant)

- **Abstract syntax**: Language-independent structures defining *what* can be expressed.
- **Concrete syntax**: Language-specific rules defining *how* to express it in a given language.
- **Linearization**: Turning an abstract structure/tree into a final surface string.
- **Morphology**: Word-level inflection (plural, tense, case, agreement, etc.).

---

## Language coverage strategy

- **Tier 1 (High quality)**: Uses strong, mature grammar resources (often GF/RGL-class) for best grammatical correctness.
- **Tier 2 (Manual overrides)**: Targeted language-specific improvements/overrides layered on top of other tiers.
- **Tier 3 (Factory / Safe Mode)**: Coverage-first grammars driven by configurable topology/ordering so a language is available quickly, even if nuance is limited.
- **Weighted topology**: A Tier 3 mechanism that uses configurable weights/rules to decide ordering (e.g., SVO/SOV tendencies) rather than hardcoded templates.

---

## Build/runtime and configuration terms

- **Everything Matrix**: A computed registry of what exists per language (assets, maturity signals, runnable status) used to avoid hardcoded language lists.
- **Two-phase build (concept)**: A build strategy that verifies components first and then links/aggregates them, to avoid partial overwrites and “last one wins” behavior.
- **PGF (Portable Grammar Format)**: The compiled GF artifact loaded at runtime. Filenames may still include legacy naming in some repos.

---

## Outputs + evaluation

- **Text output**: The default natural-language surface string.
- **CoNLL-U output**: Optional export of a UD-style dependency representation for validation/evaluation.
- **Gold Standard**: A curated set of reference examples used to track quality over time.
- **Judge**: An automated evaluator that compares output against Gold Standard data and flags regressions (optionally integrated with CI and issue tracking, depending on setup).

---

## Data organization

- **Domain sharding**: Splitting vocabulary into topic-focused files (e.g., `core`, `people`, `science`) so systems can load what they need.
- **Wikidata QID mapping**: Grounding lexicon entries to stable identifiers when available, to keep meaning aligned across languages.

---

## Software architecture terms (lightweight)

- **Ports & adapters (hexagonal architecture)**: A structuring approach that separates core generation logic from infrastructure (APIs, storage, tooling).

---

## Automation / agent terms (status may vary)

- **Automation agent (e.g., “Architect”, “Surgeon”)**: Names used for optional tooling intended to assist with authoring/repairing data or grammars. These are **not required** for the core deterministic generation path, and whether they are active depends on the project’s current workflow.
- **Frozen system prompt**: A fixed prompt template concept used to keep automated outputs consistent when agents are used.