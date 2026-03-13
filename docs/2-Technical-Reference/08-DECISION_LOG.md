# 📜 Decision Log & Architecture Records

**SemantiK Architect v2.0**

This document records the **key architectural choices** behind the SemantiK Architect and the alternatives that were considered. It is meant to be a concise "Why we did it this way" reference for reviewers and future contributors.

---

## 1. Overall System Shape

### Decision: Hexagonal Architecture (Ports & Adapters)

**The Context**
NLG systems can be built as monoliths or pipelines. We needed a structure that could handle 300+ languages and integrate with external AI agents and standards (Ninai, UD) without tight coupling.

**The Decision**
We adopted a **Hexagonal Architecture**:

1. **Core Domain:** Pure Python logic (`BioFrame`, `GrammarEngine`).
2. **Input Ports:** `NinaiAdapter` (JSON Trees) and `API` (HTTP).
3. **Output Ports:** `UDMapping` (CoNLL-U) and `TextRenderer`.
4. **Adapters:** Redis (State), GF Runtime (C-Bindings), Gemini (AI).

**Why we chose this**

* **Interoperability:** We can swap the input format from our internal JSON to the **Ninai Protocol** without touching the core linguistic logic.
* **Testing:** We can test the Core Domain without spinning up the C-runtime or Redis.

---

## 2. Input Protocol

### Decision: Adopting Ninai (Recursive Objects) vs. Flat JSON

**The Context**
v1.0 used a flat `BioFrame`. Abstract Wikipedia uses **Ninai**, a recursive LISP-like object structure (Constructors).

**The Decision**
We built the **Ninai Bridge (`app/adapters/ninai.py`)** to transform recursive Ninai objects into our flat internal frames, rather than rewriting the entire engine to work natively on trees.

**Why we chose this**

* **Standardization:** Allows SKA to function as a compliant renderer for the Abstract Wikipedia ecosystem.
* **Stability:** Keeps our internal domain logic simple (flat) while supporting complex external inputs (trees).

---

## 3. Tier 3 Linearization (The Factory)

### Decision: Weighted Topology (Udiron) vs. Hardcoded Templates

**The Context**
In v1.0, the "Factory" generated hardcoded `SVO` string concatenation. This produced grammatically incorrect output for SOV languages (Japanese) or VSO (Irish). Writing custom code for each was unscalable.

**The Decision**
We adopted **Weighted Topology Sorting** (adapted from the **Udiron** project). We assign relative integer weights to dependency roles (e.g., `subj=-10`, `obj=-5`, `verb=0` for SOV) and sort them at runtime.

**Why we chose this**

* **Zero-Code Config:** We can support *any* word order (OVS, VOS, etc.) just by editing `topology_weights.json`.
* **Simplicity:** The factory logic remains generic; only the weights change per language.

---

## 4. Evaluation Standard

### Decision: Construction-Time Tagging (UD) vs. Post-Hoc Parsing

**The Context**
To prove our output is "good," we need to evaluate it. Running a 3rd-party dependency parser on our output is slow and error-prone (parsing is guessing).

**The Decision**
We implemented **Construction-Time Tagging**. Since we *build* the sentence using specific functions (`mkCl`, `mkNP`), we know exactly what is a Subject and what is an Object. We map these intents directly to **Universal Dependencies (CoNLL-U)** tags.

**Why we chose this**

* **Accuracy:** 100% accurate tagging because it is based on the generator's intent, not a parser's guess.
* **Speed:** Zero runtime overhead compared to loading a Neural Parser.

---

## 5. State Management

### Decision: Redis Session Store vs. Stateless Requests

**The Context**
Generating isolated sentences leads to repetition ("Marie Curie is X. Marie Curie is Y."). We needed to implement **Pronominalization** (using "She").

**The Decision**
We introduced **Redis** to store a `SessionContext` (ID + History). The **Discourse Planner** checks this context to decide whether to render a Name or a Pronoun.

**Why we chose this**

* **Performance:** Redis is sub-millisecond, essential for a real-time NLG API.
* **Decoupling:** The renderer doesn't need to know *why* it's rendering "She," just that the context dictates it.

---

## 6. The "Everything Matrix" (Data-Driven Build)

### Decision: Dynamic System Scanning vs. Static Config

**The Context**
Hardcoding `LANGS = ['eng', 'fra']` leads to configuration drift.

**The Decision**
We built the **Everything Matrix**, a dynamic registry populated by scanning the filesystem before every build.

**Why we chose this**

* **Truth:** The build system never lies. If the file isn't on disk, the Matrix marks it `BROKEN`.
* **Automation:** Adding a language is as simple as adding the files; the scanner auto-registers it.

---

## 7. AI Services Integration

### Decision: "The Architect" & "The Judge" Agents

**The Context**

* **Problem A:** Writing grammar files for 300 languages is too much work.
* **Problem B:** We can't manually verify quality for 300 languages.

**The Decision**
We integrated specialized AI Agents:

* **The Architect:** Generates the `.gf` code for Tier 3 languages using the **Frozen System Prompt**.
* **The Judge:** Validates output against **Gold Standard** data and auto-files GitHub issues.

**Why we chose this**

* **Scale:** AI acts as a force multiplier, writing code and checking quality faster than humans.
* **Consistency:** The System Prompt ensures the AI writes deterministic GF code, not chatty markdown.

---

## 8. Summary

The key design choices defining v2.0 are:

1. **Hexagonal Architecture:** For Ninai/UD interoperability.
2. **Weighted Topology:** For solving the "Word Order" problem without code.
3. **Redis Context:** For Discourse Planning (Pronouns).
4. **Hybrid Factory:** Combining RGL (Expert) and AI Architect (Automated).
5. **Construction-Time Tagging:** For reliable evaluation.

Together, these choices create a system that is **scalable (300+ languages), interoperable (Standard Protocols), and autonomous (AI-Driven)**.