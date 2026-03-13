# 9. Language Coverage Strategy (Tiers)

SemantiK Architect uses a **three-tier strategy** so it can deliver **high quality where possible** and still provide **broad language coverage** (the “long tail”) without blocking on writing perfect grammars for every language. 

## Why tiers exist

* **Tier 1** maximizes linguistic quality (best output).
* **Tier 3** maximizes coverage and robustness (never “no language support”).
* **Tier 2** is the human/community override layer that can improve output without waiting for upstream libraries. 

## The tiers

### Tier 1 — “High Road” (Best quality)

Uses the GF Resource Grammar Library for languages where it’s strong (high-resource languages). 

### Tier 2 — Manual contributions (Overrides)

Community or project-maintained grammars that aren’t in the official RGL yet, but are better than automated stubs. If present, this tier **overrides** both Tier 1 and Tier 3. 

### Tier 3 — “Weighted Factory” (Coverage + safety)

An automated fallback that uses **weighted topology sorting** (adapted from Udiron) so word order can be configured rather than hardcoded templates. The intent is that the system remains usable across many word-order types and **doesn’t fail closed**. 

## How a language’s tier is chosen (at a high level)

A central registry (“Everything Matrix”) audits what exists on disk (grammar readiness, lexicon readiness), assigns a score, and selects a build strategy:

* **High score → Tier 1**
* **Low score → Tier 3** (graceful degradation / “safe mode”) 

This is also the meaning of “Hybrid Factory”: combining expert grammars (Tier 1) with automated simplified grammars (Tier 3) to reach full coverage. 
