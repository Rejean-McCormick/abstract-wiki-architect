# SemantiK Architect

SemantiK Architect is an **independent multilingual text renderer**: it turns **structured meaning** into **encyclopedic natural language**, with a focus on scaling to the **long tail** of languages (including under-resourced ones).

> Note: SemantiK Architect is **not affiliated with WMF / Abstract Wikipedia** and is **not developed in collaboration** with the Abstract Wiki team. It is the continuation/rename of “Abstract Wiki Architect” as an independent project.

---

## What it does

SemantiK Architect:
- **Accepts meaning** in a structured form (e.g., *Frames* or *Ninai-style* recursive objects).
- **Generates text** in a target language.
- Optionally **exports a linguistic view** (e.g., Universal Dependencies / CoNLL-U) to support validation and evaluation.

---

## How it works (conceptual)

At a high level, the system is organized into four conceptual parts:

- **Lexicon** — vocabulary (words + properties), grounded to stable identifiers when possible.
- **Grammar** — rules for inflection and word order.
- **Renderer** — turns the input meaning into a sentence plan and realizes it as text.
- **Context** — tracks discourse state across sentences (e.g., reference, focus, pronouns).

To scale language coverage, SemantiK Architect uses a **tiered strategy**:
- **Tier 1**: highest-quality grammars where available (e.g., GF/RGL-class resources).
- **Tier 2**: curated/manual improvements and overrides.
- **Tier 3**: automated “factory” grammars (e.g., topology/word-order driven), inspired by UD/Udiron-style approaches, to avoid missing-language dead ends.

---

## Where it stands vs related tools

- **Ninai**: a meaning representation / protocol. SemantiK Architect is a **renderer** that can consume it.
- **GF**: a grammar technology. SemantiK Architect **uses/hosts** grammars as part of a larger end-to-end renderer.
- **Udiron-style topology**: a strategy for rapid scaling via word-order/topology configuration; used as a **coverage path**.
- **UD (Universal Dependencies)**: a cross-linguistic interface useful for **evaluation and verification** (not a replacement for generation).

See: [[Positioning: Ninai, Udiron, GF, UD (No WMF/AW Affiliation)|Positioning-Ninai-Udiron-GF-UD-No-WMF-AW-Affiliation]]

---

## How to read this wiki

Recommended order:
1. [[What SemantiK Architect Is|What-SemantiK-Architect-Is]]
2. [[Positioning: Ninai, Udiron, GF, UD (No WMF/AW Affiliation)|Positioning-Ninai-Udiron-GF-UD-No-WMF-AW-Affiliation]]
3. [[Conceptual Flow: Meaning → Text|Conceptual-Flow-Meaning-to-Text]]
4. Components: [[Lexicon]] → [[Grammar]] → [[Renderer]] → [[Context]]
5. [[Language Coverage Strategy (Tiers)|Language-Coverage-Strategy-Tiers]]
6. [[Correctness & Verifiability (Gold Standards, UD Export, Judge)|Correctness-and-Verifiability-Gold-Standards-UD-Export-Judge]]
7. Using pages: [[Inputs: Frames|Inputs-Frames]] / [[Inputs: Ninai|Inputs-Ninai]] / [[Outputs: Text|Outputs-Text]] / [[Outputs: UD|Outputs-UD]]

Project pages:
- [[Roadmap]], [[Changelog]], [[Decisions]], [[Glossary]]

---

## What this wiki is (and is not)

- **This wiki is** a high-level explanation of what SemantiK Architect is, how it fits in its ecosystem, and how the main concepts connect.
- **This wiki is not** a full technical manual (setup scripts, build internals, exhaustive API reference). Those belong in minimal “Developer Notes” pages and/or repository docs.

If you’re here to implement or integrate quickly, start at: [[API Overview|API-Overview]] and [[Repo Map|Repo-Map]].