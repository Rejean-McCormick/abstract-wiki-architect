# 🧠 AI Services & Autonomous Agents

**SemantiK Architect v2.5**

## 1. Overview

The SemantiK Architect uses a **Hybrid Intelligence** model.

* **The Core:** Deterministic, Rule-Based Engine (GF/Python). Guarantees grammatical correctness and verifiable output.
* **The Edge:** Probabilistic AI Agents (LLMs). Handles high-entropy tasks like "guessing" a word's gender, grading translation naturalness, or serving as a **copilot** for grammar creation.
* **The Paradigm Shift:** We have moved away from fully autonomous runtime generation in favor of a Human-in-the-Loop (HITL) model. This ensures determinism during builds and prevents API cost drains caused by LLM hallucinations.

These agents are encapsulated in the `ai_services/` package and interact via the developer tools dashboard (`/tools`) or the CLI.

---

## 2. The Four Personas

The architecture delegates responsibilities to four distinct AI agents.

| Agent | Persona | Role | Trigger Event |
| --- | --- | --- | --- |
| **The Lexicographer** | *Data Generator* | Bootstraps dictionaries (`core.json`, `people.json`) for new languages. | `build_index.py` detects `lex_seed < 3`. |
| **The Architect** | *The Copilot* | Generates concrete grammars for missing languages using a "GF Codex". | Invoked manually via `/tools` interface (`ai_refiner`) or `manage.py generate`. |
| **The Surgeon** | *Code Fixer* | Suggests patches for broken `.gf` source files based on compiler error logs. | Manual diagnostic workflows (Removed from automatic build pipeline). |
| **The Judge** | *QA Expert* | Grades the naturalness of the generated text against "Gold Standard" reference sentences. | Scheduled CI/CD or `test_quality.py`. |

---

## 3. Directory Structure & Configuration

All AI logic is centralized to ensure consistent API handling and rate limiting.

```text
ai_services/
├── __init__.py           # Exports the agents
├── client.py             # Central Gemini Client (Auth, Rate Limiting, Backoff)
├── prompts.py            # Frozen System Prompts and GF Codex (Source of Truth)
├── lexicographer.py      # Logic for seeding dictionaries
├── architect.py          # Logic for Generative Grammar Creation (HITL)
├── surgeon.py            # Logic for Self-Healing suggestions
└── judge.py              # Logic for QA & Auto-Ticketing

```

**Environment Variables**
The client requires the following `env` variables (configured in `app/shared/config.py`):

* `GOOGLE_API_KEY`: Your Gemini API Key.
* `AI_MODEL_NAME`: Defaults to `gemini-1.5-pro` (Reasoning optimized).
* `GITHUB_TOKEN`: Required for The Judge to open issues.
* `ARCHITECT_ENABLE_AI_TOOLS`: Must be set to `1` to allow execution of AI-gated tools via the backend router.

---

## 4. Agent Definitions

### A. The Lexicographer (`lexicographer.py`)

**Goal:** Ensure no language has an empty dictionary.

**Workflow:**

1. **Trigger:** The `lexicon_scanner.py` reports a language (e.g., `zul`) has `seed_score: 0`.
2. **Prompting:** The agent receives a list of core concepts ("is", "the", "person", "water").
3. **Generation:** It asks the LLM to generate the JSON entries, including morphological features (e.g., *Zulu noun class prefixes*).
4. **Output:** Writes `data/lexicon/zul/core.json`.

### B. The Architect (`architect.py`) [UPDATED v2.5]

**Goal:** Serve as a human-guided copilot to draft new GF grammars, drastically reducing manual boilerplate.

**Workflow:**

1. **Trigger:** An operator identifies a missing language and launches the interactive `ai_refiner` tool from the developer dashboard (`/tools`).
2. **Prompting:** The tool sends the "GF Codex" and the typological order (SVO, SOV) of the target language to the LLM API.
3. **The GF Codex:** The AI relies on strict context injection including:
* **Anti-Crash Rules:** E.g., The "Inlining Rule" (banning `let` inside `lin`) and the "Symbolic Rule" (banning `mkPN` in favor of `symb` for raw strings).
* **Strict Skeletons:** Mandatory use of `Predicate = VP ;`.
* **Few-Shot Examples:** Perfect templates of validated GF grammars.


4. **Human Validation:** The operator receives the draft, reviews it, and compiles it via `tools/language_health.py --mode compile`.
5. **Output:** Once successfully compiled, the grammar is permanently saved to `gf/contrib/{lang}/Wiki{Lang}.gf` (Manual Overrides).

### C. The Surgeon (`surgeon.py`) [UPDATED v2.5]

**Goal:** Diagnostic assistance for broken grammar code.

**Workflow Changes:**

* The automated AI fallback loop that was previously triggered when compilation failed has been explicitly removed from `builder/orchestrator.py`.
* This removes the "Fire and Pray" instability and endless retry loops during standard build processes.
* The Surgeon is now invoked strictly as an interactive tool by developers trying to patch complex syntax errors.

### D. The Judge (`judge.py`)

**Goal:** Quality Assurance beyond "It compiles."

**Workflow:**

1. **Trigger:** The `test_quality.py` script runs a regression test.
2. **Reference:** It loads the **Gold Standard** dataset from `data/tests/gold_standard.json` (migrated from Udiron).
3. **Comparison:** It compares the SKA generation against the ground truth.
4. **Action:**
* **Pass:** `similarity > 0.8`.
* **Fail:** `similarity < 0.8`.


5. **Whistleblowing:** If it fails with high confidence, it calls the GitHub API to open an issue automatically.

**Issue Template:**

> **Title:** `[QA] Poor Quality: {Lang} - {Frame}`
> **Body:** "Expected 'Shaka is a warrior', got 'Me Shaka warrior'. Confidence: 95%."

---

## 5. Integration Hooks (The Deterministic Pipeline)

Because we have shifted to a Human-in-the-Loop model, the automated `if not compile_success:` AI hooks have been removed from the build orchestrator.

**The New Pipeline Behavior:**

1. **Deterministic Build:** During the regular pipeline (`build_300.py` or `orchestrator.py`), the orchestrator looks for verified files in `contrib/` and links them directly into the `semantik_architect.pgf` binary.
2. **Graceful Degradation:** If a language is broken or missing, the orchestrator simply skips it (`SKIP`) and logs an alert that human intervention is required.
3. **Zero API Calls:** No LLM API calls are made during the build sequence, ensuring 100% determinism and eliminating mid-build latency.

**CI/CD Integration (QA):**
The **Judge** continues to be triggered safely via the test runner:

```bash
# Runs the full regression suite using the Judge Agent
python -m pytest tests/integration/test_quality.py --use-judge

```

---

## 6. Rate Limiting & Cost Control

The `client.py` module implements a robust **Exponential Backoff** strategy to handle API quotas during interactive sessions.

* **Retries:** Max 3 attempts per request.
* **Backoff:** 2s -> 4s -> 8s delay between retries.
* **Circuit Breaker:** If 5 consecutive requests fail, the AI service disables itself to prevent credit drain.
* **Overall Impact:** Moving the Architect to the HITL model drastically reduces overall API costs, as calls are only made once per language rather than on every automated build.

---

## 7. Future Roadmap

* **Learned Micro-Planning:** Using the LLM to rewrite frame parameters (e.g., synonyms) for stylistic variation *before* rendering.