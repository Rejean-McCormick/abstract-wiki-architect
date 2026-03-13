# 10. Correctness & Verifiability (Gold Standards, UD Export, Judge)

## Why this matters

SemantiK Architect is designed to scale to **hundreds of languages**, which makes “manual checking” impossible as a primary quality strategy. The system therefore treats correctness as something that must be **measurable, repeatable, and enforceable**. 

## What “verifiable” means here

“Verifiable” means SemantiK Architect doesn’t just generate text—it also produces **checkable evidence** that the output remains consistent and linguistically sound across time and across languages. One key source of high-confidence correctness is the rule-based grammar path (GF/RGL) for high-resource languages, described as providing “verifiable correctness.” 

## The three mechanisms

### 1) UD Export (standards-based validation surface)

SemantiK Architect can export a **Universal Dependencies (UD)** representation (CoNLL-U mapping) so outputs can be validated and compared in a standardized way. The documentation sets a strict rule: every syntactic constructor must have a corresponding UD tag mapping—so validation coverage can’t silently drift. 

### 2) Gold Standards (ground truth expectations)

A “Gold Standard” is a curated set of **verified intent → expected text** pairs used as a regression baseline. Major changes are expected to be validated against this dataset. 
The spec also describes ingesting a test suite as ground truth (migrated from Udiron in the original lineage), reinforcing that Gold Standards are meant to be **externalized, reusable, and stable**. 

### 3) The Judge (automated regression gate)

“The Judge” is the evaluation loop that compares current outputs to Gold Standards and flags regressions. The docs describe a hard gating concept: PRs can be blocked if the Judge score drops below a threshold (0.8 is explicitly mentioned). 
The same quality loop is also described as closing the loop operationally by validating and (optionally) auto-reporting failures. 

## How to interpret failures (high level)

When a regression is detected, it usually points to one of four buckets:

* **Lexicon gap** (missing/incorrect word data),
* **Grammar/realization issue** (wrong structure or morphology),
* **Mapping/validation gap** (UD mapping missing or inconsistent),
* **Renderer/context behavior change** (surface text changed unintentionally).

The purpose of this page in the wiki is to make one idea clear: **SemantiK Architect treats correctness as a first-class product feature, enforced by standards export + gold truth + automated judging**, not as a best-effort manual process. 
