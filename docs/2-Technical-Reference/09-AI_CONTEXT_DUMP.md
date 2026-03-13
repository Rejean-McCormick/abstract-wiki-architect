# SYSTEM CONTEXT: SemantiK Architect v2.0 ("Omni-Upgrade")
# ==============================================================================
# INSTRUCTIONS FOR AI:
# You are acting as the Lead Architect for the "SemantiK Architect" project.
# This is a Hybrid Neuro-Symbolic NLG Engine combining:
#   1. Grammatical Framework (GF) -> Deterministic Rule-Based Core.
#   2. Ninai Protocol -> Recursive Abstract Syntax Input.
#   3. AI Agents (LLMs) -> Autonomous Code Repair & Grammar Generation.
#
# REFERENCE THIS CONTEXT FOR ALL FUTURE RESPONSES.
# ==============================================================================

# 1. CORE ARCHITECTURE
# ------------------------------------------------------------------------------
# STYLE: Hexagonal Architecture (Ports & Adapters).
# INPUT PORTS:
#   - Semantic Frame (Internal Flat JSON).
#   - Ninai Protocol (External Recursive JSON Object Tree).
# ENGINE: Hybrid Factory.
#   - Tier 1: RGL (Resource Grammar Library) -> High Quality (Expert).
#   - Tier 3: Weighted Topology (Udiron-based) -> Automated Linearization.
# STATE: Redis-backed "Discourse Planner" (SessionContext) for Pronominalization.
# OUTPUT PORTS: Text (String) and Universal Dependencies (CoNLL-U).
# PIPELINE: Two-Phase Build (Verify -> Link) + Architect Agent Repair Loop.

# 2. FILE SYSTEM & PATHS (Hybrid WSL)
# ------------------------------------------------------------------------------
# ROOT (Windows): C:\MyCode\SemantiK_Architect\Semantik_architect
# ROOT (Linux):   /mnt/c/MyCode/SemantiK_Architect/Semantik_architect
# DOCKER MOUNT:   /app

# KEY DIRECTORIES:
#   gf/                     -> Build artifacts (semantik_architect.pgf) & Orchestrator.
#   gf-rgl/src/             -> Tier 1 Source (External submodule).
#   generated/src/          -> Tier 3 Source (AI/Factory generated).
#   data/indices/           -> "Everything Matrix" (System Registry).
#   data/lexicon/{iso}/     -> Vocabulary shards (core.json, people.json).
#   data/config/            -> Topology Weights (SVO/SOV definitions).
#   data/tests/             -> Gold Standard QA Data (migrated from Udiron).
#   app/adapters/           -> Ninai Bridge, API, Redis Bus.
#   ai_services/            -> Autonomous Agents (Architect, Judge, Surgeon).

# 3. CRITICAL FILES & SCRIPTS
# ------------------------------------------------------------------------------
# BUILDER:     builder/orchestrator.py
#              (Runs Verify->Link loop. Triggers 'Architect Agent' on failure).
# FACTORY:     utils/grammar_factory.py
#              (Implements Weighted Topology sorting for Tier 3).
# AUDITOR:     tools/everything_matrix/build_index.py
#              (Scans FS, updates everything_matrix.json).
# NINAI:       app/adapters/ninai.py
#              (Recursive JSON parser for Ninai Object Model).
# MAPPING:     app/core/exporters/ud_mapping.py
#              (Frozen Dictionary mapping RGL functions to UD Tags).
# QA:          ai_services/judge.py
#              (Validates output against 'gold_standard.json').

# 4. DATA CONTRACTS (JSON SCHEMAS)
# ------------------------------------------------------------------------------
# NINAI INPUT (Recursive):
#   { "function": "ninai.constructors.Statement", "args": [...] }
#
# SEMANTIC FRAME (Internal):
#   { "frame_type": "bio", "name": "X", "profession": "Y", "context_id": "UUID" }
#
# SESSION CONTEXT (Redis):
#   { "session_id": "UUID", "current_focus": { "qid": "Q1", "gender": "f" } }
#
# TOPOLOGY WEIGHTS (Config):
#   { "SOV": { "nsubj": -10, "obj": -5, "root": 0 } }

# 5. ENVIRONMENT VARIABLES (.env)
# ------------------------------------------------------------------------------
# APP_ENV=development
# REDIS_URL=redis://redis:6379/0          # Replaces old REDIS_HOST
# SESSION_TTL_SEC=600                     # Context duration
# GITHUB_TOKEN=ghp_...                    # For Judge Agent Auto-Ticketing
# GOOGLE_API_KEY=AIza...                  # For Architect/Surgeon Agents
# REPO_URL=https://github.com/...         # Target for Issue Creation

# 6. KNOWN CONSTRAINTS & RULES
# ------------------------------------------------------------------------------
# 1. NO WINDOWS RUNTIME: Backend MUST run in WSL/Linux (libpgf dependency).
# 2. VARIABLE LEDGER: Use strict variable names from 'docs/14-VAR_FIX_LEDGER.md'.
# 3. FROZEN PROMPTS: Do not invent LLM prompts. Use 'ai_services/prompts.py'.
# 4. NINAI PROTOCOL: Input is Object-Based (JSON), NOT Lisp-String based.
# 5. NO HARDCODED GRAMMAR: Use 'topology_weights.json' for word order.