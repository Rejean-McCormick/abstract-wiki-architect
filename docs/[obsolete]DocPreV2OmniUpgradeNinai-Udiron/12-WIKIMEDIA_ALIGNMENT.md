# 🌐 Abstract Wikipedia Alignment & Standards

**Abstract Wiki Architect**

This document defines how the **Abstract Wiki Architect (AWA)** aligns with, diverges from, and integrates with the official technical standards of the **Abstract Wikipedia** project (Wikifunctions, Ninai, and Universal Dependencies).

---

## 1. The Core Divergence: GF vs. Universal Dependencies

The comment from the community correctly identifies that Wikidata often relies on **Universal Dependencies (UD)** for linguistic modeling. AWA, however, is built on the **Grammatical Framework (GF)**.

### Why we chose GF (The RGL Advantage)
* **Generation First:** UD is primarily a *dependency* formalism designed for *parsing* (analyzing text). GF is a *constructive* formalism designed for *linearization* (generating text).
* **The RGL:** The **Resource Grammar Library** provides us with 40+ languages where morphology (inflection) and syntax (word order) are *already solved*. To achieve the same in a UD-based system (like Udiron) often requires training statistical models or writing extensive manual linearizers.
* **Determinism:** GF guarantees that if the abstract tree is valid, the output text is grammatical. This aligns with the "Verifiable correctness" goal of Abstract Wikipedia.

### Our UD Strategy
We acknowledge UD as a standard.
* **Future Interop:** We can implement a "UD Exporter" that converts our internal GF trees into CoNLL-U format for evaluation against UD treebanks.

---

## 2. Ninai & The Semantic Frame

**Ninai** is an experimental abstract notation for constructors in Abstract Wikipedia.
* *Ninai Example:* `(cons "and" "Q1" "Q2")`

AWA uses **Semantic Frames** (Python Dataclasses) as its internal abstract representation.
* *AWA Example:* `{"frame": "bio", "name": "Q1", "prof": "Q2"}`

### The Bridge
AWA is designed to be a **Renderer Implementation** for Ninai.
1.  **Input:** AWA accepts a high-level intent.
2.  **Mapping:** A simple adapter layer can convert Ninai S-expressions into AWA `BioFrames`.
3.  **Output:** AWA returns the text.

We view Ninai as the *wire format* (how data is sent) and AWA as the *execution engine* (how data is processed).

---

## 3. Z-Object Integration (Wikifunctions)

In the Wikifunctions ecosystem, functions and types are assigned **Z-IDs** (e.g., `Z100` for a function).

### Current Mapping
AWA's architecture is "Z-Ready" by design:

| AWA Component | Wikifunctions Equivalent | Mapping Strategy |
| :--- | :--- | :--- |
| **Family Engine** (`RomanceEngine`) | **Z-Implementation** | The Python code can be wrapped as a Z-Function implementation. |
| **Lexicon Entry** (`people.json`) | **Z-Object (Type)** | Words can be mapped to Z-IDs (e.g., `physicist` -> `Z_Physicist`). |
| **Matrix Config** (`por.json`) | **Z-Configuration** | The JSON config can be stored as a Z-Object. |

### Immediate Roadmap
We treat **Wikidata QIDs** (e.g., `Q42`) as the source of truth for entity grounding, which is fully compatible with the current state of Wikifunctions.

---

## 4. Addressing "Vibe-Coding" (Rigorous Engineering)

To ensure this project is not seen as "vibe-coded" (improvisational), we enforce:
1.  **Hexagonal Architecture:** Strict isolation of domain logic.
2.  **Everything Matrix:** Auditable, data-driven build system.
3.  **Two-Phase Compilation:** Solving the PGF linking bug deterministically.
4.  **Unit Testing:** `test_gf_dynamic.py` ensures regression testing across all 50+ languages.

We invite the community to review `docs/01-ENGINE_ARCHITECTURE.md` for a deep dive into these engineering standards.