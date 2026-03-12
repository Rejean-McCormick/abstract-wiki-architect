# Positioning: Ninai, Udiron, GF, UD (No WMF/AW Affiliation)

SemantiK Architect (formerly “Abstract Wiki Architect”) is an **independent project**. It is **not affiliated with WMF / Abstract Wiki**, and does not imply collaboration or endorsement.

## The short version (one paragraph)

SemantiK Architect is a **renderer platform**: it takes a **language-independent meaning representation** and produces **encyclopedic text** across many languages, optimizing for the “long tail” (high coverage) while staying **deterministic** and **verifiable**.

## Who does what (clear boundaries)

### Ninai — meaning (input standard)

* **Role:** A language-independent way to express meaning as constructor trees (“what you want to say”).
* **What it’s not:** It does not decide word order, morphology, or surface realization.
* **Relationship to SemantiK Architect:** SemantiK Architect can **consume Ninai-style object trees** as an input path.

### GF — high-quality grammar (best-case realization)

* **Role:** A rule-based grammar system (abstract syntax → concrete syntax) that can produce high-quality text where strong grammars exist.
* **What it’s not:** It is not a full product platform (language selection policy, lexicon lifecycle, QA strategy, discourse memory).
* **Relationship to SemantiK Architect:** SemantiK Architect uses GF as a **Tier-1 “high road”** option where available, inside a broader system that must still cover under-resourced languages.

### Udiron — topology/ordering approach (coverage accelerator)

* **Role (in this doc set):** A dependency/topology-inspired approach to **linearize** constituents via configurable ordering (weights), used to scale faster than hand-writing full grammars.
* **What it’s not:** It is not a complete end-to-end renderer stack (lexicon + tiering + API + context + QA).
* **Relationship to SemantiK Architect:** SemantiK Architect adapts a **weighted topology** strategy as the coverage fallback (Tier-3).

### UD (Universal Dependencies) — evaluation/interchange surface (validation)

* **Role:** A standard way to represent dependency structure, useful for **evaluation** and interoperability.
* **What it’s not:** UD is not a generator; it does not produce text by itself.
* **Relationship to SemantiK Architect:** SemantiK Architect can **export UD/CoNLL-U** as an output format to make correctness/analysis measurable and comparable.

## What SemantiK Architect adds (the “product layer” the others don’t)

SemantiK Architect’s unique responsibility is the **end-to-end orchestration** from meaning → text at scale:

* **Hybrid realization strategy:** chooses between high-quality grammars and coverage fallbacks (tiered approach).
* **Lexicon + grounding:** manages vocabulary as a first-class system (including grounding to identifiers such as Wikidata QIDs in the current docs).
* **Discourse/context memory:** supports multi-sentence coherence (e.g., pronouns) as a core capability.
* **Quality workflow:** explicit “gold standard / judge” style validation mindset (beyond “it compiles”).

## Mental model (one line)

**Ninai says what you mean → SemantiK Architect decides how to realize it → GF (when strong) or topology (when needed) produces the sentence → UD export helps verify what was produced.**
