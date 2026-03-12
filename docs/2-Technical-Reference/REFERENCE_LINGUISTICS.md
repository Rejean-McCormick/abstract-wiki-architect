# THEORY_NOTES.md  
SemantiK Architect – Theoretical Positioning

This document explains how the architecture in this repository relates to
existing ideas in NLG and linguistic theory. It is not an implementation
spec; it is a map of **where the design is coming from** and **what it is
compatible with**.

---

## 1. Purpose

SemantiK Architect is designed as a **practical NLG stack** for Abstract Wikipedia, but its internal structure is informed by:

- **Grammar engineering / grammar matrix approaches**
- **Construction grammar / frame semantics**
- **Abstract semantic formalisms** (UMR, Ninai-style representations)
- **Typological “language family” thinking**

The goal is to be:

- **Engineered enough** for large-scale deployment, and  
- **Theory-aware enough** that it can cooperate with research-grade tools and ideas.

---

## 2. High-level analogy: where this sits

Very roughly:

- Like **Grammatical Framework (GF)**:
  - We distinguish *family-level* grammar logic and *language-specific* data.
  - We use shared, language-agnostic constructions (patterns) plus per-language realizations.

- Like a **Grammar Matrix** project:
  - We factor out cross-language patterns into configurable “matrices” and “cards”, instead of writing each language from scratch.
  - We have family templates that are parameterized by language data.

- Like **frame semantics / construction grammar**:
  - We model recurrent *constructions* (e.g. “X is a Y”, “X has Y”, relative clauses) as reusable blocks.
  - Constructions are not tied to any single language; they are parameterized by an engine and a language profile.

- Like **UMR / Ninai / abstract semantic notations**:
  - We accept frame-like semantic inputs (`BioFrame` etc.).
  - We assume we can map richer AW formalisms onto these frames later.

This project does **not** try to re-implement those formalisms directly; it borrows their *separation of concerns* and *modular structure*.

---

## 3. Relation to specific ideas / traditions

### 3.1 Grammatical Framework (GF)

GF separates:

- **Abstract syntax** (language-independent structures, e.g. `Predication subj pred`)
- **Concrete syntaxes** (per-language mappings to surface strings)

In this project:

- `semantics/types.py` + `constructions/*.py` play the role of **abstract syntax and linearization rules**:
  - Frames and roles (AGENT, PATIENT, TOPIC, etc.)
  - Constructions that map frames to clause-level structures.

- `engines/*.py` + `data/morphology_configs/*.json` + `data/<family>/<lang>.json` play the role of **concrete syntax/morphology**:
  - Word order,
  - Morphological realization,
  - Agreement patterns.

Key difference:

- We do **not** define a full GF-style type system.
- We aim for a *lighter-weight, JSON-driven* approach that fits Wikifunctions constraints and is easier to maintain by non-experts.

### 3.2 Grammar Matrix / broad-coverage grammars

Grammar matrix projects (e.g. HPSG-based) build:

- A **cross-linguistic core**, and
- Language-specific “slugs” or configurations that plug into it.

In this project:

- The “matrix” idea appears as:

  - Family matrices in `data/morphology_configs/*.json`
  - Language cards in `data/<family>/<lang>.json`
  - Shared constructions in `constructions/*.py`

- Each family engine is, conceptually, a **parameterized grammar sketch**:
  - It knows what kinds of inflection and syntax the family has (cases, noun classes, harmony, etc.),
  - It pulls concrete parameters from JSON.

We do not implement a full constraint-based grammar formalism, but we:

- Encapsulate **morphosyntactic parameters** in structured data,
- Make it possible to **derive many languages from a single family template**.

### 3.3 Construction Grammar and Frame Semantics

The constructions modules are explicitly constructional:

- Each file in `constructions/` describes a **reusable mapping** from roles and features to syntactic structure, e.g.:

  - Predicate nominals, locatives, existentials,
  - Possession with “have” vs “be + genitive”,
  - Relative clauses (subject gap, object gap),
  - Topic–comment structures.

- They operate on **semantic role labels** (subject, possessor, theme, etc.) and **information structure labels** (topic/focus).

This is closely aligned with:

- **Construction grammar**:
  - Constructions are the primary units, not just rules about individual words.
- **Frame semantics**:
  - Certain constructions correspond to lexical or grammatical frames (e.g. `Being_born`, `Possession`, `Residence`).

We keep the representation pragmatic:

- Roles are simple strings,
- Frames are Python dataclasses (e.g. `BioFrame`),
- But the design is open to being mapped to richer framebanks or AW’s own abstract representations.

### 3.4 Abstract semantic formalisms (UMR, Ninai, etc.)

Abstract Wikipedia has explored notations such as:

- **Ninai** (a compact notation for abstract content),
- Mappings from structured Wikidata statements to abstract meaning representations,
- Other AMR-like or UMR-like representations.

In this project:

- `semantics/types.py` defines *implementation-oriented frames* for now (e.g. biography-centric).
- `semantics/aw_bridge.py` / `semantics/normalization.py` are intended to be the place where:

  - AW’s chosen notation (Ninai, UMR, etc.) is mapped into internal frame types.
  - We lose as little information as possible, but we adapt to what constructions/engines expect.

The philosophy is:

- Keep the **NLG architecture** stable,
- Allow **input formalisms** to change or evolve,
- Provide clear mapping points rather than baking in any specific notation forever.

---

## 4. Internal abstractions and why they look like this

### 4.1 Family Engines

Assumption:

- A large number of languages share **core structural properties**:

  - Agglutinative vs fusional vs isolating,
  - Case vs classifier vs noun class,
  - Topic–comment vs subject–predicate orientation.

Family engines:

- Capture these recurring patterns once (e.g. “agglutinative + harmony + suffix chaining”),
- Parameterize the specifics via JSON and lexicon data.

This is a typological, not purely genetic, grouping:

- “Agglutinative” includes Turkic, Uralic, Dravidian, Koreanic features,
- “Bantu” groups noun class systems with concord,
- “Isolating” covers Chinese-like analytic grammars.

The design is influenced by:

- WALS-style typology (word order, morph type),
- Practical “language family” divisions that linguists and engineers already use.

### 4.2 Constructions vs Engines

Reason for splitting:

- Engines know **how** a language inflects and orders elements.
- Constructions know **what configuration** of elements a clause needs.

This separation:

- Allows the same construction code to be reused across families,
- Keeps engines agnostic about specific predicate types (e.g. biographies vs locations vs events),
- Encourages **compositionality**: semantics → construction → morphology.

### 4.3 Semantics and Discourse

We deliberately use:

- Simple dataclasses (`BioFrame`, `Event`, `Entity`, `TimeSpan`) instead of a full logical language.
- A **minimal DiscourseState** with:

  - salience,
  - last-mention position,
  - topic tracking.

The idea is:

- Capture just enough information to make **real discourse decisions**:
  - pronoun vs full NP,
  - topic markers vs canonical word order,
  - sentence ordering for short texts.

This keeps the system usable for production while leaving room to:

- Align with richer discourse and anaphora theories later,
- Plug in more elaborate centering or information-structure models if needed.

---

## 5. Design tradeoffs

### 5.1 Expressiveness vs maintainability

We deliberately do **not**:

- Implement full-blown HPSG or LFG-style grammars,
- Implement a full type system à la GF abstract syntax,
- Enforce a single deep semantic formalism.

Instead, we choose:

- JSON-encoded parameters and lexica,
- Python constructions and engines that can be read by non-specialists,
- A design that is understandable by both linguists and software engineers.

### 5.2 Family-based generalization vs per-language precision

- Using family engines risks **over-generalization**: some languages are typological hybrids or have idiosyncrasies.
- The architecture counters this by:
  - Allowing language cards to override or extend family patterns,
  - Using the lexicon to encode idiosyncratic behavior,
  - Letting constructions ask for language-specific flags where needed.

### 5.3 NLG-first vs parsing-first

This project is **NLG-first**:

- All modules are oriented toward generation, not parsing.
- But the separation into semantics, constructions, morphology, and lexicon means:
  - A future parsing side could re-use portions of the same data,
  - Or at least be developed in parallel with consistent categories.

---

## 6. Future theoretical directions

This architecture is intended to be a **bridge** between practical AW deployments and more research-oriented work. Natural extensions include:

1. **Richer frame inventory**  
   - Generalize `BioFrame` into a set of core frames:
     - Birth, death, office holding, discovery, award, location, membership, etc.
   - Align those with AW’s semantic notations and Wikidata schema.

2. **Closer integration with UMR / Ninai**  
   - Define explicit mappings from UMR/Ninai structures to internal frames.
   - Track information-structure annotations in those notations.

3. **More powerful discourse models**  
   - Add centering-based or game-theoretic models for anaphora and topic shifts.
   - Support longer multi-sentence texts while preserving coherence.

4. **Learned components on top of rule-based scaffolding**  
   - Keep rules as the **backbone** for grammar,
   - Explore learned models for:
     - lexical choice within a frame,
     - micro-variation in word order,
     - style control.

5. **Closer alignment with GF / grammar engineering tools**  
   - Export parts of the matrices/cards as GF lexica or vice versa.
   - Treat the family engines as “GF light” where appropriate.

---

## 7. Summary

- The architecture is **inspired by** GF, Grammar Matrix projects, construction grammar, and frame semantics, but implemented in a pragmatic, JSON-driven, Python-based form suitable for Abstract Wikipedia and Wikifunctions.
- It aims to:
  - Separate **semantics** from **constructions** from **morphosyntax** from **lexicon**,
  - Share as much logic as possible across **language families**,
  - Allow both linguists and engineers to collaborate on a shared code/data base.

These notes are here to make explicit that the system is not “just a pile of scripts”, but a conscious engineering interpretation of long-standing ideas in formal and computational linguistics.
