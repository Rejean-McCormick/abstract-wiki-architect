# Grammar

The **Grammar** layer is the rule system that turns structured meaning into **well-formed text** in a target language.

In SemantiK Architect, “grammar” covers two things:
- **Morphology** (inflection): how words change form (agreement, conjugation, declension).
- **Syntax** (structure + word order): how parts combine into phrases/clauses and how they are ordered.

This is the “rules” layer of the overall architecture: it defines morphology and syntax/word order, and it supports a **hybrid** approach that balances quality and coverage.

---

## Why this layer exists

SemantiK Architect aims for:
- **Determinism** (same input → same output),
- **Broad language coverage** (including the long tail),
- **Reasonable grammatical quality** even when a language lacks a full expert grammar.

The grammar layer is where those tradeoffs are managed: high precision when strong resources exist, and graceful degradation when they don’t.

---

## The hybrid strategy (tiers)

SemantiK Architect uses a tiered approach to grammar resources:

- **Tier 1 (High Road): expert grammars**
  For high-resource languages, use expert-grade grammar resources (GF/RGL-class) for richer morphology and more precise sentence realization.

- **Tier 2: manual / curated overrides**
  When a community or project-maintained grammar exists, it can override both Tier 1 and Tier 3 for that language to improve naturalness and correctness.

- **Tier 3 (Factory): weighted-topology fallback**
  For under-resourced languages, use a configuration-driven fallback based on **weighted topology / dependency-role ordering**. This exists to avoid “missing language” dead ends and ensure the system can still produce a grammatical-enough sentence.

See also: [[Language Coverage Strategy (Tiers)|Language-Coverage-Strategy-Tiers]]

---

## Grammar matrices and language cards

To scale efficiently, grammar knowledge is organized at two levels:

- **Family grammar matrices**
  Reusable defaults shared across related languages (e.g., Romance, Slavic). They capture broad paradigm space and common patterns.

- **Language cards**
  Language-specific overrides for quirks that shouldn’t live in the shared family matrix (e.g., special elision or clitic behavior).

This keeps the system modular: broad coverage from shared structure, with targeted exceptions where needed.

---

## Relationship to other layers

- **Lexicon → Grammar**
  The lexicon supplies lemmas and features (e.g., gender/number) that the grammar needs to inflect and agree.  
  See: [[Lexicon]]

- **Grammar → Renderer**
  The renderer selects a grammar strategy (tier) and uses it to realize a sentence plan into text.  
  See: [[Renderer]]

- **Context ↔ Grammar**
  Context can change *what* gets expressed (e.g., pronoun vs name); grammar ensures the chosen form fits correctly in the sentence.  
  See: [[Context]]

---

## What this page is (and is not)

This page explains what “Grammar” means in SemantiK Architect and how it supports coverage and quality.

It is **not** a build guide or an API reference.
- Setup/build: [[Setup]]
- API surface: [[API Overview|API-Overview]]