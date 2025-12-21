# 🤝 Contributing to Abstract Wiki Architect

Thank you for your interest in contributing! This project is a complex **Hybrid Architecture** (Python/WSL + C/Linux), so we enforce strict guidelines to prevent "Works on my machine" issues.

## 1. The Golden Rules

1.  **Never Edit Generated Files:** Do not manually edit `gf/AbstractWiki.gf` or `gf/WikiI.gf`. These are overwritten by `build_orchestrator.py`.
2.  **Respect the Matrix:** Do not hardcode language lists in Python. If you add a language, register it by creating the file structure and running `tools/everything_matrix/build_index.py`.
3.  **Linux Runtime Only:** The backend depends on `libpgf` (C-library). Do not try to run `uvicorn` or `worker.py` directly on Windows. Use WSL 2 or Docker.

---

## 2. Development Workflow

### Adding a New Language
1.  **Tier 1 (High Quality):** Ensure the language exists in `gf-rgl/src`.
2.  **Tier 3 (Factory):** Add the config to `utils/grammar_factory.py`.
3.  **Lexicon:** Create `data/lexicon/{code}/core.json`.
4.  **Audit:** Run `python tools/everything_matrix/build_index.py`.
5.  **Build:** Run `python gf/build_orchestrator.py`.

### Reporting Bugs
* **Label:** Use `[Engine]` for GF/PGF issues, `[API]` for FastAPI issues, and `[Matrix]` for scanner issues.
* **Context:** Always include the `trace_id` from the logs if reporting a worker failure.

---

## 3. Coding Standards

### Python (Backend)
* **Style:** We use `black` for formatting.
* **Typing:** Strict type hints (`mypy`) are required for all `app/core` logic.
* **Hexagonal:** Domain logic (`app/core`) must **never** import from `app/adapters`.

### GF (Grammar)
* **Naming:** Concrete grammars must be named `Wiki{Lang}.gf` (e.g., `WikiZul.gf`).
* **Paradigm:** Use `open Syntax` and `open Paradigms` standard libraries.

---

## 4. Commit Messages

We follow the **Conventional Commits** specification:

* `feat: add Zulu language support (Tier 3)`
* `fix: resolve PGF overwriting bug in orchestrator`
* `docs: update deployment guide for WSL 2`
* `chore: regenerate everything matrix`

---

## 5. Hot-Reloading Note

The `aw_worker` service watches the `AbstractWiki.pgf` file. If you run a build, wait ~5 seconds for the logs to show:
> `runtime_detected_file_change ... runtime_reloading_triggered`

If this doesn't happen, check that your Docker volumes are correctly mounted to `/app`.