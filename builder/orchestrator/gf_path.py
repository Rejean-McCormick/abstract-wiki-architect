# builder/orchestrator/gf_path.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from . import config


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _safe_resolve(p: Path) -> Path:
    try:
        return p.resolve()
    except Exception:
        return p


def _safe_is_dir(p: Path) -> bool:
    try:
        return p.exists() and p.is_dir()
    except Exception:
        return False


def discover_rgl_lang_dirs() -> List[Path]:
    """
    GF does not recurse into directories in -path.
    Include all first-level dirs under gf-rgl/src that contain any .gf file somewhere inside.
    """
    rgl_src = config.RGL_SRC
    if not _safe_is_dir(rgl_src):
        return []

    def has_gf_files(d: Path) -> bool:
        try:
            for _ in d.rglob("*.gf"):
                return True
        except Exception:
            return False
        return False

    dirs: List[Path] = []
    try:
        entries = sorted(rgl_src.iterdir(), key=lambda x: x.name)
    except Exception:
        return []

    for p in entries:
        if not _safe_is_dir(p):
            continue
        if p.name == "api":
            continue
        if has_gf_files(p):
            dirs.append(_safe_resolve(p))
    return dirs


def discover_contrib_dirs() -> List[Path]:
    """Find all language subdirectories inside gf/contrib/ (ADR 006)."""
    contrib = config.CONTRIB_DIR
    if not _safe_is_dir(contrib):
        return []

    out: List[Path] = []
    try:
        for p in contrib.iterdir():
            if _safe_is_dir(p):
                out.append(_safe_resolve(p))
    except Exception:
        return []
    return out


def generated_src_candidates() -> List[Path]:
    """
    Order matters for -path and file shadowing.

    Straight-only policy:
      - SAFE_MODE is first (isolated).
      - canonical generated/src is second.
      - NO legacy gf/generated/src fallback.
    """
    cands = [
        config.SAFE_MODE_SRC,
        config.GENERATED_SRC_DEFAULT,
        config.GENERATED_SRC_ROOT,
    ]

    uniq: List[Path] = []
    seen: set[Path] = set()
    for p in cands:
        rp = _safe_resolve(p)
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(rp)
    return uniq


def gf_path_args() -> str:
    """
    Construct GF -path value.

    CRITICAL: include:
      - gf-rgl/src + gf-rgl/src/api
      - all first-level language dirs under gf-rgl/src
      - gf/contrib/{lang}/ (ADR 006)
      - gf/ (local modules like SemantikArchitect.gf and Wiki*.gf)
      - generated/src dirs (SAFE_MODE + canonical only)
      - repo root (last resort)
    """
    parts: List[str] = []

    if _safe_is_dir(config.RGL_SRC):
        parts.append(str(_safe_resolve(config.RGL_SRC)))
    else:
        parts.append(str(config.RGL_SRC))

    if _safe_is_dir(config.RGL_API):
        parts.append(str(_safe_resolve(config.RGL_API)))
    else:
        parts.append(str(config.RGL_API))

    parts.extend(str(d) for d in discover_rgl_lang_dirs())
    parts.extend(str(d) for d in discover_contrib_dirs())

    if _safe_is_dir(config.GF_DIR):
        parts.append(str(_safe_resolve(config.GF_DIR)))
    else:
        parts.append(str(config.GF_DIR))

    for d in generated_src_candidates():
        if _safe_is_dir(d):
            parts.append(str(d))

    parts.append(str(_safe_resolve(config.ROOT_DIR)))

    return os.pathsep.join(_dedupe_keep_order(parts))


__all__ = [
    "discover_rgl_lang_dirs",
    "discover_contrib_dirs",
    "generated_src_candidates",
    "gf_path_args",
]