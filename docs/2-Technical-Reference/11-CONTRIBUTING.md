# 🤝 Contributing to SemantiK Architect v2.0

Thank you for your interest in contributing! This project is a complex **Hybrid Neuro-Symbolic Architecture** (Python/WSL + C/Linux + AI Agents), so we enforce strict guidelines to prevent "Works on my machine" issues.

## 1. The Golden Rules

1. **Never Edit Generated Files:** Do not manually edit files in `generated/src/`. These are overwritten by the **Architect Agent** and `builder/orchestrator.py`.
2. **Respect the Matrix:** Do not hardcode language lists in Python. If you add a language, register it by creating the file structure and running `tools/everything_matrix/build_index.py`.
3. **Linux Runtime Only:** The backend depends on `libpgf` (C-library). Do not try to run `uvicorn` or `worker.py` directly on Windows. Use WSL 2 or Docker.
4. **No Chatty AI:** If you modify the **Architect Agent**, you must strictly adhere to the **Frozen System Prompt** (`ai_services/prompts.py`) to ensure it outputs raw code, not Markdown.

---

## 2. Development Workflow

### Adding a New Language (The v2.0 Way)

1. **Tier 1 (High Quality):** Ensure the language exists in `gf-rgl/src`.
2. **Tier 3 (Factory):**
* Add the language code and `order` (e.g., SVO, SOV) to `utils/grammar_factory.py`.
* Verify the **Topology Weights** exist in `data/config/topology_weights.json`.


3. **Lexicon:**
* Run `python -m ai_services.lexicographer --lang={code}` to bootstrap `core.json`.


4. **Audit:** Run `python tools/everything_matrix/build_index.py`.
5. **Build:** Run `python builder/orchestrator.py`. (The **Architect Agent** will wake up and write the grammar for you).

### Reporting Bugs

* **Label:** Use `[Engine]` for GF/PGF issues, `[API]` for FastAPI, `[Matrix]` for scanners, and `[AI]` for agent hallucinations.
* **Context:** Always include the `trace_id` and the **Session ID** if the bug involves Pronominalization/Context.

---

## 3. Coding Standards

### Python (Backend)

* **Style:** We use `black` for formatting.
* **Typing:** Strict type hints (`mypy`) are required for all `app/core` logic.
* **Hexagonal:** Domain logic (`app/core`) must **never** import from `app/adapters`.
* **Variables:** Use the **Frozen Ledger** (`docs/14-VAR_FIX_LEDGER.md`) for all shared constants.

### GF (Grammar)

* **Naming:** Concrete grammars must be named `Wiki{Lang}.gf` (e.g., `WikiZul.gf`).
* **Paradigm:** Use `open Syntax` and `open Paradigms` standard libraries.

### AI Agents

* **Prompts:** Do not hardcode prompts in the agent logic. Import them from `ai_services/prompts.py`.
* **Cost Control:** Ensure your agent logic respects the `MAX_RETRIES` defined in `client.py`.

---

## 4. Standards Compliance (Ninai & UD)

### Ninai Protocol

* If you touch `app/adapters/ninai.py`, ensure you support the **Recursive Object Model**.
* **Do not** revert to regex parsing. Use the `_walk_tree` recursion pattern.

### Universal Dependencies

* If you add a new RGL function to `grammar_factory.py`, you **MUST** add its mapping to `app/core/exporters/ud_mapping.py`.
* **Rule:** Every syntactic constructor must have a corresponding CoNLL-U tag map.

---

## 5. Quality Assurance (The Judge)

We require **Gold Standard Validation** for all major PRs.

1. **Add Test Case:** Add a verified intent/text pair to `data/tests/gold_standard.json`.
2. **Run Judge:** `python -m pytest tests/integration/test_quality.py --use-judge`.
3. **Pass Criteria:** Your PR will be blocked if the Judge's similarity score drops below **0.8** for existing languages.

---

## 6. Commit Messages

We follow the **Conventional Commits** specification:

* `feat: add Zulu language support (Tier 3)`
* `fix: resolve PGF overwriting bug in orchestrator`
* `docs: update deployment guide for WSL 2`
* `ai: optimize Architect Agent system prompt`
* `test: add gold standard case for Hausa`

---

## 7. Hot-Reloading Note

The `aw_worker` service watches the `semantik_architect.pgf` file. If you run a build, wait ~5 seconds for the logs to show:

> `runtime_detected_file_change ... runtime_reloading_triggered`

If this doesn't happen, check that your Docker volumes are correctly mounted to `/app`.