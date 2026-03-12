# Improve a Language (High Level)

SemantiK Architect can generate usable sentences for many languages, but languages are not all supported at the same quality level. “Improving a language” means moving it upward on a quality ladder while keeping output stable, predictable, and buildable.

This page explains the **levers you can pull** (vocabulary, grammar, and QA), and the **typical path** from “it works” to “it feels native”.

---

## 1) The 3 support tiers (how a language is handled)

SemantiK Architect uses a three-tier approach:

- **Tier 1 — High Road (RGL-quality)**
  - Best grammatical quality and richest morphology.
  - Preferred when the language has strong, mature grammar coverage.

- **Tier 2 — Manual Overrides**
  - Community-contributed or project-contributed grammar improvements.
  - Takes precedence when present (it can “override” the other tiers).

- **Tier 3 — Safe Mode (Factory)**
  - A fallback designed to avoid “we don’t support that language”.
  - Prioritizes *always returning a sentence*, even if style/nuance is simpler.

---

## 2) What makes a language “better” in practice

Language quality is usually felt through three things:

### A. Vocabulary coverage (Lexicon)
A language improves quickly when it has the right words available *in the right places*. SemantiK Architect organizes vocabulary in **domain shards** (not one giant dictionary). Typical shards include:
- **core**: the skeleton words you need for almost any sentence (copulas, pronouns, articles, connectors)
- **people**: professions, roles, relations (so biographies sound correct)
- **geography**: countries, demonyms, adjectives
- **science**: specialized terminology

### B. Grammar behavior (how meaning becomes a sentence)
Even with good words, a language needs reliable sentence-building rules:
- Word order that fits the language’s typology
- Agreement and inflection that feels consistent
- Fewer “robotic” constructions as quality rises

Tier 2 contributions (manual overrides) are the typical bridge to make a language feel more natural before it ever becomes Tier 1.

### C. Quality assurance (staying good over time)
A language is “improved” only if it stays improved. QA is how you prevent regressions:
- Reference examples (“gold standard” sentences)
- Regression checks when changing lexicon/grammar
- Clear signals when output quality drops

---

## 3) How SemantiK decides what to do with a language

SemantiK Architect relies on a central inventory (“the brain”) that:
- Discovers what language assets exist
- Scores maturity/readiness
- Decides whether the language should run Tier 1, Tier 2, or Tier 3
- Can downgrade to Safe Mode when a language is too incomplete (to avoid brittle builds)

The key idea: the system is **data-driven**, not a manually curated list of languages.

---

## 4) The improvement loop (recommended workflow)

### Step 1 — Make sure the “skeleton” exists
Start with the minimum vocabulary needed to form basic clauses (core shard). If the language can’t reliably express “X is Y”, everything else will feel broken.

### Step 2 — Make biographies work end-to-end
Biographies are often the first “real” use case. Add/expand:
- professions, roles, relations (people shard)
- nationality and demonyms (geography shard)

### Step 3 — Fix missing words as they surface
When generation fails because a word is missing, treat it as a signal:
- Add the missing entry in the appropriate shard
- Keep shards small and meaningful rather than dumping everything into one file

### Step 4 — Improve grammar feel with Tier 2 (manual overrides)
When output is grammatical but awkward:
- Add targeted manual grammar improvements (Tier 2)
- Focus on the constructions that appear most often (biographies, basic relations, simple events)

### Step 5 — Graduate to Tier 1 where possible
Some languages may eventually rely primarily on Tier 1-quality grammar coverage. This is a longer path, but it’s the highest ceiling.

### Step 6 — Protect the gains with QA
Once a language looks good:
- Add representative examples to your reference set (“gold standard”)
- Use automated checking so “it used to work” doesn’t become a recurring problem

---

## 5) What you can contribute (non-technical categories)

- **Lexicon contributions**
  - Add missing words in the right shard
  - Expand coverage in domains that matter (people/geography first)

- **Grammar contributions**
  - Improve the most-visible sentence patterns first
  - Provide Tier 2 “overrides” that reduce awkward phrasing

- **QA contributions**
  - Add a small set of high-signal reference sentences
  - Track regressions and decide what “good enough” means for each tier

---

## 6) Practical “definition of done” (for a language milestone)

A language can be considered “meaningfully improved” when:
- It reliably generates key sentence types (especially biographies) without missing-word failures
- It has a functional lexicon skeleton plus the main domain shards needed for your targets
- It has at least a minimal QA baseline (so improvements don’t evaporate)

---

## 7) Optional: measuring progress (simple mental model)

Think of progress as:
1) **Coverage** (can we say it?)  
2) **Naturalness** (does it sound right?)  
3) **Durability** (does it stay right after changes?)

Tier 3 gets you coverage fast, Tier 2 improves naturalness, and QA makes it durable.