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

# Allow importing repo-root packages like utils/, app/, etc.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# -----------------------------------------------------------------------------
# Helpers
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


def _resolve_project_path(raw: str, *, default: Path) -> Path:
    raw = (raw or "").strip()
    if not raw:
        return default.resolve()
    p = Path(raw)
    return (p if p.is_absolute() else (ROOT_DIR / p)).resolve()


def _legacy_generated_root() -> Path:
    return (ROOT_DIR / "gf" / "generated").resolve()


def _assert_not_legacy_generated(path: Path, *, env_name: str) -> Path:
    legacy_root = _legacy_generated_root()
    try:
        if path == legacy_root or legacy_root in path.parents:
            raise ValueError(
                f"{env_name} points to legacy generated path '{path}'. "
                f"Use '{(ROOT_DIR / 'generated' / 'src').resolve()}' or "
                f"'{(ROOT_DIR / 'generated' / 'safe_mode' / 'src').resolve()}'."
            )
    except RuntimeError:
        # Very defensive: if parents cannot be resolved cleanly, still reject
        if str(path).lower().startswith(str(legacy_root).lower()):
            raise ValueError(
                f"{env_name} points to legacy generated path '{path}'."
            )
    return path


# -----------------------------------------------------------------------------
# GF binary
# -----------------------------------------------------------------------------
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
    os.getenv("ABSTRACTWIKI_RGL_REF")
    or os.getenv("ABSTRACTWIKI_RGL_COMMIT")
    or ""
).strip()

# Public export used by build.py (compat)
ENV_RGL_REF: str = _ENV_RGL_REF

_ENV_ENFORCE = (os.getenv("ABSTRACTWIKI_ENFORCE_RGL_PIN", "") or "").strip().lower()

ENFORCE_RGL_PIN: Optional[bool] = None
if _ENV_ENFORCE in ("1", "true", "yes", "on"):
    ENFORCE_RGL_PIN = True
elif _ENV_ENFORCE in ("0", "false", "no", "off"):
    ENFORCE_RGL_PIN = False


# -----------------------------------------------------------------------------
# Generated source locations
# -----------------------------------------------------------------------------
# Straight-only layout:
#   canonical generated bridge grammars  -> repo_root/generated/src
#   safe-mode generated grammars         -> repo_root/generated/safe_mode/src
#
# Legacy path repo_root/gf/generated/src is intentionally unsupported.
GENERATED_SRC_ROOT = (ROOT_DIR / "generated" / "src").resolve()

_SAFE_OVERRIDE = _resolve_project_path(
    os.getenv("ABSTRACTWIKI_SAFE_MODE_SRC", ""),
    default=ROOT_DIR / "generated" / "safe_mode" / "src",
)
SAFE_MODE_SRC = _assert_not_legacy_generated(
    _SAFE_OVERRIDE,
    env_name="ABSTRACTWIKI_SAFE_MODE_SRC",
)

SAFE_MODE_MARKER = "-- GENERATED_BY_ABSTRACTWIKI_SAFE_MODE"

_GENERATED_OVERRIDE = _resolve_project_path(
    os.getenv("ABSTRACTWIKI_GENERATED_SRC", ""),
    default=GENERATED_SRC_ROOT,
)
GENERATED_SRC_DEFAULT = _assert_not_legacy_generated(
    _GENERATED_OVERRIDE,
    env_name="ABSTRACTWIKI_GENERATED_SRC",
)


# -----------------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------------
def ensure_dirs_exist() -> None:
    """
    Create expected directories. Call early in CLI/programmatic entrypoints.
    Kept explicit (not import-time) to reduce side effects in library imports.
    """
    dirs = {
        LOG_DIR.resolve(),
        CONTRIB_DIR.resolve(),
        GENERATED_SRC_ROOT.resolve(),
        GENERATED_SRC_DEFAULT.resolve(),
        SAFE_MODE_SRC.resolve(),
    }

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)