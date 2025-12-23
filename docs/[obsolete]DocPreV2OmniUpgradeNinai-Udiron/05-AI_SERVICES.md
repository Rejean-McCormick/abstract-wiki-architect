# 🧠 AI Services & Autonomous Agents

**Abstract Wiki Architect**

## 1. Overview

The Abstract Wiki Architect uses a **Hybrid Intelligence** model.

* **The Core:** Deterministic, Rule-Based Engine (GF/Python). Guarantees grammatical correctness and verifiable output.
* **The Edge:** Probabilistic AI Agents (LLMs). Handles high-entropy tasks like "guessing" a word's gender, patching broken code, or grading translation naturalness.

These agents are encapsulated in the `ai_services/` package and interact with the build pipeline via defined hooks.

---

## 2. The Three Personas

The architecture delegates responsibilities to three distinct AI agents.

| Agent | Persona | Role | Trigger Event |
| --- | --- | --- | --- |
| **The Lexicographer** | *Data Generator* | Bootstraps dictionaries (`core.json`, `people.json`) for new languages. | `build_index.py` detects `lex_seed < 3`. |
| **The Surgeon** | *Code Fixer* | Surgically patches broken `.gf` source files based on compiler error logs. | `build_orchestrator.py` detects a compilation failure. |
| **The Judge** | *QA Expert* | Grades the naturalness of the generated text against "Gold Standard" reference sentences. | `test_gf_dynamic.py` runs a regression test. |

---

## 3. Directory Structure & Configuration

All AI logic is centralized to ensure consistent API handling and rate limiting.

```text
ai_services/
├── __init__.py           # Exports the agents
├── client.py             # Central Gemini Client (Auth, Rate Limiting, Backoff)
├── lexicographer.py      # Logic for seeding dictionaries
├── surgeon.py            # Logic for Self-Healing build
└── judge.py              # Logic for Linguistic QA

```

**Environment Variables**
The client requires the following `env` variables (configured in `app/shared/config.py`):

* `GOOGLE_API_KEY`: Your Gemini API Key.
* `AI_MODEL_NAME`: Defaults to `gemini-1.5-pro` (Reasoning optimized).

---

## 4. Agent Definitions

### A. The Lexicographer (`lexicographer.py`)

**Goal:** Ensure no language has an empty dictionary.

**Workflow:**

1. **Trigger:** The `lexicon_scanner.py` reports a language (e.g., `zul`) has `seed_score: 0`.
2. **Prompting:** The agent receives a list of core concepts ("is", "the", "person", "water").
3. **Generation:** It asks the LLM to generate the JSON entries, including morphological features (e.g., *Zulu noun class prefixes*).
4. **Output:** Writes `data/lexicon/zul/core.json`.

**Example Prompt:**

> "Act as an expert Zulu linguist. Generate a JSON lexicon entry for the word 'water'. Include part of speech and noun class."

### B. The Surgeon (`surgeon.py`)

**Goal:** The "Self-Healing" Pipeline.

**Workflow:**

1. **Trigger:** `build_orchestrator.py` fails to compile `WikiZul.gf`.
2. **Analysis:** The Surgeon reads the error log (`Error: variable 'mkN' not found`) and the broken source code.
3. **Patching:** It rewrites the GF code to fix the specific error (e.g., changing `mkN` to `mkN0`).
4. **Verification:** The build is retried.

### C. The Judge (`judge.py`)

**Goal:** Quality Assurance beyond "It compiles."

**Workflow:**

1. **Trigger:** The `test_gf_dynamic.py` script generates a sentence: *"Shaka is a warrior."*
2. **Evaluation:** The Judge compares this against the internal logic or a "Gold Standard" translation.
3. **Scoring:** It returns a JSON verdict:
```json
{
  "valid": true,
  "score": 9,
  "critique": "Grammatically correct, but 'warrior' could be more specific."
}

```



---

## 5. Integration Hooks

### Build Pipeline Integration

The **Surgeon** is hooked directly into `gf/build_orchestrator.py`:

```python
# Pseudo-code example of the hook
if not success:
    print("🚑 Build Failed. Calling The Surgeon...")
    from ai_services.surgeon import attempt_repair
    
    fixed_code = attempt_repair(source_code, error_log)
    if fixed_code:
        write_file(path, fixed_code)
        # Retry compilation...

```

### Data Pipeline Integration

The **Lexicographer** is triggered manually or by the `build_index.py` audit:

```bash
# Manual Trigger
python -m ai_services.lexicographer --lang=zul --domain=core

```

---

## 6. Rate Limiting & Cost Control

The `client.py` module implements a robust **Exponential Backoff** strategy to handle API quotas.

* **Retries:** Max 3 attempts per request.
* **Backoff:** 2s -> 4s -> 8s delay between retries.
* **Circuit Breaker:** If 5 consecutive requests fail, the AI service disables itself for the remainder of the build to prevent credit drain.

---

## 7. Future Roadmap

* **The Architect Agent:** A higher-level agent capable of writing entire `GrammarX.gf` files from scratch for new languages, effectively automating the "Factory" tier.
* **Interactive QA:** A feedback loop where the **Judge** automatically opens GitHub Issues for low-scoring languages.