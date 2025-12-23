
# ⚖️ Attribution & Integration Record

**Abstract Wiki Architect v2.0**

## 1. Overview

The v2.0 "Omni-Upgrade" was significantly accelerated by auditing the **Ninai** and **Udiron** repositories (maintained by the Abstract Wikipedia team/community). Rather than reinventing the wheel, we have adopted specific protocols, algorithms, and datasets to ensure interoperability and linguistic robustness.

This document details exactly what was adopted, the nature of the integration, and the source of origin.

---

## 2. Integration: The Ninai Protocol

**Source Repository:** `gitlab.com/mahir256/ninai`
**License:** Apache 2.0

We adopted the **Ninai Object Model** to replace our internal ad-hoc flat format. This allows AWA to function as a compliant Z-Function renderer.

| Adopted Component | Source Location | AWA Implementation | Nature of Use |
| --- | --- | --- | --- |
| **Recursive JSON Schema** | `ninai/constructors.py` | `app/adapters/ninai.py` | **Pattern Adoption.** We moved from regex-parsing S-expressions to walking the specific JSON object tree used by Ninai. |
| **Constructor Keys** | `ninai/constructors.py` | `docs/14-VAR_FIX_LEDGER.md` | **Direct Copy.** We use the exact keys (`ninai.constructors.Statement`, `ninai.types.Bio`) to ensure compatibility. |
| **List Flattening Logic** | `ninai/renderers.py` | `app/adapters/ninai.py` | **Logic Port.** The recursive logic to turn nested `cons` lists into Python lists was adapted from the Ninai reference implementation. |

---

## 3. Integration: Udiron (Universal Dependencies)

**Source Repository:** `gitlab.com/mahir256/udiron`
**License:** Apache 2.0

We adopted the **Weighted Topology** algorithmic approach to solve the linearization problem (Word Order) for our Tier 3 (Factory) languages.

| Adopted Component | Source Location | AWA Implementation | Nature of Use |
| --- | --- | --- | --- |
| **Weighted Topology** | `udiron/base/constants.py` | `utils/grammar_factory.py` | **Algorithmic Inspiration.** We adopted the concept of assigning integers (e.g., `-10`, `0`, `+10`) to dependency roles to sort Subject/Verb/Object dynamically. |
| **Topology Weights** | `udiron/langs/` | `data/config/topology_weights.json` | **Data Adaptation.** We adapted the specific weight values used for SVO, SOV, and VSO languages. |
| **Gold Standard Data** | `tests.json` | `data/tests/gold_standard.json` | **Direct Ingestion.** We copied the input/output pairs for "Simple Sentences" to use as the ground truth for our "Judge" QA agent. |
| **Construction Tagging** | `udiron/renderers.py` | `app/core/exporters/ud_mapping.py` | **Concept Adoption.** The strategy of mapping internal constructor functions to UD tags (CoNLL-U) was inspired by Udiron's renderer logic. |

---

## 4. Licensing Note

Both `ninai` and `udiron` are licensed under **Apache 2.0**.
The Abstract Wiki Architect is also compatible with this license.

* **Code:** Where logic was adapted (e.g., the Topology Sort), it is largely re-implemented in Python to fit our Hexagonal Architecture, but the *intellectual lineage* belongs to the Udiron authors.
* **Data:** The `tests.json` file is used verbatim for testing purposes.

---

## 5. Summary of Divergence

While we adopted the *patterns*, our implementation differs in the **Engine Core**:

1. **Udiron** uses these weights to linearize dependencies directly at runtime.
2. **Architect (AWA)** uses these weights to *generate GF source code* (via the Architect Agent), which is then compiled into a binary. We use the weights at "Compile Time," not "Runtime."

*This document ensures credit is given where due and clarifies the architectural boundary between AWA and the reference implementations.*