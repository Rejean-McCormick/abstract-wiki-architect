# builder/orchestrator/config.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# -----------------------------------------------------------------------------
# Repo Root + sys.path
# -----------------------------------------------------------------------------
# builder/orchestrator/config.py -> builder/orchestrator/ -> builder/ -> repo root
ROOT_DIR = Path(__file__).resolve().parents[2]

# Keep legacy robustness: allow importing from repo-root packages like utils/, app/, etc.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# -----------------------------------------------------------------------------
# GF binary
# -----------------------------------------------------------------------------
def resolve_gf_bin(exe: str) -> str:
    """
    Resolve GF binary robustly:
      - absolute path -> keep
      - relative path that exists under repo root -> convert to absolute
      - otherwise -> keep (and rely on PATH)
    """
    exe = (exe or "").strip() or "gf"
    p = Path(exe)

    if p.is_absolute():
        return str(p)

    repo_candidate = (ROOT_DIR / p).resolve()
    if repo_candidate.exists() and repo_candidate.is_file():
        return str(repo_candidate)

    try:
        cwd_candidate = p.resolve()
        if cwd_candidate.exists() and cwd_candidate.is_file():
            return str(cwd_candidate)
    except Exception:
        pass

    return exe


GF_BIN = resolve_gf_bin(os.getenv("GF_BIN", "gf") or "gf")


# -----------------------------------------------------------------------------
# Core directories
# -----------------------------------------------------------------------------
GF_DIR = ROOT_DIR / "gf"
CONTRIB_DIR = GF_DIR / "contrib"  # ADR 006: Human-in-the-Loop overrides

RGL_DIR = ROOT_DIR / "gf-rgl"
RGL_SRC = RGL_DIR / "src"
RGL_API = RGL_SRC / "api"

LOG_DIR = GF_DIR / "build_logs"

MATRIX_FILE = ROOT_DIR / "data" / "indices" / "everything_matrix.json"
ISO_MAP_FILE = ROOT_DIR / "data" / "config" / "iso_to_wiki.json"


# -----------------------------------------------------------------------------
# RGL pinning
# -----------------------------------------------------------------------------
RGL_PIN_FILE = ROOT_DIR / "data" / "config" / "rgl_pin.json"

_ENV_RGL_REF = (
    os.getenv("SEMANTIK_ARCHITECT_RGL_REF")
    or os.getenv("SEMANTIK_ARCHITECT_RGL_COMMIT")
    or ""
).strip()

# Public export used by build.py (compat)
ENV_RGL_REF: str = _ENV_RGL_REF

_ENV_ENFORCE = (os.getenv("SEMANTIK_ARCHITECT_ENFORCE_RGL_PIN", "") or "").strip().lower()

ENFORCE_RGL_PIN: Optional[bool] = None
if _ENV_ENFORCE in ("1", "true", "yes", "on"):
    ENFORCE_RGL_PIN = True
elif _ENV_ENFORCE in ("0", "false", "no", "off"):
    ENFORCE_RGL_PIN = False


# -----------------------------------------------------------------------------
# Generated source locations
# -----------------------------------------------------------------------------
# Canonical is repo_root/generated/src; legacy is repo_root/gf/generated/src.
GENERATED_SRC_ROOT = ROOT_DIR / "generated" / "src"
GENERATED_SRC_GF = GF_DIR / "generated" / "src"

# SAFE_MODE MUST be isolated to avoid reusing stale HIGH_ROAD Wiki*.gf that import SyntaxXXX.
_SAFE_OVERRIDE = (os.getenv("SEMANTIK_ARCHITECT_SAFE_MODE_SRC", "") or "").strip()
if _SAFE_OVERRIDE:
    p = Path(_SAFE_OVERRIDE)
    SAFE_MODE_SRC = (p if p.is_absolute() else (ROOT_DIR / p)).resolve()
else:
    SAFE_MODE_SRC = (ROOT_DIR / "generated" / "safe_mode" / "src").resolve()

SAFE_MODE_MARKER = "-- GENERATED_BY_SEMANTIK_ARCHITECT_SAFE_MODE"

# Default generated location (non-safe-mode)
_GENERATED_OVERRIDE = (os.getenv("SEMANTIK_ARCHITECT_GENERATED_SRC", "") or "").strip()
if _GENERATED_OVERRIDE:
    p = Path(_GENERATED_OVERRIDE)
    GENERATED_SRC_DEFAULT = (p if p.is_absolute() else (ROOT_DIR / p)).resolve()
else:
    GENERATED_SRC_DEFAULT = GENERATED_SRC_ROOT


# -----------------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------------
def ensure_dirs_exist() -> None:
    """
    Create expected directories. Call early in CLI/programmatic entrypoints.
    Kept explicit (not import-time) to reduce side effects in library imports.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CONTRIB_DIR.mkdir(parents=True, exist_ok=True)

    GENERATED_SRC_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_SRC_GF.mkdir(parents=True, exist_ok=True)
    GENERATED_SRC_DEFAULT.mkdir(parents=True, exist_ok=True)
    SAFE_MODE_SRC.mkdir(parents=True, exist_ok=True)