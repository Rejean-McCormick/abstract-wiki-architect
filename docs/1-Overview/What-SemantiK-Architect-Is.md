## 2. What SemantiK Architect Is

**SemantiK Architect** (renamed from “Abstract Wiki Architect” in these docs) is an **independent** project: a **hybrid Natural Language Generation (NLG) engine** designed to produce **verifiable encyclopedic text** in the **long tail of languages (300+)**. 

### What it does (in one sentence)

It takes a **language-independent intent** and turns it into **natural language text**, with an emphasis on **determinism**, **scalability across many languages**, and **evaluation-ready outputs**.  

### The guiding idea

SemantiK Architect combines:

* A **deterministic, rule-based core** for correctness, and
* **AI-assisted tools at the edges** (copilot/QA/bootstrapping) to scale language coverage without turning generation into free-form “chat text”. 

### The four core “building blocks” (conceptual)

The system is organized as four layers, so each concern stays clear and replaceable:

1. **Lexicon**: words + linguistic properties, grounded to **Wikidata QIDs** for semantic consistency. 
2. **Grammar**: rules for word forms and word order, with a hybrid approach for both high-resource and under-resourced languages. 
3. **Renderer**: the assembly step that converts intent into text and supports multiple input styles. 
4. **Context**: a memory layer to support multi-sentence behavior (e.g., pronouns, discourse continuity). 

### Inputs and outputs (high level)

* **Inputs:**

  * A **strict** structured “frame” for stable production behavior, and
  * A **recursive Ninai-style object tree** for expressive/experimental meaning input.  
* **Outputs:**

  * **Surface text**, and optionally
  * A **Universal Dependencies (CoNLL-U)** representation intended for evaluation/validation workflows.   

### What it is *not*

* Not a knowledge base or encyclopedia: it’s the **rendering engine**, not the source of truth.
* Not a “prompt-and-pray” text generator: it is explicitly **generation-first and structured**. 
* Not affiliated with the WMF/Abstract Wiki team (project note based on your stated context).
