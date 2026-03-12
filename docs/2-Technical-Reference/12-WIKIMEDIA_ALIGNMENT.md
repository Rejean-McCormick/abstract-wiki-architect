
# 🌐 Abstract Wikipedia Alignment & Standards

**SemantiK Architect v2.0**

This document defines how the **SemantiK Architect (SKA)** aligns with, diverges from, and integrates with the official technical standards of the **Abstract Wikipedia** project (Wikifunctions, Ninai, and Universal Dependencies).

---

## 1. The Core Divergence: Hybrid Linearization (GF + UD)

The original Abstract Wikipedia architecture often relies heavily on **Universal Dependencies (UD)** for linguistic modeling (as seen in the `Udiron` project). SKA v1.0 was purely **Grammatical Framework (GF)** based.

In **v2.0**, we have bridged this gap by adopting a **Hybrid Linearization Strategy**.

### 1.1 Tier 1: Generative Grammar (GF RGL)

For high-resource languages (English, French, Hindi), we use the **GF Resource Grammar Library**.

* **Why:** It handles complex morphology (case declension, gender agreement) perfectly using valid Abstract Syntax Trees.
* **Alignment:** This provides the "Verifiable Correctness" required by the platform.

### 1.2 Tier 3: Weighted Topology (Udiron Integration)

For under-resourced languages (Zulu, Hausa), we have integrated the **Weighted Topology** approach from the `Udiron` codebase.

* **Why:** Writing full generative grammars for 300 languages is too slow.
* **Mechanism:** We use `data/config/topology_weights.json` to define relative weights for dependency roles (e.g., `subj=-10`, `obj=-5`, `root=0` for SOV).
* **Alignment:** This aligns SKA's "Factory" tier directly with the community's preferred method for rapid language expansion.

### 1.3 Evaluation: Universal Dependencies Export

We acknowledge UD as the gold standard for *evaluation*.

* **Feature:** SKA v2.0 supports `Accept: text/x-conllu`.
* **Logic:** We implement **"Construction-Time Tagging."** Since we generate the sentence, we know exactly which word is the Subject. We map our internal RGL functions (`mkCl`) to UD tags (`nsubj`, `root`) using the **Frozen Ledger** mapping.
* **Result:** SKA output can be validated against standard UD treebanks.

---

## 2. Ninai Protocol Integration

**Ninai** is the abstract notation used by Abstract Wikipedia to represent meaning.

* *Legacy Assumption:* LISP-like S-expressions.
* *Code Reality:* Recursive JSON Object Trees (Constructors).

### 2.1 The Bridge (`NinaiAdapter`)

SKA is designed to be a native **Renderer Implementation** for Ninai.

* **Input:** We accept the recursive JSON structure natively.
* **Mapping:** The `app/adapters/ninai.py` module recursively walks the Ninai tree and flattens it into SKA's internal `BioFrame` or `EventFrame`.

### 2.2 Constructor Mapping

We map Ninai constructors to SKA logic:

| Ninai Constructor | SKA Component |
| --- | --- |
| `ninai.constructors.Statement` | `BioFrame` (Root Intent) |
| `ninai.constructors.List` | Recursive Flattening Logic |
| `ninai.constructors.Entity` | `DiscourseEntity` (QID Lookup) |
| `ninai.types.Bio` | `frame_type="bio"` |

We view Ninai as the *wire format* (Z7) and SKA as the *execution engine* (Z1).

---

## 3. Z-Object Integration (Wikifunctions)

In the Wikifunctions ecosystem, functions and types are assigned **Z-IDs**. SKA's architecture is "Z-Ready" by design.

### 3.1 Component Mapping

| SKA Component | Wikifunctions Concept | Integration Strategy |
| --- | --- | --- |
| **Family Engine** (`RomanceEngine`) | **Z-Implementation** | Python code wrapped as a Z-Function. |
| **Lexicon Entry** (`people.json`) | **Z-Object (Type)** | Mapped to `Z_Physicist` or Wikidata QIDs. |
| **Matrix Config** (`por.json`) | **Z-Configuration** | Stored as a JSON Z-Object. |
| **The Architect Agent** | **Z-Bot** | An automated contributor bot. |

### 3.2 Entity Grounding

We utilize **Wikidata QIDs** (e.g., `Q42`) as the source of truth. The `NinaiAdapter` expects these QIDs in the `Entity` constructor arguments.

---

## 4. Discourse & Coherence

Abstract Wikipedia aims to generate **Articles**, not just sentences. SKA v2.0 addresses this via the **Discourse Planner**.

### 4.1 Centering Theory

We implement a simplified version of Centering Theory to handle **Pronominalization**.

* **Standard:** If an entity is the "Backward-Looking Center" () of the previous utterance, it should be pronominalized.
* **Implementation:** The `SessionContext` in Redis tracks the current focus. If the incoming Ninai frame references the same QID, SKA renders "She/He" instead of the name.

---

## 5. Addressing "Vibe-Coding" (Rigorous Engineering)

To ensure this project is robust enough for the Wikimedia ecosystem, we enforce:

1. **Hexagonal Architecture:** Strict isolation of domain logic from the Ninai/UD adapters.
2. **Gold Standard QA:** We ingest the `Udiron` test suite (`tests.json`) to validate our outputs against community-verified strings.
3. **Two-Phase Compilation:** Solving the PGF linking bug deterministically.
4. **Self-Healing CI/CD:** The **Surgeon** and **Architect** agents automatically repair broken grammars, ensuring the build pipeline is resilient.

We invite the community to review `docs/01-ENGINE_ARCHITECTURE.md` for a deep dive into these engineering standards.