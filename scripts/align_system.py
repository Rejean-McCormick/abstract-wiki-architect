#!/usr/bin/env python3
# scripts/align_system.py
"""
Alignment System (ADR-001)

Atomic sequence:
1) Time Travel: pin gf-rgl to a GF-compatible *ref* (tag/branch/commit)
2) Cache Purge: delete *.gfo binaries to avoid version conflicts
3) Matrix Refresh (optional): rebuild everything_matrix.json (optionally --regen-rgl)
4) Tier-1 Bootstrap: generate Tier-1 bridge/app grammars via tools/bootstrap_tier1.py
   - Bridge files: generated/src/Syntax{Suffix}.gf   (project-owned; does not edit gf-rgl)
   - App grammars:  gf/Wiki{Suffix}.gf              (needed for HIGH_ROAD builds)

This script is invoked by manage.py with:
  --langs en fr --tier 1 --force [--no-time-travel]

Compatible CLI:
  python scripts/align_system.py --langs en fr --tier 1 --force
  python scripts/align_system.py --langs en,fr --tier 1 --force
  python scripts/align_system.py --ref auto --regen-rgl --force
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Set, Tuple, List


# ---------------------------------------------------------------------
# Optional logging helper (keep script self-contained)
# ---------------------------------------------------------------------
try:
    from utils.tool_run_logging import tool_logging  # type: ignore
except Exception:
    @contextmanager
    def tool_logging(_name: str):
        class _Ctx:
            def log_stage(self, msg: str) -> None:
                print(f"[align] {msg}")

            def finish(self, payload: Mapping[str, Any]) -> None:
                print("[align] done")
                for k, v in payload.items():
                    print(f"  - {k}: {v}")

        yield _Ctx()


# ---------------------------------------------------------------------
# Paths / defaults
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]

RGL_DIR = ROOT_DIR / "gf-rgl"
RGL_SRC = RGL_DIR / "src"
GF_DIR = ROOT_DIR / "gf"

MATRIX_PATH = ROOT_DIR / "data" / "indices" / "everything_matrix.json"
BUILD_INDEX = ROOT_DIR / "tools" / "everything_matrix" / "build_index.py"
BOOTSTRAP_TIER1 = ROOT_DIR / "tools" / "bootstrap_tier1.py"

ISO_MAP_PATH = ROOT_DIR / "data" / "config" / "iso_to_wiki.json"
RGL_PIN_FILE = ROOT_DIR / "data" / "config" / "rgl_pin.json"

# Bootstrap output defaults (match tools/bootstrap_tier1.py defaults)
DEFAULT_BRIDGE_OUT = ROOT_DIR / "generated" / "src"
DEFAULT_APP_OUT = ROOT_DIR / "gf"

# Env overrides (highest priority)
ENV_RGL_REF = (os.getenv("SEMANTIK_ARCHITECT_RGL_REF") or "").strip()
ENV_RGL_COMMIT = (os.getenv("SEMANTIK_ARCHITECT_RGL_COMMIT") or "").strip()  # backwards compat name


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _run_checked(cmd: Iterable[str], *, cwd: Optional[Path] = None, dry_run: bool = False) -> None:
    cmd_list = list(cmd)
    if dry_run:
        print("[dry-run]", " ".join(cmd_list))
        return
    proc = subprocess.run(cmd_list, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _run_capture(cmd: Iterable[str], *, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _parse_langs(langs_args: Optional[list[str]]) -> Optional[Set[str]]:
    """
    Accepts:
      --langs en fr
      --langs en,fr
      --langs "en,fr"
    Returns normalized set {'en','fr'} or None.
    """
    if not langs_args:
        return None
    parts: list[str] = []
    for item in langs_args:
        if not item:
            continue
        for tok in item.split(","):
            tok = tok.strip().lower()
            if tok:
                parts.append(tok)
    return set(parts) if parts else None


def _git_has_remote(repo: Path) -> bool:
    p = _run_capture(["git", "-C", str(repo), "remote"])
    return p.returncode == 0 and bool((p.stdout or "").strip())


def _git_is_shallow(repo: Path) -> bool:
    p = _run_capture(["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"])
    return p.returncode == 0 and (p.stdout or "").strip().lower() == "true"


def _git_resolve_ref(repo: Path, ref: str) -> Optional[str]:
    p = _run_capture(["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"])
    if p.returncode != 0:
        return None
    return (p.stdout or "").strip() or None


def _git_head(repo: Path) -> Optional[str]:
    p = _run_capture(["git", "-C", str(repo), "rev-parse", "HEAD"])
    if p.returncode != 0:
        return None
    return (p.stdout or "").strip() or None


def _git_list_tags(repo: Path) -> List[str]:
    p = _run_capture(["git", "-C", str(repo), "tag", "-l"])
    if p.returncode != 0:
        return []
    return [t.strip() for t in (p.stdout or "").splitlines() if t.strip()]


def _detect_gf_version() -> Optional[Tuple[int, int, int]]:
    """
    Best-effort parse of `gf --version`.
    Returns (major, minor, patch) or None.
    """
    try:
        p = _run_capture(["gf", "--version"])
        if p.returncode != 0:
            return None
        text = (p.stdout or "") + "\n" + (p.stderr or "")
        m = re.search(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b", text)
        if not m:
            return None
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3) or "0")
        return (major, minor, patch)
    except Exception:
        return None


def _pick_best_rgl_ref(tags: List[str], gf_ver: Optional[Tuple[int, int, int]]) -> Optional[str]:
    """
    Choose a reasonable default tag based on installed GF version and available tags.

    Priority:
      1) exact version match tag: release-X.Y / RELEASE-X.Y / GF-X.Y (case-insensitive)
      2) nearest <= version within same major (e.g., gf=3.12, tags include GF-3.10 -> choose 3.10)
      3) highest 3.x tag available
    """
    if not tags:
        return None

    # Normalize lookup for exact matches but return original tag spelling.
    by_lower = {t.lower(): t for t in tags}

    def exact_candidates(major: int, minor: int) -> List[str]:
        key_variants = [
            f"release-{major}.{minor}",
            f"release-{major}.{minor}.0",
            f"gf-{major}.{minor}",
            f"gf-{major}.{minor}.0",
            f"release-{major}.{minor}".upper(),
            f"gf-{major}.{minor}".upper(),
        ]
        out: List[str] = []
        for k in key_variants:
            if k.lower() in by_lower:
                out.append(by_lower[k.lower()])
        return out

    # Parse numeric tags like GF-3.10 or RELEASE-3.9
    parsed: List[Tuple[int, int, str]] = []
    for t in tags:
        m = re.search(r"(?i)\b(?:gf|release)\s*[-_]\s*(\d+)\.(\d+)\b", t)
        if m:
            parsed.append((int(m.group(1)), int(m.group(2)), t))

    # 1) exact
    if gf_ver:
        maj, min_, _ = gf_ver
        ex = exact_candidates(maj, min_)
        if ex:
            return ex[0]

    # 2) nearest <= in same major
    if gf_ver and parsed:
        maj, min_, _ = gf_ver
        same_major = [(M, m, t) for (M, m, t) in parsed if M == maj]
        if same_major:
            leq = [(M, m, t) for (M, m, t) in same_major if m <= min_]
            if leq:
                leq.sort(key=lambda x: x[1], reverse=True)  # highest minor <= target
                return leq[0][2]
            # no <= available; fall back to smallest above target
            same_major.sort(key=lambda x: x[1])
            return same_major[0][2]

    # 3) highest 3.x (or highest available)
    if parsed:
        parsed.sort(key=lambda x: (x[0], x[1]), reverse=True)
        # prefer major==3 if present
        for M, m, t in parsed:
            if M == 3:
                return t
        return parsed[0][2]

    # No GF/RELEASE numeric tags, so maybe date tags exist; choose newest lexicographically
    # (works for YYYYMMDD style tags)
    date_like = [t for t in tags if re.fullmatch(r"\d{8}", t)]
    if date_like:
        date_like.sort()
        return date_like[-1]

    return None


def _load_last_pin_ref() -> Optional[str]:
    if not RGL_PIN_FILE.exists():
        return None
    try:
        data = _load_json(RGL_PIN_FILE)
        ref = data.get("ref")
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    except Exception:
        pass
    return None


def _detect_rgl_suffix(folder_path: Path) -> Optional[str]:
    """
    Infer the RGL suffix (e.g., 'Eng') from a gf-rgl language folder.

    Prefer Syntax*.gf because bridge naming is Syntax{Suffix}.gf, then fall back to other
    common RGL module prefixes.
    """
    if not folder_path.exists():
        return None

    patterns: List[Tuple[str, str]] = [
        ("Syntax*.gf", "Syntax"),
        ("Grammar*.gf", "Grammar"),
        ("Paradigms*.gf", "Paradigms"),
        ("Lexicon*.gf", "Lexicon"),
        ("Constructors*.gf", "Constructors"),
    ]

    for glob_pat, prefix in patterns:
        for f in folder_path.glob(glob_pat):
            stem = f.stem
            if stem.startswith(prefix) and len(stem) > len(prefix):
                return stem[len(prefix) :]
    return None


def _wiki_suffix_from_iso(iso_code: str, iso_map: Mapping[str, Any]) -> str:
    iso = (iso_code or "").strip().lower()
    if not iso:
        return "Unknown"
    raw_val = iso_map.get(iso)
    if isinstance(raw_val, dict) and raw_val.get("wiki"):
        return str(raw_val["wiki"]).replace("Wiki", "").strip()
    if isinstance(raw_val, str) and raw_val:
        return raw_val.replace("Wiki", "").strip()
    return iso.title()


def _wiki_filename(iso_code: str, iso_map: Mapping[str, Any]) -> str:
    return f"Wiki{_wiki_suffix_from_iso(iso_code, iso_map)}.gf"


def _matrix_needs_regen_rgl(matrix: Mapping[str, Any]) -> bool:
    """
    Heuristic:
    If Tier-1 languages have meta.folder='api' or folder paths that don't allow suffix detection
    (Syntax*/Grammar*/Paradigms*/etc), the RGL inventory is stale/wrong and we should run --regen-rgl.
    """
    langs = matrix.get("languages")
    if not isinstance(langs, dict):
        return False

    for iso2, rec in langs.items():
        if not isinstance(iso2, str) or not isinstance(rec, dict):
            continue
        meta = rec.get("meta")
        if not isinstance(meta, dict):
            continue
        if int(meta.get("tier", -1)) != 1:
            continue

        folder = meta.get("folder")
        if not isinstance(folder, str) or not folder.strip():
            continue

        folder = folder.strip()
        if folder == "api":
            return True

        if (RGL_SRC / folder).exists() and _detect_rgl_suffix(RGL_SRC / folder) is None:
            return True

    return False


def _select_pin_ref(user_ref: Optional[str]) -> str:
    """
    Decide the ref to use.

    Priority:
      1) explicit CLI --ref/--commit (unless "auto")
      2) env SEMANTIK_ARCHITECT_RGL_REF / SEMANTIK_ARCHITECT_RGL_COMMIT
      3) last pinned data/config/rgl_pin.json (if still resolvable)
      4) auto-pick based on gf --version + available tags
    """
    # 1) explicit
    if user_ref and user_ref.strip() and user_ref.strip().lower() != "auto":
        return user_ref.strip()

    # 2) env
    if ENV_RGL_REF:
        return ENV_RGL_REF
    if ENV_RGL_COMMIT:
        return ENV_RGL_COMMIT

    # Need git for the rest
    tags = _git_list_tags(RGL_DIR)
    gf_ver = _detect_gf_version()

    # 3) last pin
    last = _load_last_pin_ref()
    if last and _git_resolve_ref(RGL_DIR, last):
        return last

    # 4) auto from tags
    best = _pick_best_rgl_ref(tags, gf_ver)
    if best:
        return best

    # Final fallback: keep HEAD (means no checkout) – but warn user via failure in time travel
    return "auto"


# ---------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------
def step_time_travel(ref: str, *, force_checkout: bool, dry_run: bool) -> str:
    """
    Pin gf-rgl to a *ref* (tag/branch/commit) and return resolved commit hash.
    Works whether gf-rgl is a normal git repo. Submodule support is best-effort:
    if .gitmodules contains gf-rgl entry, we will init/update it.
    """
    if not _git_available():
        raise SystemExit("git not found on PATH. Cannot align gf-rgl.")

    # Submodule init only if configured (avoid .gitmodules error)
    gitmodules = ROOT_DIR / ".gitmodules"
    if gitmodules.is_file():
        txt = gitmodules.read_text(encoding="utf-8", errors="ignore")
        if ("path = gf-rgl" in txt) or ('path = "gf-rgl"' in txt):
            _run_checked(
                ["git", "submodule", "update", "--init", "--recursive", "gf-rgl"],
                cwd=ROOT_DIR,
                dry_run=dry_run,
            )

    if not RGL_DIR.exists():
        raise SystemExit("gf-rgl/ missing. Expected repo_root/gf-rgl to exist.")

    if not (RGL_DIR / ".git").exists():
        raise SystemExit("gf-rgl exists but is not a git repo (missing gf-rgl/.git).")

    # Fetch tags so tag refs resolve deterministically (also handles shallow clones)
    if _git_has_remote(RGL_DIR):
        if _git_is_shallow(RGL_DIR):
            _run_checked(["git", "-C", str(RGL_DIR), "fetch", "--unshallow", "--tags", "--prune"], dry_run=dry_run)
        else:
            _run_checked(["git", "-C", str(RGL_DIR), "fetch", "--tags", "--prune"], dry_run=dry_run)

    resolved = _git_resolve_ref(RGL_DIR, ref) if not dry_run else "DRY_RUN"
    if not resolved:
        tags = _git_list_tags(RGL_DIR)
        tail = "\n".join(tags[-25:]) if tags else "(no tags found)"
        gf_ver = _detect_gf_version()
        gf_str = f"{gf_ver[0]}.{gf_ver[1]}.{gf_ver[2]}" if gf_ver else "unknown"
        suggestion = _pick_best_rgl_ref(tags, gf_ver)
        sugg_line = f"\nSuggested (auto) ref for your GF ({gf_str}): {suggestion}\n" if suggestion else "\n"
        raise SystemExit(
            f"Ref '{ref}' not found in gf-rgl (even after fetch).\n"
            f"Detected gf --version: {gf_str}\n"
            f"{sugg_line}"
            "If you are using a fork, pick an existing tag/commit and pass --ref.\n"
            "Recent tags:\n"
            f"{tail}\n"
        )

    # Deterministic pin: detach, hard reset, clean
    checkout = (
        ["git", "-C", str(RGL_DIR), "checkout", "-f", "--detach", ref]
        if force_checkout
        else ["git", "-C", str(RGL_DIR), "checkout", "--detach", ref]
    )
    _run_checked(checkout, dry_run=dry_run)
    _run_checked(["git", "-C", str(RGL_DIR), "reset", "--hard", ref], dry_run=dry_run)
    _run_checked(["git", "-C", str(RGL_DIR), "clean", "-fdx"], dry_run=dry_run)

    final_head = _git_head(RGL_DIR) if not dry_run else resolved
    return final_head or resolved


def step_write_rgl_pin(*, ref: str, commit: str, dry_run: bool) -> None:
    """
    Write data/config/rgl_pin.json so builder/orchestrator can enforce deterministically.
    """
    payload = {
        "ref": ref,
        "commit": commit,
        "updated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if dry_run:
        print("[dry-run] write", str(RGL_PIN_FILE))
        return
    _write_json(RGL_PIN_FILE, payload)


def step_cache_purge(*, dry_run: bool) -> int:
    """Delete all .gfo binaries under known build roots."""
    purge_roots = [ROOT_DIR / "gf-rgl", ROOT_DIR / "gf", ROOT_DIR / "generated"]
    deleted = 0
    for base in purge_roots:
        if not base.exists():
            continue
        for path in base.rglob("*.gfo"):
            deleted += 1
            if not dry_run:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
    return deleted


def step_ensure_matrix(
    *,
    force: bool,
    regen_rgl: bool,
    regen_lex: bool,
    regen_app: bool,
    regen_qa: bool,
    dry_run: bool,
) -> None:
    """
    Ensure data/indices/everything_matrix.json exists.
    If missing or forced or any regen flag set, build using tools/everything_matrix/build_index.py.
    """
    if MATRIX_PATH.exists() and not (force or regen_rgl or regen_lex or regen_app or regen_qa):
        return

    if not BUILD_INDEX.exists():
        raise SystemExit(f"Matrix builder not found: {BUILD_INDEX}")

    cmd = [sys.executable, str(BUILD_INDEX)]
    if force:
        cmd.append("--force")
    if regen_rgl:
        cmd.append("--regen-rgl")
    if regen_lex:
        cmd.append("--regen-lex")
    if regen_app:
        cmd.append("--regen-app")
    if regen_qa:
        cmd.append("--regen-qa")

    _run_checked(cmd, cwd=ROOT_DIR, dry_run=dry_run)

    if not dry_run and not MATRIX_PATH.exists():
        raise SystemExit(f"Matrix still not found after build: {MATRIX_PATH}")


def step_bootstrap_tier1(
    *,
    langs_filter: Optional[Set[str]],
    force: bool,
    dry_run: bool,
    bridge_out: Path,
    app_out: Path,
) -> None:
    """
    Delegate to tools/bootstrap_tier1.py (authoritative generator).
    This avoids editing gf-rgl and matches your successful run output.
    """
    if not BOOTSTRAP_TIER1.exists():
        raise SystemExit(f"bootstrap_tier1 tool not found: {BOOTSTRAP_TIER1}")

    cmd = [sys.executable, str(BOOTSTRAP_TIER1)]
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")

    # bootstrap_tier1 expects --langs as a single string (comma/space separated)
    if langs_filter:
        cmd += ["--langs", ",".join(sorted(langs_filter))]

    cmd += ["--matrix", str(MATRIX_PATH)]
    cmd += ["--rgl-src", str(RGL_SRC)]
    cmd += ["--bridge-out", str(bridge_out)]
    cmd += ["--app-out", str(app_out)]

    _run_checked(cmd, cwd=ROOT_DIR, dry_run=dry_run)


def step_validate(
    *,
    langs_filter: Optional[Set[str]],
    tier: int,
    bridge_out: Path,
    app_out: Path,
) -> Tuple[int, int, int]:
    """
    Validate (best-effort):
      - for Tier==1, selected languages should have app grammar in gf/
      - if gf-rgl doesn't provide Syntax{suffix}.gf, project bridge should exist in generated/src

    Returns: (missing_apps, missing_bridges, unsupported_tier1)
    """
    if tier != 1:
        return (0, 0, 0)

    if not MATRIX_PATH.exists() or not ISO_MAP_PATH.exists():
        return (0, 0, 0)

    matrix = _load_json(MATRIX_PATH)
    iso_map = _load_json(ISO_MAP_PATH)

    languages = matrix.get("languages", {})
    if not isinstance(languages, dict):
        return (0, 0, 0)

    missing_apps = 0
    missing_bridges = 0
    unsupported_tier1 = 0

    for iso2, rec in languages.items():
        if not isinstance(iso2, str) or not isinstance(rec, dict):
            continue
        iso_key = iso2.lower()

        if langs_filter and iso_key not in langs_filter:
            continue

        meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
        if int(meta.get("tier", -1)) != 1:
            continue

        folder = meta.get("folder")
        if not folder:
            continue

        folder_path = RGL_SRC / str(folder)
        suffix = _detect_rgl_suffix(folder_path)
        if not suffix:
            unsupported_tier1 += 1
            continue

        wiki_file = app_out / _wiki_filename(iso_key, iso_map)
        if not wiki_file.exists():
            missing_apps += 1

        bridge_name = f"Syntax{suffix}.gf"
        rgl_has_bridge = (folder_path / bridge_name).exists()
        if not rgl_has_bridge:
            if not (bridge_out / bridge_name).exists():
                missing_bridges += 1

    return (missing_apps, missing_bridges, unsupported_tier1)


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Align gf-rgl and bootstrap Tier-1 bridge/app GF files.")

    # Keep manage.py compatibility: manage passes --langs (nargs=*), --tier, --force, --no-time-travel
    parser.add_argument("--langs", nargs="*", default=None, help="ISO-2 language codes (space or comma separated).")
    parser.add_argument("--tier", type=int, default=1, help="Tier to bootstrap (only Tier 1 supported here).")

    # Pinning: allow tags/branches/commits; "auto" is special
    parser.add_argument(
        "--ref",
        default="auto",
        help="Pinned gf-rgl ref (tag/branch/commit). Use 'auto' to select based on gf --version + available tags.",
    )
    parser.add_argument("--commit", default=None, help="Backward-compat alias for --ref (can be a tag/commit).")

    # Behavior flags
    parser.add_argument("--force", action="store_true", help="Overwrite generated files; also force checkout in gf-rgl.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without writing/deleting.")
    parser.add_argument("--no-time-travel", action="store_true", help="Skip gf-rgl pin/reset step (NOT recommended).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 2) if any required Tier-1 outputs are missing. Default is non-fatal reporting.",
    )

    # Matrix refresh flags (matches tools/everything_matrix/build_index.py)
    parser.add_argument("--force-matrix", action="store_true", help="Force rebuild of everything_matrix.json (ignore cache).")
    parser.add_argument("--regen-rgl", action="store_true", help="Regenerate RGL inventory (recommended if folder mapping is wrong).")
    parser.add_argument("--regen-lex", action="store_true", help="Force lexicon rescan.")
    parser.add_argument("--regen-app", action="store_true", help="Force app rescan.")
    parser.add_argument("--regen-qa", action="store_true", help="Force QA rescan.")

    # Quality-of-life: auto regen-rgl if matrix looks stale (folder=api, etc.)
    parser.add_argument("--no-auto-regen-rgl", action="store_true", help="Disable auto regen-rgl heuristic.")

    # Output dirs (rarely needed to override)
    parser.add_argument("--bridge-out", default=str(DEFAULT_BRIDGE_OUT), help="Bridge output dir (default: generated/src).")
    parser.add_argument("--app-out", default=str(DEFAULT_APP_OUT), help="App grammar output dir (default: gf/).")

    args = parser.parse_args()

    if int(args.tier) != 1:
        raise SystemExit("This align script only supports Tier 1 bootstrap (tier must be 1).")

    if not _git_available():
        raise SystemExit("git not found on PATH. Cannot align gf-rgl.")

    if not RGL_DIR.exists():
        raise SystemExit("gf-rgl/ missing. Expected repo_root/gf-rgl to exist.")

    langs_filter = _parse_langs(args.langs)
    tier = int(args.tier)

    # Determine ref
    raw_ref = (args.commit or args.ref or "auto").strip()
    pinned_ref = _select_pin_ref(raw_ref)

    bridge_out = Path(args.bridge_out)
    app_out = Path(args.app_out)

    with tool_logging("align_system") as ctx:
        if args.no_time_travel:
            ctx.log_stage("Time Travel (skipped)")
            resolved = _git_head(RGL_DIR) or "unknown"
        else:
            if pinned_ref.lower() == "auto":
                tags = _git_list_tags(RGL_DIR)
                gf_ver = _detect_gf_version()
                suggestion = _pick_best_rgl_ref(tags, gf_ver)
                raise SystemExit(
                    "AUTO pin could not determine a usable gf-rgl ref.\n"
                    "Run: git -C gf-rgl tag -l\n"
                    "Then re-run with: python manage.py align --force  (and set SEMANTIK_ARCHITECT_RGL_REF)\n"
                    f"Or pass an explicit ref: --ref <tag/branch/commit>\n"
                    f"Detected gf --version: {gf_ver}\n"
                    f"Auto suggestion: {suggestion}\n"
                )

            ctx.log_stage(f"Time Travel (gf-rgl -> {pinned_ref})")
            resolved = step_time_travel(pinned_ref, force_checkout=bool(args.force), dry_run=bool(args.dry_run))

        ctx.log_stage("Write RGL pin (data/config/rgl_pin.json)")
        step_write_rgl_pin(ref=pinned_ref if not args.no_time_travel else "HEAD", commit=resolved, dry_run=bool(args.dry_run))

        ctx.log_stage("Cache Purge (.gfo)")
        deleted = step_cache_purge(dry_run=bool(args.dry_run))

        # Auto-regen heuristic (only if user didn't request regen already)
        auto_regen = False
        if (not args.no_auto_regen_rgl) and (not args.regen_rgl) and MATRIX_PATH.exists():
            try:
                matrix = _load_json(MATRIX_PATH)
                auto_regen = _matrix_needs_regen_rgl(matrix)
            except Exception:
                auto_regen = False

        regen_rgl = bool(args.regen_rgl) or bool(auto_regen)

        if auto_regen:
            ctx.log_stage("Matrix looks stale (auto --regen-rgl enabled)")

        ctx.log_stage("Index (Everything Matrix)")
        step_ensure_matrix(
            force=bool(args.force_matrix),
            regen_rgl=regen_rgl,
            regen_lex=bool(args.regen_lex),
            regen_app=bool(args.regen_app),
            regen_qa=bool(args.regen_qa),
            dry_run=bool(args.dry_run),
        )

        ctx.log_stage("Bootstrap Tier-1 (tools/bootstrap_tier1.py)")
        step_bootstrap_tier1(
            langs_filter=langs_filter,
            force=bool(args.force),
            dry_run=bool(args.dry_run),
            bridge_out=bridge_out,
            app_out=app_out,
        )

        ctx.log_stage("Validation")
        missing_apps, missing_bridges, unsupported_tier1 = step_validate(
            langs_filter=langs_filter,
            tier=tier,
            bridge_out=bridge_out,
            app_out=app_out,
        )

        ctx.finish(
            {
                "ref": pinned_ref if not args.no_time_travel else "HEAD",
                "resolved_commit": resolved,
                "no_time_travel": bool(args.no_time_travel),
                "dry_run": bool(args.dry_run),
                "gfo_deleted": deleted,
                "regen_rgl": regen_rgl,
                "missing_apps": missing_apps,
                "missing_bridges": missing_bridges,
                "unsupported_tier1": unsupported_tier1,
                "strict": bool(args.strict),
                "bridge_out": str(bridge_out),
                "app_out": str(app_out),
                "rgl_pin_file": str(RGL_PIN_FILE),
            }
        )

        if not args.dry_run and args.strict and (missing_apps > 0 or missing_bridges > 0):
            raise SystemExit(2)


if __name__ == "__main__":
    main()