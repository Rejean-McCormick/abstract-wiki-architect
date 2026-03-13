# Context

## What “Context” means in SemantiK Architect

Context is the **memory layer** that lets SemantiK Architect move beyond generating isolated sentences and instead produce **coherent multi-sentence text**. In the architecture, it is explicitly the layer responsible for **session state** used for **discourse planning**. 

## Why it exists

Without context, the system repeats full names and produces text that feels unnatural. The docs illustrate this with a two-sentence example where repeating “Marie Curie” is correct but stylistically poor. 
Context exists to address that by tracking which entity is currently “in focus” so the system can choose more natural referring expressions. 

## What it tracks (conceptually)

SemantiK Architect keeps a lightweight “discourse state” that includes:

* **Mentioned entities**
* **Which entity is salient / in focus**
* **Last mention and topic selection signals** 

This is intentionally “light but real”: enough structure to handle multi-sentence needs without adopting a heavy formal discourse/semantics framework. 

## What it enables (user-visible effects)

### 1) Pronominalization (avoiding repetition)

When the subject of the current sentence matches the current “in-focus” entity from the session, the system can replace a repeated name with a pronoun (“Swap Name → Pronoun”). 

### 2) Basic coherence across sentences

Context supports “discourse planning” decisions such as:

* pronouns vs full names,
* topic markers vs default word order,
* basic ordering of information. 

## What Context is *not*

* It is **not** a full semantic/discourse formalism (the docs explicitly reject heavy approaches for the initial implementation). 
* It is **not** “style generation” by itself; it’s a control layer that helps the renderer make consistent choices across sentences.

## How it fits with the rest of the system

* The **Renderer** decides what sentence to produce now.
* **Context** provides the “what has been said / what is in focus” memory so the renderer can produce a better next sentence. 
* The “Summary of Systems” explicitly pairs the discourse planner with **Centering Theory / coreference** as the conceptual grounding. 

## Where this is going (safe, high-level roadmap)

The docs describe future upgrades toward more powerful discourse models for anaphora and topic shifts, enabling longer multi-sentence texts while keeping coherence. 
