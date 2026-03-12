## 22. Changelog

### Unreleased (SemantiK Architect)

* Project renamed from **“Abstract Wiki Architect” → “SemantiK Architect”** (independent project; no WMF/Abstract Wiki affiliation).
* Wiki scope reduced to a simpler v1 (high-level pages first; deeper material postponed).

### v2.5 (Docs baseline: setup/deploy + operator workflow)

* Documented the **Windows + WSL2 hybrid** dev model (Windows for editing/frontend, Linux/WSL for backend + GF), driven by the GF `libpgf` Linux dependency. 
* Standardized prerequisites (WSL2, Ubuntu, Docker Desktop, VS Code WSL extension, Node 18+). 
* Clarified **deployment via docker-compose**, including base-path conventions for UI and versioned API prefix. 
* Formalized config/ops knobs in `.env`, including explicit **AI tool gating**. 

### v2.1 (Architecture and build system clarified/expanded)

* Consolidated the system model as a **4-layer architecture**: Lexicon, Grammar, Renderer, Context. 
* Defined the **dual-path input** (Strict Frames vs Prototype Ninai/UniversalNode) and dual output (Text or UD/CoNLL-U). 
* Codified the **3-tier language strategy** (Tier 1 “High Road”, Tier 2 overrides, Tier 3 weighted-topology factory) for long-tail coverage. 
* Made the build “self-aware” via the **Everything Matrix** (filesystem scanning → maturity scoring → build strategy). 

### v2.0 (Omni-upgrade milestone: expansion beyond sentence-level generation)

* Stated the core shift: from a **sentence-level rule-based engine** to a **context-aware, interoperable, AI-augmented platform**. 
* Introduced the “7 pillars” roadmap: Ninai bridge, UD exporter, discourse planner, automation agent, interactive QA, weighted topology factory, learned micro-planning. 
* Introduced a unified **“Check, Build, Serve”** pipeline and a single operational entry point for developers (`manage.py`). 
* Established the **Everything Matrix** as a dynamic registry replacing static language lists/config. 
