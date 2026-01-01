# 🧠 AI Services & Autonomous Agents

**Abstract Wiki Architect v2.0**

## 1. Overview

The Abstract Wiki Architect uses a **Hybrid Intelligence** model.

* **The Core:** Deterministic, Rule-Based Engine (GF/Python). Guarantees grammatical correctness and verifiable output.
* **The Edge:** Probabilistic AI Agents (LLMs). Handles high-entropy tasks like "guessing" a word's gender, patching broken code, or grading translation naturalness.

These agents are encapsulated in the `ai_services/` package and interact with the build pipeline via defined hooks.

---

## 2. The Four Personas

The architecture delegates responsibilities to four distinct AI agents.

| Agent | Persona | Role | Trigger Event |
| --- | --- | --- | --- |
| **The Lexicographer** | *Data Generator* | Bootstraps dictionaries (`core.json`, `people.json`) for new languages. | `build_index.py` detects `lex_seed < 3`. |
| **The Architect** | *The Builder* | **[NEW]** Generates entire concrete grammars from scratch for "Factory" (Tier 3) languages. | `builder/orchestrator.py` detects a missing language file. |
| **The Surgeon** | *Code Fixer* | Surgically patches broken `.gf` source files based on compiler error logs. | `builder/orchestrator.py` detects a compilation failure. |
| **The Judge** | *QA Expert* | Grades the naturalness of the generated text against "Gold Standard" reference sentences. | Scheduled CI/CD or `test_gf_dynamic.py`. |

---

## 3. Directory Structure & Configuration

All AI logic is centralized to ensure consistent API handling and rate limiting.

```text
ai_services/
├── __init__.py           # Exports the agents
├── client.py             # Central Gemini Client (Auth, Rate Limiting, Backoff)
├── prompts.py            # [NEW] Frozen System Prompts (Source of Truth)
├── lexicographer.py      # Logic for seeding dictionaries
├── architect.py          # Logic for Generative Grammar Creation
├── surgeon.py            # Logic for Self-Healing build
└── judge.py              # Logic for QA & Auto-Ticketing

```

**Environment Variables**
The client requires the following `env` variables (configured in `app/shared/config.py`):

* `GOOGLE_API_KEY`: Your Gemini API Key.
* `AI_MODEL_NAME`: Defaults to `gemini-1.5-pro` (Reasoning optimized).
* `GITHUB_TOKEN`: Required for The Judge to open issues.

---

## 4. Agent Definitions

### A. The Lexicographer (`lexicographer.py`)

**Goal:** Ensure no language has an empty dictionary.

**Workflow:**

1. **Trigger:** The `lexicon_scanner.py` reports a language (e.g., `zul`) has `seed_score: 0`.
2. **Prompting:** The agent receives a list of core concepts ("is", "the", "person", "water").
3. **Generation:** It asks the LLM to generate the JSON entries, including morphological features (e.g., *Zulu noun class prefixes*).
4. **Output:** Writes `data/lexicon/zul/core.json`.

### B. The Architect (`architect.py`) [NEW]

**Goal:** Automate the creation of Tier 3 (Factory) grammars.

**Workflow:**

1. **Trigger:** `builder/orchestrator.py` finds a language in the Matrix (e.g., `WikiHau.gf`) that does not exist on disk.
2. **Prompting:** It loads the **Frozen System Prompt** from `prompts.py` to ensure non-chatty, code-only output.
3. **Constraint:** The prompt includes the **Weighted Topology** (SVO/SOV) from `topology_weights.json`.
4. **Generation:** The LLM writes the full `concrete WikiHau of AbstractWiki = ...` file.
5. **Output:** Saves to `generated/src/`.

**System Prompt (Snippet):**

> "You are the Abstract Wiki Architect. Output ONLY raw GF code. Do not use Markdown blocks. Implement the 'AbstractWiki' interface using standard RGL modules (Syntax, Paradigms)."

### C. The Surgeon (`surgeon.py`)

**Goal:** The "Self-Healing" Pipeline.

**Workflow:**

1. **Trigger:** `builder/orchestrator.py` fails to compile `WikiZul.gf`.
2. **Analysis:** The Surgeon reads the error log (`Error: variable 'mkN' not found`) and the broken source code.
3. **Patching:** It rewrites the GF code to fix the specific error (e.g., changing `mkN` to `mkN0`).
4. **Verification:** The build is retried (Max 3 attempts).

### D. The Judge (`judge.py`)

**Goal:** Quality Assurance beyond "It compiles."

**Workflow:**

1. **Trigger:** The `test_gf_dynamic.py` script runs a regression test.
2. **Reference:** It loads the **Gold Standard** dataset from `data/tests/gold_standard.json` (migrated from Udiron).
3. **Comparison:** It compares the AWA generation against the ground truth.
4. **Action:**
* **Pass:** `similarity > 0.8`.
* **Fail:** `similarity < 0.8`.


5. **Whistleblowing:** If it fails with high confidence, it calls the GitHub API to open an issue automatically.

**Issue Template:**

> **Title:** `[QA] Poor Quality: {Lang} - {Frame}`
> **Body:** "Expected 'Shaka is a warrior', got 'Me Shaka warrior'. Confidence: 95%."

---

## 5. Integration Hooks

### Build Pipeline Integration

The **Architect** and **Surgeon** are hooked directly into `builder/orchestrator.py`:

```python
# Pseudo-code example of the hook
if not file_exists(path):
    print("🏗️  Calling The Architect...")
    architect.generate_grammar(lang)

if not compile_success:
    print("🚑 Build Failed. Calling The Surgeon...")
    fixed_code = surgeon.attempt_repair(source_code, error_log)
    if fixed_code:
        write_file(path, fixed_code)
        # Retry compilation...

```

### CI/CD Integration

The **Judge** is triggered via the test runner:

```bash
# Runs the full regression suite using the Judge Agent
python -m pytest tests/integration/test_quality.py --use-judge

```

---

## 6. Rate Limiting & Cost Control

The `client.py` module implements a robust **Exponential Backoff** strategy to handle API quotas.

* **Retries:** Max 3 attempts per request.
* **Backoff:** 2s -> 4s -> 8s delay between retries.
* **Circuit Breaker:** If 5 consecutive requests fail, the AI service disables itself for the remainder of the build to prevent credit drain.

---

## 7. Future Roadmap

* **Learned Micro-Planning:** Using the LLM to rewrite frame parameters (e.g., synonyms) for stylistic variation *before* rendering.