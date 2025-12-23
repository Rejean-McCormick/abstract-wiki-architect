
# 🎓 Linguistics Reference & Theory

**Abstract Wiki Architect**

## 1. Purpose & Positioning

This document explains **why** the system is built the way it is. It maps the engineering components (Engines, Matrices, JSON) to their corresponding concepts in linguistic theory.

The Abstract Wiki Architect is designed to be:

* **Engineered for Scale:** Capable of supporting 300+ languages through automation and hierarchy.
* **Theory-Aware:** Informed by research-grade formalisms to ensure it can handle the complexity of natural language, not just simple template filling.

### High-Level Analogy

The system sits at the intersection of three traditions:

1. **Grammatical Framework (GF):** We adopt the separation of *Abstract Syntax* (Logic) and *Concrete Syntax* (Strings).
2. **Grammar Matrix:** We use typological hierarchies (Language Families) to share code.
3. **Frame Semantics:** We use semantic frames (`BioFrame`) as the atomic unit of meaning, rather than raw syntax trees.

---

## 2. Theoretical Foundations

### 2.1 Grammatical Framework (GF)

The system uses GF as its low-level runtime engine but wraps it in a Pythonic architecture.

* **Abstract Syntax:** In our system, this is represented by the **Semantic Frame** (e.g., `BioFrame`). It defines *what* can be said (Subject, Profession, Nationality) without defining *how* it is said.
* **Concrete Syntax:** In our system, this is split between the **RGL (Resource Grammar Library)** for Tier 1 languages and the **Factory (Generated)** for Tier 3.

**Key Difference:**
We do not force developers to write full GF code for every language. Instead, we use **JSON Configurations** (`data/morphology_configs/`) to parameterize the concrete syntax, making the system accessible to non-linguists.

### 2.2 Construction Grammar (CxG)

We explicitly model **Constructions**—pairings of form and meaning—rather than just abstract syntax rules.

* **The Construction Layer:** Located in the `app/core/domain/` logic.
* **Role:** It maps a Semantic Frame to a syntactic template.
* *Example:* The **"Equative Construction"** (`X is Y`) is a shared pattern used by the `BioFrame`.
* *Realization:* The engine knows that in Russian, the Equative Construction in the present tense often omits the copula ("Ivan — doctor"), whereas in English it requires "is".



### 2.3 Typology & Language Families

We reject the idea of writing a unique engine for every language. Instead, we use **Typological Inheritance**.

* **Family Engines:** We group languages not just by genetics (Romance, Germanic) but by structural properties (Typology).
* **The Romance Matrix:** Handles gender agreement (Noun-Adj), pluralization, and article selection.
* **The Agglutinative Matrix:** Handles vowel harmony (Front/Back vowels) and suffix chaining (Root + Plural + Case + Possessive).
* **The Isolating Matrix:** Handles rigid word order and lack of inflection (e.g., for certain Pidgin or Creole implementations).



This approach reduces code duplication by ~90%. If we fix a bug in the "Romance Adjective Agreement" logic, it fixes Portuguese, Spanish, French, and Romanian simultaneously.

---

## 3. Internal Abstractions

### 3.1 The "Everything Matrix" as a Typological Database

The `everything_matrix.json` is not just a build config; it is a **Typological Registry**.

* **Zone A (Grammar):** Encodes the structural capability of the language (e.g., "Does it have a Noun module?").
* **Zone B (Lexicon):** Encodes the semantic coverage.

### 3.2 Semantics vs. Discourse

We distinguish between the meaning of a sentence and its presentation in context.

* **Semantic Frame:** The `BioFrame` contains the raw facts: `Name="Marie Curie", Prof="Physicist"`.
* **Discourse State:** (Future Roadmap) Tracks information structure (Topic vs. Focus).
* *First Mention:* "Marie Curie is a physicist."
* *Second Mention:* "She was born in Poland." (Pronominalization).



Currently, the system focuses on **Sentence-Level Generation**, but the architecture leaves room for a **Discourse Planner** to manage multi-sentence coherence.

---

## 4. Design Trade-offs

### 4.1 Expressiveness vs. Maintainability

* **The Choice:** We prioritize **Maintainability**.
* **The Cost:** We do not implement a "Perfect" grammar for every language. We accept "Good Enough" (Tier 3 / Factory) to ensure coverage.
* **Rationale:** A Wikipedia that covers 300 languages with 90% accuracy is more valuable than one that covers 20 languages with 100% accuracy.

### 4.2 JSON vs. Code

* **The Choice:** We push as much logic as possible into **JSON Configuration**.
* **The Benefit:** This allows "Crowdsourcing the Cards." A contributor can add support for Catalan by copying `spa.json` to `cat.json` and tweaking the article rules, without touching the Python engine.

### 4.3 NLG-First

* **The Choice:** The system is strictly **Generation-First** (NLG), not Parsing-First (NLU).
* **Implication:** We do not need to worry about ambiguity. We know exactly what the input means because it comes as structured JSON. This simplifies the grammar significantly compared to a translation system.

---

## 5. Future Theoretical Directions

The architecture is built to support future research-grade extensions:

1. **UMR / Ninai Integration:** The Semantic Frames are designed to map cleanly to **Uniform Meaning Representation (UMR)** or Abstract Wikipedia's **Ninai** notation.
2. **Learned Micro-Planning:** While the macro-structure is rule-based, we can inject ML models to handle "Micro-Planning" (e.g., choosing between synonyms based on style).
3. **Cross-Linguistic QA:** Using the "Judge" agent to perform massive contrastive analysis (e.g., "Does the generated text in Zulu match the semantic intent of the English text?").

---

## 6. Summary

* **We separate Semantics (Frames) from Syntax (GF).**
* **We share logic via Language Families (Matrices).**
* **We prioritize Coverage via the Hybrid Factory.**
* **We treat Linguistics as Data (JSON), not Code.**

This document confirms that the Abstract Wiki Architect is not just a script, but a conscious engineering interpretation of long-standing ideas in formal and computational linguistics.