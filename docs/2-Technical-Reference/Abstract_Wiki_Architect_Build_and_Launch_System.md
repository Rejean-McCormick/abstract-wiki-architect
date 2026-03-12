
# 🚀 SemantiK Architect: Unified Build & Launch System (v2.0)

## 1. High-Level Architecture

The system follows a strict **"Check, Build, Serve"** pipeline. It does not simply start the API; it first performs a deep census of your data (The Matrix), compiles the grammar binary (The PGF) using a robust two-phase process, and only then launches the runtime services.

The v2.0 architecture replaces fragile OS-scripts with a **Unified Python Task Runner** to ensure speed, atomicity, and portability.

---

## 2. Level 1: The Commander (`manage.py`) 🚀

**Script:** `manage.py` (Replaces `launch.ps1`)
**Role:** The Unified CLI & Environment Manager
**Location:** Root

This is the single entry point for all developer operations. It centralizes logic previously scattered across `.bat`, `.sh`, and `.ps1` files.

### Core Commands

* **`python manage.py start`**: The "Daily Driver". Checks Docker/Redis, runs an incremental build, and launches the API/Worker.
* **`python manage.py build --clean --parallel 8`**: Forces a clean rebuild using parallel processing.
* **`python manage.py doctor`**: Runs system diagnostics (identifies Zombie files, checks pathing).
* **`python manage.py generate --missing`**: Asynchronously calls AI/Factory to create missing grammars (Decoupled from build).

---

## 3. Level 2: The Optimized Builders 🏗️

These scripts run sequentially under the `build` command. They are refactored for **Speed** (Caching/Parallelism) and **Safety** (Atomic Writes).

### A. The Census Taker (Indexer)

* **Script:** `tools/everything_matrix/build_index.py`
* **Optimization:** **Content Hashing (Caching)**.
* **Logic:**
1. Checks the MD5 checksum of `gf-rgl/` and `data/lexicon/`.
2. **Match:** Loads cached `everything_matrix.json` (0s latency).
3. **Mismatch:** Rescans the file system and updates the index.



### B. The Compiler (Orchestrator)

* **Script:** `builder/orchestrator.py`
* **Optimization:** **Parallel Verification & Single-Shot Linking**.
* **Logic:**
1. **Weighted Topology (Pre-Flight):** Calls `grammar_factory.py` to generate "Safe Mode" grammars for Tier 3 languages (e.g., Zulu, Hausa) using `topology_weights.json`.
2. **Parallel Verification:** Spawns a process pool (e.g., 8 workers) to compile `.gfo` files for all languages simultaneously.
3. **Atomic Writes:** Compiles to a `_temp` directory first. Only valid builds are moved to the final folder, permanently eliminating "Zombie" files.
4. **Single-Shot Link:** Collects *all* valid languages and executes **one single** `gf -make` command to produce the final `semantik_architect.pgf` binary.



---

## 4. Level 3: The Specialists (Hidden Dependencies) 🧠

These are libraries imported by Level 2 to perform complex analysis, generation, or repair.

### A. The Weighted Topology Factory

* **Script:** `utils/grammar_factory.py`
* **Role:** Deterministic Generation (Tier 3).
* **Logic:** Uses `data/config/topology_weights.json` to generate grammatically correct word order (SVO, SOV, VSO) for under-resourced languages without needing AI.

### B. The AI Agent (Architect & Surgeon)

* **Script:** `ai_services/architect.py`
* **Role:** Probabilistic Generation (Tier 3+) & Repair.
* **Refactor:** **Decoupled**.
* No longer called implicitly during the build loop (prevents network timeouts).
* Invoked explicitly via `python manage.py generate`.
* **Architect:** Generates raw GF code from scratch.
* **Surgeon:** Patches broken `.gf` files based on compiler logs.



### C. The Scanners (Auditors)

* **Scripts:** `rgl_auditor.py`, `lexicon_scanner.py`
* **Role:** Quality Scoring.
* **Logic:** analyze RGL coverage and Vocabulary depth to assign a **Maturity Score (0-10)**, enabling the Orchestrator to choose between "High Road" (Tier 1) and "Safe Mode" (Tier 3).

---

## 5. Level 4: The Runtime Services 🔌

Once Level 2 finishes successfully, Level 1 spawns these persistent processes in visible windows.

### A. The API (Brain)

* **Script:** `app/adapters/api/main.py`
* **Framework:** FastAPI + Uvicorn
* **Role:** Handles HTTP requests, manages the Dependency Injection Container, and serves the Swagger UI.

### B. The Worker (Muscle)

* **Script:** `app/workers/worker.py`
* **Framework:** ARQ (Redis)
* **Optimization:** **OS-Native Hot Reload**.
* **Logic:** Uses `watchfiles` (instead of polling) to reload the `semantik_architect.pgf` binary into memory the *instant* the builder updates it.

---

## Data Flow Summary

1. **Filesystem** (Lexicon/RGL) ➔ **Indexer** (Cache Check) ➔ **Matrix JSON**.
2. **Matrix JSON** ➔ **Orchestrator** (Parallel Build) ➔ **Factory** (Tier 3 Gen) ➔ **GF Compiler** ➔ **PGF Binary**.
3. **PGF Binary** ➔ **Worker** (Hot Reload) ➔ **API** (User Request).