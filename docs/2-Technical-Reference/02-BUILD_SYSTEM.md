

# 🏗️ The Build System & Everything Matrix

**SemantiK Architect v2.1**

## 1. Overview: Data-Driven Orchestration

In a traditional system, you might hardcode a list of supported languages (e.g., `LANGS = ['en', 'fr']`).
In the SemantiK Architect, this is forbidden.

Instead, we use a **Data-Driven Architecture**. The system scans its own file system to discover what languages are available, grades their quality, and dynamically decides how to build them. This "Self-Awareness" is stored in a central registry called the **Everything Matrix**.

### Key Principles

* **No Hardcoding:** The build script does not know that "French" exists until the Matrix tells it.
* **Graceful Degradation:** If a grammar is incomplete (low score), the system automatically downgrades it to "Safe Mode" (Tier 3), utilizing the **Weighted Topology Factory** to ensure valid output.
* **Two-Phase Compilation:** We separate *verification* from *linking* to solve the GF "Last Man Standing" overwriting bug.
* **AI Intervention:** If a build fails, the **Architect Agent** is triggered automatically to attempt code repair.

---

## 2. The Source of Truth: `everything_matrix.json`

The heart of the build system is a JSON file regenerated daily by the scanners.

**Location:** `data/indices/everything_matrix.json`

### The Schema

The matrix tracks the "Health" of every language across distinct zones. Note that the primary keys are **ISO 639-1 (2-letter)** codes.

```json
{
  "timestamp": 1709337600,
  "stats": {
    "total_languages": 75,
    "production_ready": 12
  },
  "languages": {
    "fr": {
      "meta": {
        "iso": "fr",
        "tier": 1,
        "origin": "rgl",
        "folder": "french"
      },
      "blocks": {
        "rgl_grammar": 10,  // Zone A: Grammar Logic
        "rgl_syntax": 10,   // Zone A: Sentence Building
        "lex_seed": 8,      // Zone B: Vocabulary Size
        "lex_wide": 0       // Zone B: Bulk Import status
      },
      "status": {
        "build_strategy": "HIGH_ROAD", // Decisions: HIGH_ROAD vs SAFE_MODE
        "maturity_score": 9.2,
        "data_ready": true
      }
    }
  }
}

```

---

## 3. The Scanning Suite

Before a build occurs, a suite of Python scripts audits the codebase to populate the Matrix. These live in `tools/everything_matrix/`.

### A. The Master Indexer (`build_index.py`)

* **Role:** The Conductor. It initializes the scan, calls the sub-scanners, aggregates the scores, and writes the final JSON file.
* **Command:** `python tools/everything_matrix/build_index.py`

### B. The Grammar Auditor (`rgl_auditor.py`)

* **Role:** Audits **Zone A (The Foundation)**.
* **Logic:** It physically scans the `gf-rgl/src` directory for the 5 Pillars of RGL:
1. `Cat` (Category definitions)
2. `Noun` (Morphology)
3. `Grammar` (Structural Core)
4. `Paradigms` (Constructors)
5. `Syntax` (API)


* **Scoring:**
* **10/10:** All 5 modules exist. (Strategy: `HIGH_ROAD`)
* **< 7/10:** Missing critical modules. (Strategy: `SAFE_MODE`)



### C. The Lexicon Scanner (`lexicon_scanner.py`)

* **Role:** Audits **Zone B (The Vocabulary)**.
* **Logic:** It parses the JSON shards in `data/lexicon/{lang_code}/` (e.g., `data/lexicon/fr/`) to count actual words.
* **Scoring:**
* **0:** No files. (Status: `data_ready = False`)
* **5:** Functional core (< 50 words).
* **10:** Production ready (> 200 words + Wide Import).



---

## 4. The Maturity Scale (0-10)

Every language is assigned a `maturity_score` based on the audit.

| Score | Rating | Meaning | Build Action |
| --- | --- | --- | --- |
| **0 - 2** | 🔴 **Broken** | Critical files missing. | **Skip.** Do not attempt to build. |
| **3 - 5** | 🟡 **Draft** | Auto-generated or incomplete. | **Safe Mode.** Build using **Weighted Topology Factory** (Udiron-style ordering). |
| **6 - 7** | 🔵 **Beta** | Manual implementation, potentially buggy. | **Safe Mode.** Use RGL but verify strictly. |
| **8 - 9** | 🟢 **Stable** | Full RGL support + Lexicon. | **High Road.** Full optimization. |
| **10** | 🌟 **Gold** | Production verified, unit tests pass. | **High Road.** |

---

## 5. The Build Orchestrator (`builder/orchestrator.py`)

This script reads the Matrix and executes the compilation. It solves the critical "Last Man Standing" bug using a **Two-Phase Pipeline** augmented by AI.

### Phase 1: Verification (The "Try" Loop)

The system iterates through every language in the Matrix. It does **not** link them yet. It runs the compiler in "Check Mode" to generate intermediate `.gfo` files.

* **Command:** `gf -batch -c -path ... Wiki{Lang}.gf`
* **Purpose:** To verify that the code *can* compile without actually creating the final binary.

### Phase 1.5: The Architect Loop (Auto-Repair) [NEW]

If Phase 1 fails for a language:

1. **Capture:** The orchestrator captures the GF compiler error log (e.g., `unknown function 'mkN0'`).
2. **Trigger:** It calls the **Architect Agent** with the broken code and the error.
3. **Patch:** The Agent rewrites the `.gf` file to fix the error (e.g., swapping `mkN0` for `mkN`).
4. **Retry:** The system compiles again. (Max Retries: 3).
5. **Drop:** If it still fails after 3 tries, the language is removed from the build list.

### Phase 2: Linking (The "Make" Shot)

Once the list of valid languages is finalized, the orchestrator runs **one single command** to link them all together.

* **Command:** `gf -batch -make -path ... semantik_architect.gf WikiEng.gf WikiFre.gf ...`
* **Purpose:** This produces the multi-lingual `semantik_architect.pgf`.
* **Why:** GF cannot merge PGF files later. All languages must be present in the final Link command to be included in the binary.

---

## 6. How to Run the Pipeline

### Step 1: Audit the System (Update the Matrix)

Run this whenever you add new files or change grammar code.

```bash
# From project root
python tools/everything_matrix/build_index.py

```

* **Output:** `data/indices/everything_matrix.json`

### Step 2: Build the Engine

Run this to compile the PGF binary with AI assistance enabled.

```bash
# Go to gf directory
cd gf
python builder/orchestrator.py

```

* **Output:** `gf/semantik_architect.pgf`
* *Note:* Ensure `GOOGLE_API_KEY` is set in `.env` if you want the Architect Agent to fix errors.

### Step 3: Verify the Binary

Check which languages actually made it into the binary.

```bash
# Quick Python one-liner
python3 -c "import pgf; print(pgf.readPGF('semantik_architect.pgf').languages.keys())"

```

* **Expected:** `['WikiEng', 'WikiFre', 'WikiZul', ...]`

---

## 7. Troubleshooting

### "My language isn't in the binary!"

1. **Check the Matrix:** Open `data/indices/everything_matrix.json`. Does your language exist?
* *No?* Run `build_index.py`.
* *Yes?* Check `build_strategy`. If it is `SKIP`, check the audit logs.


2. **Check Build Logs:** Look at `gf/build_logs/{lang}.log`.
* *Common Error:* `File not found`. This means `rgl_auditor` detected the folder, but the actual `.gf` file path was unresolved.



### "The Architect Agent is consuming too much quota."

* **Cause:** Frequent build failures triggering the repair loop.
* **Fix:** Check `gf/build_logs/`. If a language is fundamentally broken, set its score to 0 manually in the Matrix (or delete the file) to stop the Agent from trying to fix it.

### "Lexicon score is 0 but I added files."

* **Cause:** Your JSON structure might be invalid.
* **Fix:** The `lexicon_scanner.py` requires valid JSON. If `json.load()` fails, it skips the file. Check your syntax.