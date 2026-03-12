# 🧠 The Everything Matrix v2.1: Health & Decision Specification

**SemantiK Architect**

## 1. Executive Summary

The **Everything Matrix** (`data/indices/everything_matrix.json`) is the central nervous system of the build pipeline. It replaces static configuration with a dynamic **Health Ledger**.

In **v2.1**, the Matrix evolves from a simple "File Exists" checker to a **14-Point Deep Tissue Scanner**. It audits every language across four strategic zones (Logic, Data, Application, Quality) to calculate a precise **Maturity Score (0-10)**. This score empowers the Orchestrator to make autonomous decisions (e.g., *"French is robust enough for High Road compilation, but Zulu needs Safe Mode and AI-repair"*).

---

## 2. The 4 Zones & 14 Health Blocks

Every language is graded on 14 specific metrics. These are not boolean flags; they are continuous scores (0.0 - 10.0) derived from physical code analysis.

### Zone A: RGL Engine (Logic) ⚙️

*Audits the structural integrity of the Grammatical Framework implementation.*

| Block | Metric Name | Definition | Target (10/10) |
| --- | --- | --- | --- |
| **1** | `CAT` | **Categories** | Are standard types (`N`, `V`, `A`) defined? |
| **2** | `NOUN` | **Morphology** | Can nouns/verbs be inflected? |
| **3** | `PARA` | **Paradigms** | Are smart constructors (`mkN`, `mkV`) avail? |
| **4** | `GRAM` | **Grammar** | Is the structural core implemented? |
| **5** | `SYN` | **Syntax** | Is the API layer exposed? |

> **Impact:** If `CAT` or `SYN` < 10, the build strategy automatically downgrades to **SAFE_MODE** (Factory) because the RGL is incomplete.

### Zone B: Lexicon (Data) 📚

*Audits the vocabulary depth and semantic alignment.*

| Block | Metric Name | Definition | Target (10/10) |
| --- | --- | --- | --- |
| **6** | `SEED` | **Core Seed** | Size of functional vocabulary (`core.json`). |
| **7** | `CONC` | **Concepts** | Size of domain vocabulary (`people.json`). |
| **8** | `WIDE` | **Wide Import** | Existence of bulk-import CSV. |
| **9** | `SEM` | **Semantics** | Wikidata Alignment Score. |

> **Impact:** If `SEED` < 2.0, the language is marked `runnable: false` to prevent the runtime from crashing on empty dictionaries.

### Zone C: Application (Use Case) 🚀

*Determines readiness for specific vertical capabilities.*

| Block | Metric Name | Definition | Requirement |
| --- | --- | --- | --- |
| **10** | `PROF` | **Bio-Ready** | Can generate Biographies? |
| **11** | `ASST` | **Chat-Ready** | Can handle dialog? |
| **12** | `ROUT` | **Routing** | Is topology configured? |

### Zone D: Quality (Verification) 🛡️

*Tracks the physical artifacts and regression status.*

| Block | Metric Name | Definition | Requirement |
| --- | --- | --- | --- |
| **13** | `BIN` | **Binary** | Is present in `semantik_architect.pgf`? |
| **14** | `TEST` | **Regression** | Gold Standard Pass Rate. |

---

## 3. The JSON Schema

The `build_index.py` script aggregates all scanners into this finalized structure.

```json
"fra": {
  "meta": { "iso": "fra", "name": "French", "family": "Romance" },
  "zones": {
    "A_RGL": { "CAT": 10, "NOUN": 10, "PARA": 10, "GRAM": 10, "SYN": 10 },
    "B_LEX": { "SEED": 8.5, "CONC": 4.2, "WIDE": 10, "SEM": 9.0 },
    "C_APP": { "PROF": 1.0, "ASST": 0.0, "ROUT": 1.0 },
    "D_QA":  { "BIN": 1.0, "TEST": 0.8 }
  },
  "verdict": {
    "maturity_score": 8.9,      // Weighted Average (A*0.6 + B*0.4)
    "build_strategy": "HIGH_ROAD", // Decisions: HIGH_ROAD | SAFE_MODE | SKIP
    "runnable": true            // If False, Worker will refuse to load it.
  }
}

```

---

## 4. The Scanning Architecture

The Matrix is populated by three specialized "Census Takers" running in parallel.

### 1. `rgl_auditor.py` (Zone A)

* **Target:** `gf-rgl/src/{lang}/`
* **Logic:** Checks for the physical existence of the 5 standard GF modules.
* **Output:** The structural integrity score.

### 2. `lexicon_scanner.py` (Zones B & C)

* **Target:** `data/lexicon/{lang}/`
* **Logic:**
* Parses JSON shards to count entries (`SEED`, `CONC`).
* Checks specific keys (`qid`, `forms`) for semantic alignment (`SEM`).
* Validates domain readiness (e.g., checks if `people.json` contains "physicist" for `PROF` score).



### 3. `qa_scanner.py` (Zone D)

* **Target:** `gf/` and `tests/logs/`
* **Logic:**
* Verifies if the language key exists in `semantik_architect.pgf`.
* Parses the latest JUnit XML report from `pytest` to extract pass/fail rates.



---

## 5. Decision Logic (The Verdict)

The Orchestrator (`builder/orchestrator.py`) reads the `verdict` object to determine the build path.

### Strategy Table

| Maturity | Zone A Score | Verdict | Orchestrator Action |
| --- | --- | --- | --- |
| **> 7.0** | **10 (Perfect)** | `HIGH_ROAD` | Links directly to RGL source. Full optimization. |
| **> 2.0** | **Any** | `SAFE_MODE` | Generates "Factory Grammar" (Weighted Topology). Triggers **Architect Agent** if file missing. |
| **< 2.0** | **Any** | `SKIP` | Excludes language from build. |

### Runnable Logic

The Worker (`app/workers/worker.py`) checks `verdict.runnable` before initialization.

* **Rule:** `runnable = (SEED >= 2.0) OR (build_strategy == "HIGH_ROAD")`
* **Why:** A language with no core words ("is", "the") will generate empty strings or crash the linearization engine. We protect the runtime by isolating these "Zombie Languages."

---

## 6. Implementation Guide

### Adding a New Language

1. **Register:** Create `data/lexicon/{iso}/core.json`.
2. **Scan:** Run `python tools/everything_matrix/build_index.py`.
3. **Check:** Ensure `SEED` score > 2.0.
4. **Build:** Run `python manage.py build`.

### Debugging Low Scores

* **Low `SEM`:** Your JSON is missing `qid` fields. Run `harvest_lexicon.py`.
* **Low `PROF`:** You cannot generate biographies. Add `people.json`.
* **Low `TEST`:** Your grammar logic is flawed. Run `pytest` and check the **Judge Agent's** critique.