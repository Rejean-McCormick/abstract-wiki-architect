# Technical Specification: The Everything Matrix

## 1\. Overview

The **Everything Matrix** (`everything_matrix.json`) is the central nervous system of the project. It aggregates data from the RGL file system, the application frontend, and the compilation artifacts into a single unified index.

**Purpose:**

1.  **Orchestration:** Provides the "facts" needed by the build scripts to choose strategies (High Road vs. Safe Mode).
2.  **Visibility:** Powers the "Language Status Dashboard" on the frontend, visualizing progress (Heatmap).
3.  **Lifecycle Management:** Tracks every language from "Planned" (Level 1) to "Production" (Level 10) across 15 distinct architectural blocks.

**Artifact Path:** `data/indices/everything_matrix.json`

-----

## 2\. JSON Data Schema

The matrix is a JSON object keyed by the **3-letter Wiki Code** (e.g., `Eng`, `Amh`, `Zho`).

```json
{
  "timestamp": "2023-10-27T10:00:00Z",
  "languages": {
    "Eng": {
      "meta": {
        "wiki_code": "Eng",
        "rgl_code": "Eng",
        "iso_639_3": "eng",
        "name": "English",
        "family": "Germanic"
      },
      "blocks": {
        "rgl_cat": 10,
        "rgl_noun": 10,
        "rgl_grammar": 10,
        "rgl_syntax": 10,
        "lex_seed": 8,
        "app_profile": 10
        // ... (see Section 3 for full list)
      },
      "status": {
        "build_strategy": "HIGH_ROAD",
        "overall_maturity": 9.2,
        "is_active": true
      }
    }
  }
}
```

-----

## 3\. The 15 Data Blocks (Variables)

Each language tracks 15 specific components. The value for each variable is an integer from **0 to 10** (see Maturity Scale).

### **Zone A: RGL Foundation (The Engine)**

*These blocks determine if the language can technically compile.*

| Variable Name | Description | Source / Detection Logic |
| :--- | :--- | :--- |
| **`rgl_cat`** | Base Category definitions (`CatX.gf`). | Scanner finds `gf-rgl/src/x/CatX.gf`. |
| **`rgl_noun`** | Noun morphology rules (`NounX.gf`). | Scanner finds `gf-rgl/src/x/NounX.gf`. |
| **`rgl_paradigms`** | Constructor functions (`ParadigmsX.gf`). | Scanner finds `gf-rgl/src/x/ParadigmsX.gf`. |
| **`rgl_grammar`** | Core grammatical structure (`GrammarX.gf`). | Scanner finds `GrammarX.gf` (Physical or Family). |
| **`rgl_syntax`** | High-level API access (`SyntaxX`). | Scanner finds `api` folder support or specific `SyntaxX` module. |

### **Zone B: Lexicon (The Data)**

*These blocks determine the vocabulary size and richness.*

| Variable Name | Description | Source / Detection Logic |
| :--- | :--- | :--- |
| **`lex_seed`** | Initial AI-generated dictionary. | Exists in `data/seeds/{lang}.json`. |
| **`lex_concrete`** | Compiled GF Dictionary file (`WikiX.gf`). | Scanner finds generated `.gf` file in root. |
| **`lex_wide`** | Large-scale external import (Wiktionary/PanLex). | Check `data/imports/{lang}_wide.csv`. |
| **`sem_mappings`** | Abstract-to-Concrete mappings. | Check `semantics/mappings/{lang}.json`. |

### **Zone C: Application (The Interface)**

*These blocks determine if the language works in the User Interface.*

| Variable Name | Description | Source / Detection Logic |
| :--- | :--- | :--- |
| **`app_profile`** | Frontend configuration entry. | Exists in `architect_frontend/.../profiles.json`. |
| **`app_assets`** | UI Assets (Flag icon, localized strings). | Check `public/flags/{iso}.svg`. |
| **`app_routes`** | Active API endpoint status. | Backend API responds 200 OK for this lang. |
| **`build_config`** | Build Strategy assignment. | Presence in `rgl_matrix_strategy.json`. |

### **Zone D: Quality (The Status)**

*These blocks represent the health of the language.*

| Variable Name | Description | Source / Detection Logic |
| :--- | :--- | :--- |
| **`meta_compile`** | Binary compilation status. | `Wiki.pgf` contains this language. |
| **`meta_test`** | Unit test pass rate. | Percentage of `tests/lang_test.py` passing. |

-----

## 4\. The Maturity Scale (0-10)

Every block is assigned a score based on its state.

  * **0 - ABSENT**: The file or data block is completely missing.
  * **1 - PLANNED**: Listed in configuration but no physical files exist.
  * **3 - SCAFFOLDED**: Empty files, folders, or placeholders created.
  * **5 - DRAFT**: Auto-generated content (e.g., AI Lexicon, `Safe Mode` Grammar). Functional but unverified.
  * **7 - BETA**: Manually reviewed or successfully compiled in `High Road` mode.
  * **8 - PRE-FINAL**: Fully integrated into the app and passing basic tests.
  * **10 - FINAL**: Production-ready, validated by a human linguist, 100% test coverage.

-----

## 5\. Aggregation Logic (Tools)

### **The Aggregator (`tools/everything_matrix/build_index.py`)**

This script acts as the "Grand Aggregator." It calls the sub-scanners, consolidates scores, and generates the final JSON.

1.  **Reads RGL Inventory:** Maps `rgl_*` scores (0 if missing, 10 if present) using `tools/everything_matrix/rgl_scanner.py`.
2.  **Reads Strategy Map:** If Strategy is `HIGH_ROAD`, `rgl_syntax` gets 10. If `SAFE_MODE`, it gets 5.
3.  **Reads File System:** Checks for flags, JSON seeds, and generated GF files via dedicated scanners (`lexicon_scanner.py`, `app_scanner.py`).
4.  **Reads PGF:** Queries the compiled `Wiki.pgf` to confirm `meta_compile` status.
5.  **Outputs:** Writes the consolidated JSON to `data/indices/everything_matrix.json`.

-----

## 6\. Visualization (The Dashboard)

The Frontend will read `everything_matrix.json` to render the **Language Health Grid**:

  * **Rows:** Languages.
  * **Columns:** The 15 variables above.
  * **Cell Color:**
      * `0-2`: 🔴 Red (Missing/Blocker)
      * `3-5`: 🟡 Yellow (Draft/Safe Mode)
      * `6-8`: 🔵 Blue (Functional/Beta)
      * `9-10`: 🟢 Green (Production)