# Outputs: Text

## What “Text” output is

SemantiK Architect’s primary output is **natural language surface text**: the human-readable sentence(s) you would display in a UI, store, or publish. In the engine architecture, the Renderer’s output port is explicitly **“Natural Language Text”** (alongside an optional UD/CoNLL-U output). 

This output is intended to be **encyclopedic**, and the system is framed around producing **verifiable, high-quality encyclopedic text** across **300+ languages**. 

## What you receive (conceptual response envelope)

When you request generation, the response includes:

* **`surface_text`**: the generated text string (the thing you display)
* **`meta`**: minimal provenance about how that string was produced (engine/adapter/strategy), useful for debugging and QA—not required for basic usage. 

## What shapes the text output (high level)

### 1) Grammar realization (quality when available)

Where strong grammars exist, the system relies on rule-based realization (GF linearization into concrete strings) to produce well-formed text. 

### 2) Coverage strategy (consistent output across many languages)

SemantiK Architect is designed to keep producing usable text even when a language has limited handcrafted grammar support (via its tiered/hybrid approach). 

### 3) Context (when generating more than one sentence)

If you generate text in a session, the Context layer can influence surface text choices (e.g., avoiding repetition via pronouns), because it exists specifically to manage discourse state. 

## Relationship to UD output (optional)

Text is the “publishable” output; UD/CoNLL-U is an **optional companion output** meant to support verification and evaluation. The system treats both as first-class output ports. 
