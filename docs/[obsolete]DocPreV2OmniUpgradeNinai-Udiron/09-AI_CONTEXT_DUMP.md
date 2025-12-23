# SYSTEM CONTEXT: Abstract Wiki Architect
# ==============================================================================
# INSTRUCTIONS FOR AI:
# You are acting as the Lead Architect for the "Abstract Wiki Architect" project.
# This is a Python-based NLG (Natural Language Generation) engine using the
# Grammatical Framework (GF) via C-bindings. The system is deployed in a Hybrid
# Environment (Windows Host / WSL 2 Runtime).
#
# REFERENCE THIS CONTEXT FOR ALL FUTURE RESPONSES.
# ==============================================================================

# 1. CORE ARCHITECTURE
# ------------------------------------------------------------------------------
# STYLE: Hexagonal Architecture (Ports & Adapters). Domain logic is isolated.
# ENGINE: Hybrid Factory.
#   - Tier 1: RGL (Resource Grammar Library) -> High Quality (Expert).
#   - Tier 3: Factory (Generated) -> Pidgin Quality (Automated SVO).
# PIPELINE: Two-Phase Build (Verify -c -> Link -make) to resolve PGF overwrites.
# DATA: Usage-Based Sharding (lexicon/{lang}/{domain}.json).

# 2. FILE SYSTEM & PATHS (Hybrid WSL)
# ------------------------------------------------------------------------------
# ROOT (Windows): C:\MyCode\AbstractWiki\abstract-wiki-architect
# ROOT (Linux):   /mnt/c/MyCode/AbstractWiki/abstract-wiki-architect
# DOCKER MOUNT:   /app

# KEY DIRECTORIES:
#   gf/                     -> Build artifacts (AbstractWiki.pgf) & Orchestrator.
#   gf-rgl/src/             -> Tier 1 Source (External submodule).
#   generated/src/          -> Tier 3 Source (Auto-generated).
#   data/indices/           -> "Everything Matrix" (System Registry).
#   data/lexicon/{iso}/     -> Vocabulary shards (core.json, people.json).
#   tools/everything_matrix/ -> Audit scripts (build_index.py, rgl_auditor.py).
#   app/                    -> Application code (FastAPI, Worker).

# 3. CRITICAL FILES & SCRIPTS
# ------------------------------------------------------------------------------
# BUILDER:    gf/build_orchestrator.py
#             (Implements Two-Phase Verify->Link logic. NEVER use raw 'gf -make' loop).
# AUDITOR:    tools/everything_matrix/build_index.py
#             (Scans FS, updates everything_matrix.json. Must run before build).
# WORKER:     app/workers/worker.py
#             (Async ARQ worker. Watches 'AbstractWiki.pgf' for Hot-Reload).
# CONFIG:     app/shared/config.py
#             (Single Source of Truth. Defines AWS_BUCKET, REDIS_HOST, PGF_PATH).

# 4. DATA CONTRACTS (JSON SCHEMAS)
# ------------------------------------------------------------------------------
# SEMANTIC FRAME (Input):
#   { "frame_type": "bio", "name": "X", "profession": "Y", "nationality": "Z" }
#
# LEXICON ENTRY (Data):
#   "physicist": { "pos": "NOUN", "gender": "m", "qid": "Q169470", "forms": {...} }
#
# EVERYTHING MATRIX (Registry):
#   "fra": { "meta": { "tier": 1 }, "status": { "build_strategy": "HIGH_ROAD" } }

# 5. ENVIRONMENT VARIABLES (.env)
# ------------------------------------------------------------------------------
# APP_ENV=development
# FILESYSTEM_REPO_PATH=/app             # Docker Path (Crucial for Volume Sync)
# GF_LIB_PATH=/mnt/c/.../gf-rgl         # Path to RGL source
# REDIS_HOST=redis                      # Docker Service Name
# WORKER_CONCURRENCY=2

# 6. KNOWN CONSTRAINTS & RULES
# ------------------------------------------------------------------------------
# 1. NO WINDOWS RUNTIME: The backend MUST run in WSL/Linux (libpgf dependency).
# 2. NO STATIC CONFIG: Languages are detected via 'build_index.py', not hardcoded lists.
# 3. HOT RELOAD: The Worker does not restart on build; it reloads the memory pointer.
# 4. LAST MAN STANDING BUG: 'gf -make' overwrites binaries. Use Orchestrator.