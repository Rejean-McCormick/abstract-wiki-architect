Here is the formal documentation for the **SemantiK Architect: Multilingual Engine V2**.

This document defines the architecture, directory structure, and logic required to scale the system from \~40 to 300+ languages using a **Hybrid Factory** approach.

-----

# 📘 Project Abstract: The Hybrid Multilingual Engine

### 1\. Core Philosophy

To support the 300+ languages required by Abstract Wikipedia, we cannot rely solely on the academic **Resource Grammar Library (RGL)**, which covers only \~40 languages. Conversely, manual implementation of 260+ languages is unscalable.

We adopt a **Three-Tier Hybrid Architecture**:

1.  **Prioritize Quality:** Use official, expert-written grammars where available.
2.  **Allow Overrides:** Enable manual community contributions for specific languages.
3.  **Guarantee Coverage:** Programmatically generate "Pidgin" (simplified) grammars for all remaining languages to ensure 100% API availability.

### 2\. The "Waterfall" Lookup Logic

The build system (`build_300.py`) will resolve a language code (e.g., `zul`) by checking sources in a specific priority order.

  * **Priority 1: Official RGL.** *Is it in the standard library?* If yes, use it.
  * **Priority 2: Contrib.** *Do we have a manual draft in `gf/contrib`?* If yes, use it (overrides RGL).
  * **Priority 3: Factory.** *Is it in the generated folder?* If yes, use it.
  * **Fail:** If none exist, skip the language.

-----

### 3\. File Arborescence (Directory Structure)

The project structure is reorganized to separate **Source** (Official), **Manual** (Community), and **Generated** (Factory) assets.

```text
C:\MyCode\SemantiK_Architect\Semantik_architect\
│
├── architect_http_api\
│   └── gf\
│       └── language_map.py       # [ROUTER] Maps Z-IDs (Z1002) to Concrete Names (WikiEng)
│
├── docker\
│   └── Dockerfile.backend        # [ENV] Copies all 3 grammar folders into the container
│
├── gf\
│   ├── Wiki.pgf                  # [ARTIFACT] The compiled binary containing ALL languages
│   ├── build_300.py              # [BUILDER] Orchestrates the "Waterfall" compilation
│   │
│   ├── gf-rgl\                   # [TIER 1] Official RGL (Cloned Git Repo)
│   │   └── src\                  #    Contains: english, french, chinese...
│   │
│   ├── contrib\                  # [TIER 2] Manual Overrides (Version Controlled)
│   │   └── que\                  #    Example: High-quality manual Quechua grammar
│   │       └── WikiQue.gf
│   │
│   └── generated\                # [TIER 3] Factory Output (Git Ignored / Auto-Cleaned)
│       ├── zul\                  #    Example: Auto-generated Zulu stubs
│       ├── yor\                  #    Example: Auto-generated Yoruba stubs
│       └── ... (250+ others)
│
├── utils\
│   └── grammar_factory.py        # [GENERATOR] Reads config, writes files to 'gf/generated/'
│
└── test_gf_dynamic.py            # [VERIFIER] Dynamically tests every language in Wiki.pgf
```

-----

### 4\. Component Definitions

#### A. The Language Factory (`utils/grammar_factory.py`)

  * **Purpose:** To ensure no language is left behind.
  * **Input:** A configuration dictionary defining the "DNA" of missing languages (Name, ISO Code, Word Order).
  * **Output:** Valid, compilable GF source files (`Res`, `Syntax`, `Wiki`) implementing a simplified "Pidgin" grammar (e.g., SVO string concatenation).
  * **Lifecycle:** Runs *before* the build. Wipes and recreates the `gf/generated/` folder every time.

#### B. The Orchestrator (`gf/build_300.py`)

  * **Purpose:** To bind all separate grammar files into a single Portable Grammar Format (`.pgf`) file.
  * **Logic:**
      * Iterates through a master list of 300+ ISO codes.
      * Resolves the file path for each code using the **Waterfall Logic**.
      * Injects the `gf/generated` and `gf/contrib` paths into the compiler's search scope.
      * Generates the bridging `Wiki{Lang}.gf` file for RGL languages to connect them to our API.

#### C. The Router (`language_map.py`)

  * **Purpose:** To translate external identifiers into internal GF concrete grammar names.
  * **Logic:**
      * `get_concrete("fra")` -\> `WikiFre` (Legacy RGL naming)
      * `get_concrete("zul")` -\> `WikiZul` (Standard Factory naming)
      * `get_concrete("Z1002")` -\> `WikiEng` (Wikidata ID mapping)

-----

### 5\. Developer Workflows

#### Scenario A: Adding a "Missing" Language

  * **Goal:** Add *Hausa* (`hau`), which is not in the RGL.
  * **Action:** Open `utils/grammar_factory.py` and add to the config:
    ```python
    "hau": {"name": "Hausa", "order": "SVO"}
    ```
  * **Result:** The next build automatically creates `WikiHau` and compiles it.

#### Scenario B: "Graduating" a Language

  * **Goal:** Replace the "Pidgin" Zulu grammar with a high-quality manual one.
  * **Action:**
    1.  Create folder `gf/contrib/zul/`.
    2.  Write (or paste) the high-quality `WikiZul.gf` files there.
  * **Result:** `build_300.py` detects the folder in `contrib`, ignores the one in `generated`, and compiles the high-quality version.

#### Scenario C: Updating the Core

  * **Goal:** Get the latest fixes for English or French.
  * **Action:** Run `git pull` inside `gf/gf-rgl/`.

-----

### 6\. Implementation Checklist

1.  ✅ **Architecture Defined.**
2.  ⬜ **Create Factory Script:** `utils/grammar_factory.py`.
3.  ⬜ **Update Orchestrator:** `gf/build_300.py` (Waterfall logic).
4.  ⬜ **Update Router:** `language_map.py` (300+ code support).
5.  ⬜ **Update Docker:** Copy `contrib` and `generated` folders.
6.  ⬜ **Verification:** Run `test_gf_dynamic.py`.

