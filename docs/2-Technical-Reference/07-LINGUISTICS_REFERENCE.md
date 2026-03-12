# 🎓 Linguistics Reference & Theory

**SemantiK Architect v2.0**

## 1. Purpose & Positioning

This document explains **why** the system is built the way it is. It maps the engineering components (Engines, Matrices, JSON) to their corresponding concepts in linguistic theory.

The SemantiK Architect v2.0 is designed to be:

* **Engineered for Scale:** Capable of supporting 300+ languages through automation.
* **Interoperable:** Native support for the **Ninai** protocol and **Universal Dependencies (UD)** standards.
* **Theory-Aware:** Informed by research-grade formalisms to ensure it can handle the complexity of natural language.

### High-Level Analogy

The system sits at the intersection of four traditions:

1. **Grammatical Framework (GF):** Separation of *Abstract Syntax* (Logic) and *Concrete Syntax* (Strings).
2. **Dependency Grammar:** We use "Weighted Topology" (Udiron) to linearize text based on head-dependent relationships.
3. **Frame Semantics:** We use **Ninai Constructors** as the atomic unit of meaning.
4. **Discourse Theory:** We explicitly model entity salience (Centering Theory) to handle pronouns.

---

## 2. Theoretical Foundations

### 2.1 The Ninai Protocol (Abstract Syntax)

In v2.0, we adopt **Ninai** (Abstract Wikipedia's notation) as our primary representation of meaning.

* **Concept:** Language-Independent Logic Form.
* **Implementation:** `app/adapters/ninai.py`.
* **Theory:** A Ninai Object Tree represents the *Deep Structure* of a sentence. It uses **Constructors** (e.g., `ninai.constructors.Statement`) to define relationships without committing to a specific word order or morphology.

### 2.2 Grammatical Framework (Concrete Syntax)

We use GF as the low-level runtime engine to realize the Deep Structure into Surface Text.

* **Role:** Handles the "Morphological Explosion" (e.g., Finnish noun cases).
* **Hybridization:**
* **Tier 1 (RGL):** Uses "Hand-Written Grammars" (Chomskyan / Generative).
* **Tier 3 (Factory):** Uses "Topology Grammars" (Data-Driven).



### 2.3 Universal Dependencies (Evaluation)

We bridge the gap between **Generative Grammar** (building trees) and **Dependency Grammar** (analyzing links).

* **Theory:** "Construction-Time Tagging."
* **Implementation:** `app/core/exporters/ud_mapping.py`.
* **Logic:** Since we *build* the sentence, we know exactly which word is the Subject (`nsubj`) and which is the Object (`obj`). We map these intents to **CoNLL-U** tags dynamically, allowing our output to be evaluated against standard treebanks.

---

## 3. Tier 3 Theory: Weighted Topology (Udiron)

For under-resourced languages, writing a full generative grammar is too slow. We adopt the **Weighted Topology** approach from the `Udiron` project.

### 3.1 The Linearization Problem

How do you generate text for 300 languages when some are SVO (English), some SOV (Japanese), and some VSO (Irish)?

### 3.2 The Topological Solution

We view a sentence not as a tree, but as a **Field of Slots** sorted by weight.

* **The Mechanism:** We assign integer weights to dependency roles relative to the Root (Verb).
* **Configuration:** `data/config/topology_weights.json`.

**Example: Subject-Object-Verb (SOV)**

* `Subject (nsubj)`: **-10** (Far Left)
* `Object (obj)`: **-5** (Left)
* `Verb (root)`: **0** (Center)

**Result:** The engine simply sorts the constituents by weight: `[-10, -5, 0]`  `Subject + Object + Verb`.
This allows us to support any word order configuration purely through configuration, without changing code.

---

## 4. Discourse & Context (Centering Theory)

In v2.0, we moved beyond single sentences to **Discourse Planning**.

### 4.1 The Problem

* Sentence 1: "Marie Curie is a physicist."
* Sentence 2: "Marie Curie was born in Poland."
* *Critique:* Repetitive and unnatural.

### 4.2 The Solution: Entity Salience

We implement a simplified version of **Centering Theory**.

* **Backward-Looking Center ():** The entity currently "in focus" from the previous utterance.
* **Implementation:** `SessionContext` in Redis.
* **Rule:** If the **Subject** of the current sentence matches the **** of the session, we apply a **Pronominalization Transformation** (Swap Name  Pronoun).

---

## 5. Design Trade-offs

### 5.1 Determinism vs. Variation (Micro-Planning)

* **The Tension:** Rule-based systems are repetitive. AI systems are hallucination-prone.
* **The v2.0 Compromise:** **Learned Micro-Planning**.
* We use **AI (LLM)** to select the *lexical items* (Style).
* We use **GF (Rules)** to assemble the *syntax* (Grammar).
* *Result:* We can vary "died" vs "passed away" (Style) without risking "He passed away" for a female subject (Grammar handles gender).



### 5.2 NLG-First

* **The Choice:** The system is strictly **Generation-First** (NLG).
* **Implication:** We do not parse text. We render data. This eliminates the "Ambiguity Problem" common in translation systems because the input (Ninai JSON) is unambiguous by design.

---

## 6. Summary of Systems

| Component | Linguistic Concept | Implementation |
| --- | --- | --- |
| **Ninai Adapter** | Deep Structure / Logical Form | Recursive JSON Parser |
| **Lexicon** | Lexical Semantics | JSON Shards (`people.json`) |
| **RGL (Tier 1)** | Generative Grammar | `.gf` Source Files |
| **Factory (Tier 3)** | Topological Fields / Linearization | `topology_weights.json` |
| **Discourse Planner** | Centering Theory / Coreference | Redis Session Store |
| **UD Exporter** | Dependency Grammar | `ud_mapping.py` |

This document confirms that the SemantiK Architect v2.0 is a **Hybrid Neuro-Symbolic System**, leveraging the best of formal linguistics (GF/UD) and modern engineering (Redis/AI).