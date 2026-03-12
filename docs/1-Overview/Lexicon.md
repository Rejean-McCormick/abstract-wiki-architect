# 5. Lexicon

## What the Lexicon is

The Lexicon is SemantiK Architect’s **vocabulary layer**: the words (and key linguistic properties) the system needs to express meaning in a specific language. It is designed to support **300+ languages** without becoming a single unmaintainable dictionary. 

## Core principles

* **Grounded meaning:** entries are traced back to **Wikidata QIDs** so terms stay anchored to stable identifiers (provenance + alignment). 
* **Usage-based sharding:** vocabulary is split into **domain shards** so the engine can load only what it needs for the current context (instead of loading “everything”). 
* **Strict validation:** every entry must follow a schema so generation doesn’t fail because a required property (e.g., grammatical gender) is missing. 

## How it’s organized (human-friendly mental model)

* **One namespace per language**, using **ISO 639-1 two-letter codes**. 
* Inside each language, the Lexicon is split into a few **semantic domains** (files) that match real generation needs: 

  * **core**: “skeleton” function words needed to build any sentence (highest priority). 
  * **people**: terms used for biographies (professions, relations, titles). 
  * **geography**: countries/places and derived forms (adjectives, demonyms). 
  * **science**: specialized terminology (grows over time). 

## Why this matters operationally (readiness scoring)

SemantiK Architect treats Lexicon coverage as a measurable readiness signal (“Zone B”): a scanner counts words in these shards to grade whether a language is **data-ready** (from “no files” to “production-ready”). 

## Typical workflows (high level)

* **Bootstrap a new language:** start with **core** first (so basic sentences are possible), then add **people/geography** for biographies. 
* **Grow coverage from Wikidata:** use Wikidata as the upstream source for translations and QID provenance, then store locally in the right domain shard. 
* **Fix “missing word” issues:** add the missing term to the appropriate shard (often **people** for biographies), keeping schema-valid entries. 
