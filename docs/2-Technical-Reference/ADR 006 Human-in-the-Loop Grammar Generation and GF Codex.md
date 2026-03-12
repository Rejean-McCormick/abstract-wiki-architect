# ADR 006: Human-in-the-Loop (HITL) Grammar Generation & GF Codex

**Status:** Accepted

**Date:** February 2026

**Context:** SemantiK Architect v2.5

## 1. Context and Problem Statement

In the v2.0 architecture, the Architect Agent was designed to autonomously generate grammars for under-resourced languages (Tier 3) at compile time (Runtime Auto-Generation). While functional in theory, this approach revealed critical limitations in production:

* **Probabilistic Instability ("Fire and Pray"):** Generating Grammatical Framework (GF) code via LLMs often produces complex typing errors. The "Surgeon" agent sometimes loops endlessly without successfully patching the strict syntax errors enforced by the GF C-compiler.
* **Cost and Latency (Financial Drain):** Repeated attempts (retry loops) with the Gemini API upon every compilation failure consume excessive credits and significantly slow down the build pipeline.
* **Finite Scope:** The number of target languages for Wikipedia is not infinite (approximately 300 languages). Dynamic, "blind" automation on every build is disproportionate to the actual need, which is simply to generate a static file permanently.

## 2. The Decision

We are abandoning fully autonomous runtime generation in favor of a **Human-in-the-Loop (HITL)** model. The AI is no longer an "autonomous builder" but a **copilot**, guided by a human operator using a strict instruction manual called the **"GF Codex"**.

Grammars generated this way and validated by a human will now be permanently stored in `gf/contrib/{lang}/` (Tier 2 - Manual Overrides), rather than the ephemeral `gf/generated/src/` folder.

## 3. The "GF Codex" (RAG / Few-Shot Context Injection)

To ensure high-quality code on the first attempt, requests to the LLM will no longer rely on a simple static prompt. Instead, they will include a comprehensive "GF Codex." This reference document will contain:

1. **Anti-Crash Rules (Implementation Rules):**
* *The Inlining Rule:* Absolute prohibition of using `let` variables inside `lin` blocks to prevent the `variable #0 is out of scope` error.
* *The Symbolic Rule:* Mandatory use of `symb` for raw strings instead of `mkPN` to prevent `unsupported token gluing` errors.


2. **Strict Skeletons:** Strict definition of the types imposed by `semantik_architect.gf` (e.g., mandatory use of `Predicate = VP ;` and an absolute ban on hallucinating `VPS`).
3. **"Few-Shot" Examples:** Perfect templates of validated GF grammars (e.g., one SVO model, one SOV model) to guide the AI's coding style.

## 4. The New Deployment Workflow

1. **Initialization:** The operator identifies a missing language and launches the interactive `ai_refiner` tool from the developer dashboard (`/tools`).
2. **Generation (Copilot):** The tool sends the "GF Codex" and the typological order (SVO, SOV) of the target language to the LLM API.
3. **Human Validation:** The operator receives the GF draft, reviews it, and uses `tools/language_health.py --mode compile` to ensure the code compiles perfectly with the RGL library.
4. **Save & Commit:** Once the file compiles successfully, it is manually pushed to the repository under `gf/contrib/{lang}/Wiki{Lang}.gf`.
5. **Deterministic Build:** During the regular pipeline (`build_300.py` / `orchestrator.py`), the orchestrator detects the file in `contrib/` and links it directly into the `semantik_architect.pgf` binary without making any API calls.

## 5. Consequences

| Impact | Description |
| --- | --- |
| **Positive** | **Drastic API Cost Reduction:** LLM calls are only made once per language, entirely outside the daily build pipeline. |
| **Positive** | **Build Stability:** The build pipeline becomes 100% deterministic again. Unexpected errors caused by AI hallucinations during compilation are eliminated. |
| **Positive** | **Quality Increase:** Human review guarantees that the grammar makes linguistic sense before it reaches production. |
| **Negative** | **Operational Friction:** Adding a new language now requires human intervention (this trade-off is deemed highly acceptable given the finite limit of ~300 languages). |

---

### 💡 Recommended Code Updates:

1. **In `05-AI_SERVICES.md**`: Update the section on "The Architect" to specify that it is now a tool invoked manually via the `/tools` interface, rather than automatically triggered by `orchestrator.py`.
2. **In `builder/orchestrator.py**`: Remove the AI fallback loop (The Surgeon) triggered when compilation fails. The orchestrator should simply skip the broken/missing language (`SKIP`) and log an alert that human intervention is required.