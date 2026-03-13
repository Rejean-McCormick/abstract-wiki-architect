# 🏛️ Engine Architecture & Internals

**SemantiK Architect v2.1**

## 1. High-Level System Overview

The SemantiK Architect is a **Hybrid Natural Language Generation (NLG) Engine**. It combines the determinism of Rule-Based Systems (Grammatical Framework) with the flexibility of modern AI Agents and the interoperability of Semantic Web standards.

It is designed to solve the **"Long Tail" Problem**: ensuring verifiable, high-quality encyclopedic text generation for 300+ languages, from high-resource languages like English (Tier 1) to under-resourced languages like Zulu or Quechua (Tier 3).

### The Four-Layer Architecture

The architecture separates the system into four distinct layers to ensure modularity, scalability, and state management:

#### Layer A: The Lexicon (Data)

* **Role:** The vocabulary. Stores words and their inherent properties (gender, stems).
* **Strategy:** **Usage-Based Sharding**. Data is organized by domain (`core`, `people`, `science`) rather than monolithic dictionary files.
* **Alignment:** Mapped to **Wikidata QIDs** (e.g., `Q42` -> `Alan Turing`) to ensure grounding in the Semantic Web.
* **Standard:** Strictly uses **ISO 639-1 (2-letter)** directory names (e.g., `data/lexicon/en/`).

#### Layer B: The Grammar Matrix (Logic)

* **Role:** The rules. Defines morphology (inflection) and syntax (word order).
* **Mechanism:** Uses the **Grammatical Framework (GF)** to define abstract syntax trees that are linearized into concrete strings.
* **Hybrid Approach:** Combines expert-written grammars (RGL) with **Weighted Topology Grammars** (Factory) to guarantee 100% coverage.

#### Layer C: The Renderer (Presentation)

* **Role:** The assembly. Takes an abstract intent and transforms it into text.
* **Input Ports (Dual-Path):**
* **Strict Path:** Internal `BioFrame` (Flat JSON) for production stability.
* **Prototype Path:** `UniversalNode` (Recursive Ninai JSON) for experimental flexibility.


* **Output Port:** Natural Language Text or **CoNLL-U** (Universal Dependencies).

#### Layer D: The Context (State) [NEW in v2.0]

* **Role:** The memory. Manages session state to handle **Discourse Planning**.
* **Mechanism:** Uses **Redis** to store entities mentioned in previous sentences.
* **Function:** Enables **Pronominalization** (e.g., swapping "Marie Curie" for "She" in the second sentence).

---

## 2. The Hybrid Factory Architecture

To scale from ~40 academic languages to the 300+ required by Wikipedia, we employ a **Three-Tiered Hybrid System**:

### Tier 1: The "High Road" (RGL)

* **Source:** The official **GF Resource Grammar Library**.
* **Quality:** Expert-written, linguistically perfect. Handles complex morphology (case declension, verb conjugation).
* **Examples:** English (`en`), French (`fr`), Russian (`ru`), Hindi (`hi`).
* **Internal Mapping:** The engine automatically maps the outer 2-letter code (`en`) to the inner 3-letter RGL module (`WikiEng`) at runtime.
* **Build Strategy:** `HIGH_ROAD`.

### Tier 2: Manual Contrib (Overrides)

* **Source:** `gf/contrib/{lang}/`.
* **Quality:** Community-contributed grammars that are not yet in the official RGL but are better than machine-generated stubs.
* **Role:** Overrides both Tier 1 and Tier 3 if present.

### Tier 3: The "Weighted Factory" (Automated) [UPDATED]

* **Source:** `generated/src/{lang}/`.
* **Logic:** **Weighted Topology Sorting** (adapted from Udiron).
* **Mechanism:** Instead of hardcoded SVO templates, the factory uses a configuration file (`topology_weights.json`) to define the relative position of Subject, Verb, and Object.
* *Example:* For Japanese (SOV), `obj` has a lower weight than `verb`, ensuring correct linearization automatically.


* **Role:** Ensures the API never returns a 404. Supports SVO, SOV, VSO, VOS, OVS, OSV word orders dynamically.
* **Build Strategy:** `SAFE_MODE`.

---

## 3. The "Two-Phase" Build Pipeline

We identified a critical issue in the standard GF build process where sequential compilation overwrites the binary (the "Last Man Standing" bug). The new **Build Orchestrator** (`builder/orchestrator.py`) implements a strict two-phase process to resolve this.

### Phase 1: Isolated Verification

The orchestrator iterates through the **Everything Matrix** inventory:

1. **Resolve Path:** Determines if the language is Tier 1, 2, or 3.
2. **Compile:** Runs `gf -batch -c path/to/Wiki{Lang}.gf`.
3. **Output:** Generates a temporary `.gfo` (object file).
4. **Verdict:** If compilation fails, the **Architect Agent** is triggered to attempt a repair (see Section 6).

### Phase 2: Global Linking

Once all languages are verified:

1. **Aggregate:** The orchestrator collects the file paths of all successful Phase 1 candidates.
2. **Link:** It executes a **single** `gf -make` command containing the Abstract Grammar and *all* valid Concrete Grammars.
3. **Result:** A single `semantik_architect.pgf` binary containing 50+ languages.

---

## 4. The "Everything Matrix" (The Brain)

The system is no longer driven by static config files. It uses a **Dynamic Registry** called the **Everything Matrix** (`data/indices/everything_matrix.json`).

### The Scanning Suite (`tools/everything_matrix/`)

Before any build, the system runs a deep-tissue audit:

* **`rgl_auditor.py`**: Scans `gf-rgl/src` to detect which modules (`Cat`, `Noun`, `Paradigms`) exist on disk. It assigns a **Maturity Score (0-10)**.
* **`lexicon_scanner.py`**: Audits `data/lexicon/{iso_2}/` to count vocabulary size.
* **`build_index.py`**: The master script. It runs the sub-scanners and updates the JSON matrix using strictly **2-letter ISO codes**.

### Decision Logic

The Build Orchestrator reads the Matrix to decide how to treat a language:

* **Score > 7:** Build as **Tier 1** (High Road).
* **Score < 7:** Downgrade to **Tier 3** (Factory) to prevent build failures.

---

## 5. Hexagonal Architecture (The Code)

The backend follows **Ports and Adapters** (Hexagonal) architecture to keep the core domain logic isolated from external tools.

### The Core (`app/core/`)

* **Domain:** Pure Python classes (`BioFrame`, `Sentence`, `DiscourseEntity`). No external dependencies.
* **Logic:** `GrammarEngine` (rendering) and `DiscoursePlanner` (state).

### The Adapters (`app/adapters/`)

* **Input Port (API):** `ninai.py` (Recursive JSON Parser) and `api.py` (FastAPI).
* **Output Port (Exporters):** `ud_mapping.py` (CoNLL-U conversion).
* **Persistence:** File-system adapters reading the `gf/` directory.
* **State:** `redis_bus.py` for Session Context storage.

### The Application (`app/shared/`)

* **Config:** `config.py` (Pydantic settings) is the single source of truth.
* **Container:** Dependency Injection wiring.

---

## 6. AI Services & Automation [NEW]

The v2.0 architecture integrates AI Agents to handle "Human-in-the-Loop" tasks automatically.

### The Architect Agent

* **Role:** The Builder.
* **Trigger:** Build failure or missing language in the Matrix.
* **Action:** Generates raw GF code using the **Frozen System Prompt** to create a Tier 3 grammar from scratch.
* **Loop:** Writes Code → Compiles → Reads Error Log → Rewrites Code.

### The Judge Agent

* **Role:** The QA Engineer.
* **Trigger:** Daily scheduled task or "Whistleblower" mode.
* **Action:** Compares SKA output against the **Gold Standard** (`data/tests/gold_standard.json`).
* **Output:** If quality is low, it automatically opens a GitHub Issue via the API.

---

## 7. Data Flow: The Request Lifecycle

1. **Ingest:** User POSTs a JSON object to `/api/v1/generate/{lang_code}` (e.g., `en`).
2. **Adapt (Dual-Path):**
* **Path A (Strict):** If `frame_type="bio"`, validated as `BioFrame`.
* **Path B (Prototype):** If `function="..."`, parsed as `UniversalNode` by the **Ninai Adapter**.


3. **Context:**
* **Discourse Planner** checks Redis for `X-Session-ID`.
* If the Subject matches the Session Focus, it applies **Pronominalization** ("She" instead of "Marie").


4. **Render:**
* The engine maps the 2-letter code (`en`) to the internal grammar (`WikiEng`).
* It looks up vocabulary in the **Lexicon**.
* It applies **Weighted Topology** rules (if Tier 3) or RGL rules (if Tier 1).


5. **Export:**
* If `Accept: text/plain`, returns the string.
* If `Accept: text/x-conllu`, the **UD Exporter** maps the tree to dependency tags.



---

## 8. Directory Map & Key Files

| Path | Component | Description |
| --- | --- | --- |
| **`builder/orchestrator.py`** | **The Builder** | The script that runs the Two-Phase compilation & Architect Agent loop. |
| **`app/adapters/ninai.py`** | **Input Port** | The recursive parser for Ninai JSON objects. |
| **`app/core/exporters/`** | **Output Port** | Contains `ud_mapping.py` for CoNLL-U export. |
| **`data/config/topology_weights.json`** | **Configuration** | Defines SVO/SOV/VSO weights for the Factory. |
| **`data/tests/gold_standard.json`** | **QA Data** | The "Ground Truth" dataset (migrated from Udiron). |
| **`gf-rgl/`** | **Tier 1 Source** | External submodule containing expert grammars. |
| **`generated/src/`** | **Tier 3 Source** | Folder for auto-generated "Factory" grammars. |
| **`gf/semantik_architect.pgf`** | **The Artifact** | The final compiled binary used by the API. |