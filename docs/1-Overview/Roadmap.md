# Roadmap — SemantiK Architect

> Formerly “Abstract Wiki Architect”. SemantiK Architect is **independent** and **not affiliated with WMF / Abstract Wiki**.

## Guiding principles
- **Deterministic by default**: normal builds and runtime operation do not rely on automated LLM calls.
- **Human-in-the-loop for hard repairs**: any AI assistance (if enabled) is interactive and reviewable, not an unattended build hook.
- **Quality is enforceable**: improvements must be measurable and protected against regressions (Gold Standard + gating).

---

## Near-term (Wiki v1 scope)

### 1) Product clarity + documentation stabilization
- Publish the **short GitHub Wiki** (Home, Positioning, How it Works, Quality, Using, Dev Notes, Project).
- Align wording across pages on AI usage and determinism (remove contradictions, mark “target contract” vs “current behavior”).
- Normalize naming (“SemantiK Architect”) across UI/docs/repo, and clearly label legacy repo paths/names where they still exist.

### 2) Language onboarding (reliable first pass)
- Make “Add a language” consistently result in a **runnable** language (minimum lexicon seed + basic grammar selection).
- Keep the **Everything Matrix** as the single discovery/health registry that drives the language strategy (tier selection, readiness signals).

### 3) Verifiability baseline
- Establish a **Gold Standard** set for high-signal sentence types and keep gating behavior stable and documented.
- Keep **UD export** usable as a validation surface where applicable.

---

## Execution order (implementation roadmap, simplified)
1. **Foundation**: naming cleanup, configuration cleanup, and a clear “language strategy” registry model.
2. **Deterministic adapters**: stable input adapters (Frames + Ninai) and stable validation/export surfaces (e.g., UD).
3. **Core generation coverage**: ensure Tier 3/fallback coverage is reliable; integrate tier selection cleanly.
4. **Context support**: enable multi-sentence coherence in a controlled, testable way.
5. **Optional AI tools**: keep AI-assisted workflows out of the default build path; improve evaluation tooling and developer experience.

---

## Later (v2 — explicitly out of “simple wiki” scope)
- **Learned micro-planning**: optional pre-render rewriting for style variation (tone, synonym choice) before deterministic rendering.
- **Richer discourse planning**: broader context control beyond basic reference/pronouns.
- **Expanded validation**: broader gold standards, stronger automated regression analysis, and clearer quality dashboards.