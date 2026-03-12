# 15. Add a Language (High Level)

## Goal

Bring a new language online with a **minimal, runnable** generation path first, then iterate toward higher quality using the project’s maturity signals.

SemantiK Architect treats “language support” as a **measured state** (not a checkbox): the system computes per-language maturity and uses it to decide what is runnable and which strategy to use (high-quality vs safe-mode).

---

## Step 1 — Choose an initial quality path (Tier choice)

Pick the best available strategy for the language:

- **Tier 1 (High quality):** choose this when the language already has strong, mature grammar support (e.g., a robust GF/RGL-class path).
- **Tier 3 (Guaranteed availability / Safe Mode):** choose this for under-resourced languages so the language is available quickly via the **weighted topology / factory** approach, then improve later.
- **Tier 2 (Manual overrides):** use this as the bridge when you want to improve phrasing/behavior for a specific language without waiting for full Tier 1 coverage.

---

## Step 2 — Create the language “home” (language code and identity)

Use a **two-letter ISO-2 code** as the **internal language key** (folder names, core data identity, and internal registry expectations).

Important nuance:
- **Internal identity** is ISO-2 (the consistent key the system reasons about).
- **External/public identifiers** (if you expose them) may require explicit mapping and do not have to be “ISO-2 everywhere.”

---

## Step 3 — Seed the minimum Lexicon so the language is runnable

A language becomes runnable only when it clears a minimum **lexicon maturity** threshold.

Minimal expectations (example policy):
- **Minimal:** `core.json` exists and contains enough entries to generate basic sentences.
- **Functional:** adds essential domain shards (often starting with `people` for biographies).

Bootstrapping workflow (high level):
1. Create the language lexicon directory.
2. Seed `core.json` (manually or with helper tooling).
3. Run an audit/index step so the system discovers the new language.

Guardrail:
- If the “core seed” is too small, the system should treat the language as **non-runnable** to avoid brittle generation paths.

Optional:
- A “lexicon bootstrapper”/helper can generate a starter `core.json` specifically to prevent “empty dictionary” languages.

---

## Step 4 — Register + audit via the Everything Matrix (no hardcoded lists)

Do **not** hardcode language lists.

The rule is:
- **Create the expected file structure**, then
- Let the indexing/audit step pick up the language and compute maturity.

The Matrix acts as the “central nervous system” for autonomous decisions (e.g., whether to run Tier 1 or fall back to safe-mode).

---

## Step 5 — Add at least one correctness checkpoint (so it can’t silently regress)

“Done” is not “it compiles.” Add at least one baseline check that can fail if quality regresses.

Minimum recommendation:
- Add **one gold-standard example** for the language and ensure the automated evaluator (“Judge”) runs it.

Project policies sometimes use a similarity threshold (e.g., **0.8**) to block regressions; treat the exact number as a project-level policy that can evolve.

If your language work introduces new factory-path constructions, keep the **validation/export mapping** (e.g., UD view) aligned so the output remains auditable.

---

## Definition of “done” (for a first PR)

A new language is “added” when:

- It exists under the **internal ISO-2 key** (with any external mapping handled explicitly if needed)
- It has at least a **minimal lexicon seed** that makes it runnable
- It is discovered by the **Everything Matrix** audit/index step
- It has at least **one gold-standard case** so quality can be tracked over time