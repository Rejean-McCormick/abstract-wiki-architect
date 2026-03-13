# 20. Decisions

## Purpose

This page records the **product-defining choices** that explain *why SemantiK Architect works the way it does*, and what must stay stable when the system evolves.

(Notes: the source docs use the former name “Abstract Wiki Architect”; the decisions below remain applicable under the SemantiK Architect rename.)

---

## Canonical decisions (high level)

### 1) Data-driven registry instead of hardcoded configuration (“Everything Matrix”)

* **Problem:** hardcoded language lists drift from reality.
* **Decision:** a dynamic registry is rebuilt by scanning what exists on disk before each build.
* **Why:** it becomes the single source of truth; adding a language becomes “add the files.” 

### 2) Hybrid language strategy instead of a single approach

* **Decision:** a tiered strategy: high-resource languages use GF/RGL; under-resourced languages use a weighted-topology approach (from the Udiron lineage) for coverage. 
* **Why:** it explicitly manages the quality vs coverage tradeoff rather than pretending one method fits all.

### 3) Standards interoperability as a first-class requirement

* **Decision:** design for interoperability with **Ninai** (meaning protocol) and **UD** (validation/export surface), framed as a core architecture choice. 

### 4) Discourse/context is a core capability (not an afterthought)

* **Decision:** maintain session context (e.g., for pronouns/discourse planning) as a key architectural pillar. 

### 5) Quality is enforced via Gold Standards + an automated Judge

* **Decision:** regressions are checked against Gold Standard data (explicitly ingesting the Udiron test suite lineage) and gated by a similarity threshold (0.8 is called out). 

### 6) AI is used as a scale multiplier for generation and evaluation (as designed in v2.0)

* **Decision:** specialized agents (“Architect” for generating Tier-3 grammar assets and “Judge” for validation + issue filing). 
* **Note for your wiki:** if your current SemantiK direction reduces/removes build-time AI, keep this decision as “historical” or “optional mode,” not as the default.

### 7) “No arbitrary execution” in tooling

* **Decision:** operational tools are run through a strict allowlist registry rather than arbitrary commands, to keep the system safe and predictable. 

---

## How new decisions should be recorded

When changing any of the above (e.g., removing AI from builds, changing tier strategy, changing gating thresholds), add an entry that states:

* Context / problem
* Decision
* Why
* Consequences (what becomes easier/harder)

This keeps SemantiK Architect understandable without turning the wiki into low-level technical documentation.
