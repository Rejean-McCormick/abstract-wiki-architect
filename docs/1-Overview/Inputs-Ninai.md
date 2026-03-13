## 12. Inputs: Ninai

**Ninai** is a **meaning representation**: a structured way to express “what you want to say” before choosing any particular language. In the docs, it’s described as **recursive JSON object trees** (constructor-style structures), not plain text. 

### Why SemantiK Architect supports Ninai

SemantiK Architect uses Ninai as its **interoperability input**: a way to accept rich, language-independent meaning in a form that can be rendered across many languages. This is explicitly part of the v2 pillars (“Ninai Bridge”). 

### How it fits in the product (high level)

* Ninai is the **prototype/experimental input port** into the Renderer (the “UniversalNode / recursive Ninai JSON” path). 
* SemantiK Architect then **maps** that Ninai tree into its internal intent structures (e.g., Bio/Event frames) so it can generate text deterministically. 
* The key conceptual point: Ninai is the **meaning layer**, and Architect is the **renderer** that turns it into text. 

### What Ninai looks like (conceptually)

* A **tree** where each node states a “constructor/function” plus its arguments. 
* Because it’s recursive, the system treats it as a **meaning tree** and walks it (not a string to parse). 

### When to use Ninai vs Frames

* Use **Ninai** when you want: portability, richer semantics, experimentation, and a single meaning structure that can be rendered in many languages. 
* Use **Frames** when you want: a stable, constrained “production” input shape (the docs explicitly separate strict vs prototype paths). 

*(Project note: SemantiK Architect is independent and not affiliated with WMF/Abstract Wiki; Ninai is treated here as an external meaning format that SemantiK Architect can consume.)*
