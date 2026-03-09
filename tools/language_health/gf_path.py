# tools/language_health/gf_path.py
"""
GF path helpers for the language health tooling.

Straight-only policy:
  - Canonical generated bridge grammars live in: repo_root/generated/src
  - Hand-maintained grammars live in:        repo_root/gf
  - Legacy path repo_root/gf/generated/src is intentionally NOT used

Centralizes:
  - repo root detection (robust across CWDs / CI)
  - compile source dir detection (generated/src vs gf)
  - Prelude.gf discovery (to make gf compilation succeed reliably)
  - building the GF -path string (os.pathsep-separated)

Key behaviors:
  - Prefer the best compile source dir by sampling/counting language-like Wiki???.gf modules.
  - Never probe or include repo_root/gf/generated/src.
  - IMPORTANT: GF does not search recursively. For the RGL, we must include leaf dirs under gf-rgl/src
    (e.g. gf-rgl/src/abstract) so imports like Cat.gf resolve correctly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

# Environment overrides (useful in CI / when invoked from an installed package)
_REPO_ROOT_ENV_VARS: Tuple[str, ...] = ("LANGUAGE_HEALTH_REPO_ROOT", "REPO_ROOT")

# Straight-only compile source candidates (repo-relative)
_DEFAULT_COMPILE_SRC_REL: Tuple[str, ...] = (
    "generated/src",  # canonical generated bridge grammars
    "gf",             # hand-maintained grammars
)

# Roots to search for Prelude.gf if fast paths don’t hit
_DEFAULT_PRELUDE_SEARCH_REL: Tuple[str, ...] = (
    "gf-rgl",
    "gf",
    ".",
)

# RGL leaf dirs: include these first (mirrors typical GF_FLAGS ordering)
_RGL_PRIORITY_DIRS: Tuple[str, ...] = (
    "prelude",
    "abstract",
    "common",
    "api",
)

# Bound how many gf-rgl/src/* leaf dirs we include (safety against pathological trees)
_RGL_MAX_DIRS_ENV = "GF_RGL_SRC_MAX_DIRS"
_RGL_MAX_DIRS_DEFAULT = 512


# ---------------------------------------------------------------------------
# SMALL UTILITIES
# ---------------------------------------------------------------------------
def _as_dir(p: Path) -> Path:
    """If p is a file path, return its parent directory; otherwise return p."""
    try:
        return p if p.is_dir() else p.parent
    except Exception:
        return p.parent


def _parse_path_list_env(var_name: str) -> List[Path]:
    """Parse an os.pathsep-separated env var into Paths. Empty/missing => []"""
    raw = (os.environ.get(var_name) or "").strip()
    if not raw:
        return []
    out: List[Path] = []
    for part in (s.strip() for s in raw.split(os.pathsep)):
        if not part:
            continue
        try:
            out.append(Path(part))
        except Exception:
            continue
    return out


def _rel(repo_root: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(repo_root.resolve()))
    except Exception:
        return str(p)


def _safe_resolve(p: Path) -> Optional[Path]:
    """
    Resolve a path defensively.

    Returns None for broken/inaccessible paths instead of raising.
    """
    try:
        return p.expanduser().resolve()
    except Exception:
        return None


def _is_existing_dir(p: Path) -> bool:
    """
    Robust directory check that treats broken/inaccessible paths as absent.
    """
    try:
        return p.exists() and p.is_dir()
    except Exception:
        return False


def is_language_wiki_file(path: Path) -> bool:
    """
    True for per-language Wiki modules like WikiEng.gf, WikiFre.gf, WikiAra.gf.
    False for shared/non-language modules like WikiLexicon.gf.
    """
    name = path.name
    if not (name.startswith("Wiki") and name.endswith(".gf")):
        return False
    core = name[len("Wiki") : -len(".gf")]
    # Project convention here is strict 3-letter alpha suffix (Eng/Fre/Ara/...)
    return len(core) == 3 and core.isalpha()


def _sample_language_module_count(dir_path: Path, cap: int = 200) -> int:
    """
    Count language-like modules in a directory, up to cap (fast).
    This avoids expensive full scans on huge dirs.
    """
    n = 0
    try:
        if not _is_existing_dir(dir_path):
            return 0
        for p in dir_path.glob("Wiki*.gf"):
            if is_language_wiki_file(p):
                n += 1
                if n >= cap:
                    return cap
    except Exception:
        return n
    return n


def _safe_int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v > 0 else default
    except Exception:
        return default


def _list_immediate_subdirs(parent: Path, max_count: int) -> List[Path]:
    """
    List immediate subdirectories of `parent`, sorted by name (deterministic).
    """
    out: List[Path] = []
    try:
        if not _is_existing_dir(parent):
            return out
        subs = [p for p in parent.iterdir() if _is_existing_dir(p)]
        subs.sort(key=lambda p: p.name)
        for p in subs:
            out.append(p)
            if len(out) >= max_count:
                break
    except Exception:
        return out
    return out


def _rgl_leaf_dirs(repo_root: Path) -> List[Path]:
    """
    GF does not recurse: include gf-rgl/src and ALSO gf-rgl/src/* leaf dirs
    so modules like Cat.gf (in gf-rgl/src/abstract) resolve.
    """
    repo_root = repo_root.resolve()
    rgl_root = (repo_root / "gf-rgl" / "src").resolve()
    if not _is_existing_dir(rgl_root):
        return []

    max_dirs = _safe_int_env(_RGL_MAX_DIRS_ENV, _RGL_MAX_DIRS_DEFAULT)

    out: List[Path] = []
    seen: set[str] = set()

    # Always include the root itself (some modules may live directly under src/)
    out.append(rgl_root)
    seen.add(rgl_root.name)

    # Priority dirs first
    for name in _RGL_PRIORITY_DIRS:
        d = (rgl_root / name).resolve()
        if _is_existing_dir(d):
            out.append(d)
            seen.add(name)

    # Then include other immediate subdirs (deterministic), bounded
    for d in _list_immediate_subdirs(rgl_root, max_count=max_dirs):
        if d.name in seen:
            continue
        if d.name.startswith("."):
            continue
        out.append(d)
        seen.add(d.name)

        if len(out) >= max_dirs:
            break

    return out


# ---------------------------------------------------------------------------
# REPO ROOT DETECTION
# ---------------------------------------------------------------------------
def detect_repo_root(start: Optional[Path] = None) -> Path:
    """
    Detect repo root by walking upwards from `start`.

    Heuristics (first match wins):
      - env var LANGUAGE_HEALTH_REPO_ROOT / REPO_ROOT pointing to an existing dir
      - directory containing both "tools/" and "data/"
      - directory containing ".git"
      - directory containing "pyproject.toml"
      - fallback: parents[2] from this file (repo_root/tools/language_health/gf_path.py)

    Returns an absolute Path.
    """
    for var in _REPO_ROOT_ENV_VARS:
        v = (os.environ.get(var) or "").strip()
        if not v:
            continue
        p = Path(v).expanduser()
        if _is_existing_dir(p):
            return p.resolve()

    p0 = (start or Path(__file__)).expanduser()
    p = _as_dir(p0).resolve()

    for parent in [p, *p.parents]:
        try:
            if _is_existing_dir(parent / "tools") and _is_existing_dir(parent / "data"):
                return parent
            if (parent / ".git").exists():
                return parent
            if (parent / "pyproject.toml").exists():
                return parent
        except Exception:
            continue

    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# COMPILE SRC DETECTION
# ---------------------------------------------------------------------------
def detect_compile_src_dir(
    repo_root: Path,
    candidates: Optional[Sequence[Union[Path, str]]] = None,
) -> Tuple[Path, str]:
    """
    Detect the directory that contains per-language Wiki???.gf modules.

    Returns:
      (compile_src_dir, label_relative_to_repo_root)

    Selection rule:
      - Among candidates that exist, pick the one with the most language-like Wiki???.gf files.
      - Break ties by the canonical preference order:
          generated/src > gf
      - If nothing exists, fallback to repo_root/gf.
    """
    repo_root = repo_root.resolve()

    cands: List[Path] = []
    if candidates is None:
        for rel in _DEFAULT_COMPILE_SRC_REL:
            p = _safe_resolve(repo_root / rel)
            if p is not None:
                cands.append(p)
    else:
        for c in candidates:
            try:
                raw = (repo_root / c) if isinstance(c, str) else c
                p = _safe_resolve(raw)
                if p is not None:
                    cands.append(p)
            except Exception:
                continue

    best: Optional[Path] = None
    best_score = -1

    for p in cands:
        if not _is_existing_dir(p):
            continue
        score = _sample_language_module_count(p, cap=200)
        if score > best_score:
            best = p
            best_score = score

    if best is None:
        fallback = (repo_root / "gf").resolve()
        return fallback, _rel(repo_root, fallback)

    return best, _rel(repo_root, best)


# ---------------------------------------------------------------------------
# PRELUDE DISCOVERY
# ---------------------------------------------------------------------------
def _default_prelude_search_roots(repo_root: Path) -> List[Path]:
    return [(repo_root / rel).resolve() for rel in _DEFAULT_PRELUDE_SEARCH_REL]


@lru_cache(maxsize=16)
def _find_prelude_dirs_cached(repo_root_str: str, max_hits: int = 6) -> Tuple[str, ...]:
    """
    Cached Prelude.gf directory discovery.
    Returns tuple[str] of dir paths to keep cache keys stable.
    """
    repo_root = Path(repo_root_str).resolve()

    found: List[Path] = []
    seen: set[Path] = set()

    common = [
        repo_root / "gf-rgl" / "src" / "prelude" / "Prelude.gf",
        repo_root / "gf-rgl" / "src" / "Prelude.gf",
        repo_root / "gf" / "Prelude.gf",
    ]
    for prelude in common:
        try:
            if prelude.exists():
                d = prelude.parent.resolve()
                if d not in seen:
                    seen.add(d)
                    found.append(d)
        except Exception:
            continue

    if len(found) >= max_hits:
        return tuple(str(p) for p in found[:max_hits])

    for root in _default_prelude_search_roots(repo_root):
        if not _is_existing_dir(root):
            continue
        try:
            for prelude in root.rglob("Prelude.gf"):
                d = prelude.parent.resolve()
                if d not in seen:
                    seen.add(d)
                    found.append(d)
                if len(found) >= max_hits:
                    return tuple(str(p) for p in found[:max_hits])
        except Exception:
            continue

    return tuple(str(p) for p in found)


def find_prelude_dirs(repo_root: Path, max_hits: int = 6) -> List[Path]:
    """
    Public Prelude dir discovery.

    Env hinting:
      - GF_PRELUDE_DIRS: os.pathsep-separated list of directories to try first.

    Returns list[Path] (deduped, existing-only), priority order.
    """
    repo_root = repo_root.resolve()

    hinted = _parse_path_list_env("GF_PRELUDE_DIRS")
    out: List[Path] = []
    seen: set[Path] = set()

    def add_dir(d: Path) -> None:
        rp = _safe_resolve(d)
        if rp is None:
            return
        if rp in seen:
            return
        if not _is_existing_dir(rp):
            return
        seen.add(rp)
        out.append(rp)

    for d in hinted:
        add_dir(d)

    for s in _find_prelude_dirs_cached(str(repo_root), max_hits=max_hits):
        add_dir(Path(s))

    return out


# ---------------------------------------------------------------------------
# GF -path BUILDING
# ---------------------------------------------------------------------------
def build_gf_path(
    repo_root: Path,
    compile_src_dir: Path,
    extra_dirs: Optional[Iterable[Path]] = None,
    prelude_max_hits: int = 6,
) -> str:
    """
    Build the os.pathsep-separated GF -path string.

    Includes (in order):
      - discovered Prelude.gf parent dirs
      - gf-rgl/src and gf-rgl/src/* leaf dirs (priority order then sorted; bounded)
      - repo_root/generated/src (if present)
      - repo_root/gf
      - compile_src_dir
      - repo_root
      - any caller-provided extra_dirs (appended)
      - env GF_PATH_EXTRA (os.pathsep-separated) appended last

    Only existing directories are included; duplicates removed preserving order.

    Straight-only note:
      - repo_root/gf/generated/src is intentionally excluded.
    """
    repo_root = repo_root.resolve()
    compile_src_dir = compile_src_dir.resolve()

    gen_src_root = (repo_root / "generated" / "src").resolve()
    gf_dir = (repo_root / "gf").resolve()

    parts: List[Path] = []

    # Prelude dirs first
    parts.extend(find_prelude_dirs(repo_root, max_hits=prelude_max_hits))

    # RGL paths (must include leaf dirs like gf-rgl/src/abstract)
    parts.extend(_rgl_leaf_dirs(repo_root))

    # Straight-only generated location
    parts.append(gen_src_root)

    # Always include gf + compile src + repo root
    parts.extend([gf_dir, compile_src_dir, repo_root])

    if extra_dirs:
        parts.extend([Path(p) for p in extra_dirs])

    parts.extend(_parse_path_list_env("GF_PATH_EXTRA"))

    out: List[str] = []
    seen: set[Path] = set()
    for p in parts:
        rp = _safe_resolve(p)
        if rp is None:
            continue
        if rp in seen:
            continue
        if not _is_existing_dir(rp):
            continue
        seen.add(rp)
        out.append(str(rp))

    return os.pathsep.join(out)