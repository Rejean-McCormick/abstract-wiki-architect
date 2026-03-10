# builder/orchestrator/build.py
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import config
from . import gf_path
from . import git_utils
from . import iso_map

try:
    from utils.grammar_factory import generate_safe_mode_grammar  # type: ignore
except Exception:
    generate_safe_mode_grammar = None

logger = logging.getLogger("Orchestrator")

# The PGF artifact name should be stable and match what the API expects.
PGF_BASENAME = "semantik_architect"
# Known legacy names we might encounter from older runs.
LEGACY_PGF_FILENAMES = (
    "SemantikArchitect.pgf",
    "semantik_architect.pgf",
)


def _get_env_rgl_ref() -> Optional[str]:
    """
    Backwards/forwards compatible access to the orchestrator RGL ref env.
    (Some versions export ENV_RGL_REF; current config uses _ENV_RGL_REF.)
    """
    v = getattr(config, "ENV_RGL_REF", None)
    if v is None:
        v = getattr(config, "_ENV_RGL_REF", None)
    if isinstance(v, str):
        v = v.strip() or None
    return v


# -----------------------------------------------------------------------------
# Subprocess helpers
# -----------------------------------------------------------------------------
def _format_cmd(cmd: List[str]) -> str:
    # Stable, readable command string for logs.
    return " ".join(shlex.quote(c) for c in cmd)


def _run(cmd: List[str], cwd: Path, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _relpath(from_dir: Path, target: Path) -> str:
    try:
        return str(target.resolve().relative_to(from_dir.resolve()))
    except Exception:
        try:
            return os.path.relpath(str(target), start=str(from_dir))
        except Exception:
            return str(target)


def _ensure_dirs() -> None:
    for d in (
        config.LOG_DIR,
        config.CONTRIB_DIR,
        config.GENERATED_SRC_ROOT,
        config.GENERATED_SRC_GF,
        config.GENERATED_SRC_DEFAULT,
        config.SAFE_MODE_SRC,
    ):
        d.mkdir(parents=True, exist_ok=True)


def _ensure_executable_exists(exe: str) -> None:
    p = Path(exe)

    if p.is_absolute() and p.exists() and p.is_file():
        return

    if not p.is_absolute():
        repo_candidate = (config.ROOT_DIR / p)
        if repo_candidate.exists() and repo_candidate.is_file():
            return

    if shutil.which(exe) is None:
        raise RuntimeError(
            f"GF binary '{exe}' not found on PATH (or as a file). "
            f"Set GF_BIN or install GF."
        )


# -----------------------------------------------------------------------------
# Matrix
# -----------------------------------------------------------------------------
def load_matrix() -> Dict[str, object]:
    if not config.MATRIX_FILE.exists():
        logger.warning("⚠️  Everything Matrix not found. Defaulting to empty.")
        return {}
    try:
        data = json.loads(config.MATRIX_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.error("❌ Everything Matrix is not a JSON object. Cannot proceed.")
            return {}
        return data
    except json.JSONDecodeError:
        logger.error("❌ Corrupt Everything Matrix. Cannot proceed.")
        return {}
    except Exception as e:
        logger.error(f"❌ Failed to load Everything Matrix: {e}")
        return {}


# -----------------------------------------------------------------------------
# Cleaning
# -----------------------------------------------------------------------------
def _clean_dir_patterns(root: Path, patterns: Tuple[str, ...]) -> None:
    for pat in patterns:
        for p in root.rglob(pat):
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except Exception:
                pass


def clean_artifacts() -> None:
    """Best-effort clean of build artifacts across gf/ and generated sources."""
    _ensure_dirs()
    logger.info("🧹 Cleaning build artifacts...")

    # Remove current and known legacy PGF names.
    for fname in (f"{PGF_BASENAME}.pgf", *LEGACY_PGF_FILENAMES):
        p = config.GF_DIR / fname
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # Remove object/log/tmp artifacts (keep .gf sources).
    _clean_dir_patterns(config.GF_DIR, ("*.gfo", "*.tmp"))

    for gen_dir in (
        config.SAFE_MODE_SRC,
        config.GENERATED_SRC_ROOT,
        config.GENERATED_SRC_GF,
        config.GENERATED_SRC_DEFAULT,
    ):
        if gen_dir.exists():
            _clean_dir_patterns(gen_dir, ("*.gfo", "*.tmp"))

    if config.CONTRIB_DIR.exists():
        _clean_dir_patterns(config.CONTRIB_DIR, ("*.gfo", "*.tmp"))

    # Build logs are owned by the orchestrator; safe to wipe.
    if config.LOG_DIR.exists():
        for p in config.LOG_DIR.glob("*"):
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except Exception:
                pass

    logger.info("🧹 Clean complete.")


# -----------------------------------------------------------------------------
# Alignment / Preflight checks (no side effects)
# -----------------------------------------------------------------------------
def _load_rgl_pin_file() -> Dict[str, Any]:
    if not config.RGL_PIN_FILE.exists():
        return {}
    try:
        data = json.loads(config.RGL_PIN_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _expected_rgl_pin() -> Tuple[Optional[str], Optional[str], bool, Optional[str]]:
    """
    Returns (expected_ref, expected_commit, enforce, note)
    """
    pin = _load_rgl_pin_file()

    ref: Optional[str] = None
    resolved: Optional[str] = None

    env_rgl_ref = _get_env_rgl_ref()

    if pin:
        ref = str(pin.get("ref") or "").strip() or None
        resolved = str(pin.get("resolved") or "").strip() or None
        if not ref:
            maybe = str(pin.get("commit") or "").strip()
            if maybe:
                ref = maybe

    if env_rgl_ref:
        ref = env_rgl_ref

    if ref:
        resolve_ref = getattr(git_utils, "git_resolve_ref", None) or getattr(git_utils, "_git_resolve_ref", None)
        live = resolve_ref(config.RGL_DIR, ref) if resolve_ref else None
        if live:
            resolved = live

    note: Optional[str] = None
    if not ref and not resolved and config.RGL_DIR.exists():
        detect_gf_version = getattr(git_utils, "detect_gf_version", None) or getattr(git_utils, "_detect_gf_version", None)
        list_tags = getattr(git_utils, "git_list_tags", None) or getattr(git_utils, "_git_list_tags", None)
        choose_best = getattr(git_utils, "choose_best_rgl_ref_from_tags", None) or getattr(git_utils, "_choose_best_rgl_ref_from_tags", None)

        gf_ver = detect_gf_version(config.GF_BIN, config.ROOT_DIR) if detect_gf_version else None
        tags = list_tags(config.RGL_DIR, limit=200) if list_tags else []
        suggested = choose_best(gf_ver, tags) if choose_best else None
        if suggested:
            note = f"Suggested RGL ref from local tags: {suggested}"

    if config.ENFORCE_RGL_PIN is not None:
        enforce = config.ENFORCE_RGL_PIN
    else:
        enforce = bool(pin) or bool(env_rgl_ref)

    return ref, resolved, enforce, note


def _index_rgl_grammars(rgl_lang_dirs: List[Path]) -> Dict[str, Path]:
    idx: Dict[str, Path] = {}
    if not config.RGL_SRC.exists():
        return idx

    scan_roots: List[Path] = []
    if config.RGL_API.exists():
        scan_roots.append(config.RGL_API)
    scan_roots.extend([d for d in rgl_lang_dirs if d.exists()])

    for root in scan_roots:
        try:
            for g in root.rglob("Grammar*.gf"):
                suffix = g.stem.replace("Grammar", "").strip()
                if suffix and suffix not in idx:
                    idx[suffix] = g
        except Exception:
            continue

    return idx


def _find_bridge_file(suffix: str, grammar_parent: Optional[Path]) -> Optional[Path]:
    filename = f"Syntax{suffix}.gf"

    for d in gf_path.generated_src_candidates():
        p = d / filename
        if p.exists():
            return p

    if grammar_parent:
        p = grammar_parent / filename
        if p.exists():
            return p

    return None


def _require_alignment(tasks: List[Tuple[str, str]]) -> None:
    """
    Fail fast when HIGH_ROAD inputs are likely to fail due to missing RGL or missing Syntax bridges.
    Pin enforcement happens only when explicitly configured (pin file or env).
    """
    _ensure_executable_exists(config.GF_BIN)
    env_rgl_ref = _get_env_rgl_ref()

    high_road = [code for (code, strat) in tasks if strat == "HIGH_ROAD"]
    if high_road and not config.RGL_SRC.exists():
        raise RuntimeError(
            "gf-rgl/src not found.\n"
            f"Expected: {config.RGL_SRC}\n"
            "Fix:\n"
            "  - Ensure gf-rgl is cloned/available at repo_root/gf-rgl\n"
        )

    expected_ref, expected_commit, enforce_pin, note = _expected_rgl_pin()
    if note:
        logger.info(f"ℹ️  {note}")

    if enforce_pin:
        git_head = getattr(git_utils, "git_head", None) or getattr(git_utils, "_git_head", None)
        head = git_head(config.RGL_DIR) if (config.RGL_DIR.exists() and git_head) else None
        if not head:
            raise RuntimeError(
                "gf-rgl HEAD cannot be read.\n"
                "Expected gf-rgl to be a git repository at repo_root/gf-rgl.\n"
            )

        if expected_commit:
            if head != expected_commit:
                git_list_tags = getattr(git_utils, "git_list_tags", None) or getattr(git_utils, "_git_list_tags", None)
                tags = git_list_tags(config.RGL_DIR, limit=12) if git_list_tags else []
                tags_msg = ("\nRecent tags:\n  " + "\n  ".join(tags)) if tags else ""
                raise RuntimeError(
                    "gf-rgl is not pinned to the expected ref.\n"
                    f"  ref:      {expected_ref or '(none)'}\n"
                    f"  expected: {expected_commit}\n"
                    f"  actual:   {head}\n"
                    "Fix:\n"
                    "  1) run alignment, or\n"
                    f"  2) git -C gf-rgl fetch --tags --prune && git -C gf-rgl checkout {expected_ref or expected_commit}\n"
                    "  3) python tools/bootstrap_tier1.py --force\n"
                    f"{tags_msg}\n"
                )
        else:
            git_list_tags = getattr(git_utils, "git_list_tags", None) or getattr(git_utils, "_git_list_tags", None)
            tags = git_list_tags(config.RGL_DIR, limit=12) if git_list_tags else []
            tags_msg = ("\nRecent tags:\n  " + "\n  ".join(tags)) if tags else ""
            raise RuntimeError(
                "gf-rgl pin ref cannot be resolved.\n"
                f"  ref: {expected_ref or '(none)'}\n"
                "Fix:\n"
                "  git -C gf-rgl fetch --tags --prune\n"
                "  (or set SEMANTIK_ARCHITECT_RGL_REF to a valid tag/branch/commit)\n"
                f"{tags_msg}\n"
            )
    else:
        if not (env_rgl_ref or config.RGL_PIN_FILE.exists()):
            logger.warning(
                "⚠️  RGL pin not configured (no data/config/rgl_pin.json and no SEMANTIK_ARCHITECT_RGL_REF). "
                "Build will proceed without deterministic pin enforcement."
            )

    if not high_road:
        return

    rgl_lang_dirs = gf_path.discover_rgl_lang_dirs()
    rgl_idx = _index_rgl_grammars(rgl_lang_dirs)

    missing_bridge: List[Tuple[str, str, Optional[Path]]] = []
    for code in high_road:
        suffix = iso_map.get_wiki_suffix(code)
        grammar_path = rgl_idx.get(suffix)
        grammar_parent = grammar_path.parent if grammar_path else None
        bridge = _find_bridge_file(suffix, grammar_parent)
        if not bridge:
            missing_bridge.append((code, suffix, grammar_parent))

    if missing_bridge:
        lines = ["Missing required Syntax bridge files for HIGH_ROAD languages:"]
        for code, suffix, parent in missing_bridge[:30]:
            if parent is None:
                lines.append(
                    f"  - {code}: cannot find Grammar{suffix}.gf in RGL scan; HIGH_ROAD likely unsupported for this suffix"
                )
            else:
                lines.append(
                    f"  - {code}: expected Syntax{suffix}.gf either in generated/src or next to {parent}"
                )
        lines.append("Fix:")
        lines.append("  python tools/bootstrap_tier1.py --force")
        raise RuntimeError("\n".join(lines))


# -----------------------------------------------------------------------------
# Source resolution
# -----------------------------------------------------------------------------
def _safe_mode_source_path(gf_filename: str) -> Path:
    return config.SAFE_MODE_SRC / gf_filename


def _is_safe_mode_file(p: Path) -> bool:
    try:
        if not p.exists():
            return False
        head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        return config.SAFE_MODE_MARKER in head
    except Exception:
        return False


def _validate_strategy(strategy: str) -> str:
    s = (strategy or "").strip().upper()
    if s not in ("HIGH_ROAD", "SAFE_MODE"):
        raise ValueError(f"Invalid strategy '{strategy}'. Expected HIGH_ROAD or SAFE_MODE.")
    return s


def ensure_source_exists(lang_code: str, strategy: str, *, regen_safe: bool = False) -> Path:
    """
    Ensures the .gf source file exists before compilation.
    Returns the path that will be compiled.

    HIGH_ROAD: must exist in gf/
    SAFE_MODE: always lives under SAFE_MODE_SRC to avoid stale HIGH_ROAD contamination.
    """
    _ensure_dirs()
    strategy = _validate_strategy(strategy)
    lang_code = (lang_code or "").strip()

    gf_filename = iso_map.get_gf_name(lang_code)

    # ADR 006: Tier 2 overrides
    contrib_path = config.CONTRIB_DIR / lang_code / gf_filename
    if contrib_path.exists():
        return contrib_path

    if strategy == "HIGH_ROAD":
        p = config.GF_DIR / gf_filename
        if p.exists():
            return p
        raise FileNotFoundError(f"Missing HIGH_ROAD source: {p}")

    # SAFE_MODE: deterministic, isolated, stamped.
    target_file = _safe_mode_source_path(gf_filename)

    if target_file.exists() and _is_safe_mode_file(target_file) and not regen_safe:
        return target_file

    if not generate_safe_mode_grammar:
        raise RuntimeError(f"Grammar Factory not imported. Cannot generate SAFE_MODE for {lang_code}.")

    logger.info(f"🔨 Generating SAFE_MODE grammar for {lang_code} -> {_relpath(config.ROOT_DIR, target_file)}")

    code = generate_safe_mode_grammar(lang_code)
    stamped = (
        f"{config.SAFE_MODE_MARKER}\n"
        f"-- lang={lang_code}\n"
        f"-- generated_at={time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{code}"
    )

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(stamped, encoding="utf-8")
    return target_file


# -----------------------------------------------------------------------------
# Compilation + Linking
# -----------------------------------------------------------------------------
def compile_gf(lang_code: str, strategy: str, *, regen_safe: bool = False) -> Tuple[subprocess.CompletedProcess, Path]:
    """
    Compiles a single language to a .gfo object file (Phase 1).
    Returns (proc, source_path).
    """
    _ensure_dirs()
    strategy = _validate_strategy(strategy)
    lang_code = (lang_code or "").strip()

    gf_filename = iso_map.get_gf_name(lang_code)
    source_path = ensure_source_exists(lang_code, strategy, regen_safe=regen_safe)

    cmd = [
        config.GF_BIN,
        "-batch",
        "-path",
        gf_path.gf_path_args(),
        "-c",
        str(source_path.resolve()),
    ]
    proc = _run(cmd, cwd=config.GF_DIR)

    if proc.returncode != 0:
        log_path = config.LOG_DIR / f"{gf_filename}.log"
        try:
            log_path.write_text(
                _format_cmd(cmd) + "\n\n" + (proc.stderr or "") + "\n" + (proc.stdout or ""),
                encoding="utf-8",
            )
        except Exception:
            pass
        logger.error(f"   [STDERR {lang_code}] {(proc.stderr or '').strip()[-500:]}")
        logger.error(f"   [LOG] See {log_path}")

    return proc, source_path


def phase_1_verify(lang_code: str, strategy: str, *, regen_safe: bool = False) -> Tuple[str, bool, str, Optional[Path]]:
    """Phase 1: Verify compilation of individual languages."""
    try:
        proc, src = compile_gf(lang_code, strategy, regen_safe=regen_safe)
    except Exception as e:
        return (lang_code, False, str(e), None)

    if proc.returncode == 0:
        return (lang_code, True, "OK", src)

    msg = (proc.stderr or "").strip() or (proc.stdout or "").strip() or f"Unknown Error (Exit Code {proc.returncode})"
    return (lang_code, False, msg, src)


@dataclass(frozen=True)
class LinkedLang:
    code: str
    strategy: str
    source_path: Path


def _find_any_pgf_candidate() -> Optional[Path]:
    try:
        pgfs = list(config.GF_DIR.glob("*.pgf"))
    except Exception:
        return None
    if not pgfs:
        return None
    # Prefer known legacy names; otherwise pick the most recently modified PGF.
    for fname in LEGACY_PGF_FILENAMES:
        p = config.GF_DIR / fname
        if p.exists():
            return p
    pgfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pgfs[0]


def phase_2_link(valid_langs: List[LinkedLang]) -> Path:
    """Phase 2: Link all valid languages into a single semantik_architect.pgf binary."""
    start_time = time.time()
    logger.info("\n=== PHASE 2: LINKING PGF ===")

    if not valid_langs:
        logger.error("❌ No valid languages to link! Build aborted.")
        raise SystemExit(1)

    main_abstract = config.GF_DIR / "SemantikArchitect.gf"
    if not main_abstract.exists():
        raise FileNotFoundError(f"Missing main abstract grammar: {main_abstract}")

    # Deterministic order for linking.
    ordered = sorted(valid_langs, key=lambda x: x.code)
    targets = [str(ll.source_path.resolve()) for ll in ordered]

    # IMPORTANT: -name controls the produced <name>.pgf filename.
    pgf_name = PGF_BASENAME
    expected_pgf = config.GF_DIR / f"{pgf_name}.pgf"

    cmd = [
        config.GF_BIN,
        "-make",
        "-path",
        gf_path.gf_path_args(),
        "-name",
        pgf_name,
        main_abstract.name,  # run in cwd=config.GF_DIR
        *targets,
    ]

    logger.info(f"🔗 Linking {len(targets)} languages...")
    logger.info(f"   [CMD] {_format_cmd(cmd)}")

    proc = _run(cmd, cwd=config.GF_DIR)
    duration = time.time() - start_time

    if proc.returncode == 0:
        logger.info(f"✅ BUILD SUCCESS: {expected_pgf.name} created in {duration:.2f}s")

        if not expected_pgf.exists():
            # Robust fallback: if GF produced a differently-cased or legacy-named PGF, copy it to expected name.
            candidate = _find_any_pgf_candidate()
            if candidate and candidate.exists():
                try:
                    shutil.copyfile(candidate, expected_pgf)
                    logger.warning(
                        f"⚠️ PGF produced as {candidate.name}; copied to expected {expected_pgf.name}."
                    )
                except Exception:
                    pass

        if expected_pgf.exists():
            size_mb = expected_pgf.stat().st_size / (1024 * 1024)
            logger.info(f"   [ARTIFACT] {expected_pgf} ({size_mb:.2f} MB)")
        else:
            logger.warning(f"⚠️ Build reported success but {expected_pgf.name} not found.")
        return expected_pgf

    logger.error(f"❌ LINK FAILED in {duration:.2f}s")
    if proc.stderr:
        logger.error(f"   [STDERR]\n{proc.stderr.strip()}")
    if proc.stdout:
        logger.error(f"   [STDOUT]\n{proc.stdout.strip()}")
    raise SystemExit(proc.returncode or 1)


# -----------------------------------------------------------------------------
# Programmatic API
# -----------------------------------------------------------------------------
def build_pgf(
    *,
    strategy: str = "AUTO",
    langs: Optional[List[str]] = None,
    clean: bool = False,
    verbose: bool = False,
    max_workers: Optional[int] = None,
    no_preflight: bool = False,
    regen_safe: bool = False,
) -> Path:
    """
    Programmatic entrypoint (usable by API/worker without spawning another process).
    Returns path to semantik_architect.pgf.
    """
    _ensure_dirs()

    if verbose:
        logger.setLevel(logging.DEBUG)

    if clean:
        clean_artifacts()

    start_global = time.time()
    matrix = load_matrix()
    tasks: List[Tuple[str, str]] = []

    strat_in = (strategy or "").strip().upper()
    if strat_in != "AUTO":
        forced = _validate_strategy(strat_in)
        selected = [c.strip() for c in (langs or ["en"]) if c and c.strip()]
        tasks = [(code, forced) for code in selected]
        logger.info(f"⚙️  Forced strategy: {forced} for {len(tasks)} language(s)")
    else:
        if matrix:
            langs_filter = set([c.strip() for c in langs]) if langs else None
            languages = matrix.get("languages", {})
            if isinstance(languages, dict):
                for code, data in languages.items():
                    if not isinstance(code, str):
                        continue
                    code = code.strip()
                    if not code:
                        continue
                    if langs_filter is not None and code not in langs_filter:
                        continue

                    blob = data if isinstance(data, dict) else {}
                    verdict = blob.get("verdict") or blob.get("status") or {}
                    verdict = verdict if isinstance(verdict, dict) else {}
                    strat = str(verdict.get("build_strategy") or "SKIP").strip().upper()

                    if strat in ("HIGH_ROAD", "SAFE_MODE"):
                        tasks.append((code, strat))

        if not tasks:
            logger.info("⚠️  No tasks from matrix. Using bootstrap defaults.")
            tasks = [("en", "HIGH_ROAD")]

    # Deterministic compilation order (execution may still be parallel).
    tasks = sorted(tasks, key=lambda x: x[0])

    _ensure_executable_exists(config.GF_BIN)

    if not no_preflight:
        _require_alignment(tasks)

    logger.info("=== PHASE 1: COMPILATION ===")
    logger.info(f"Targeting {len(tasks)} languages")
    logger.info(f"GF_BIN: {config.GF_BIN}")
    logger.info(f"GF_DIR: {_relpath(config.ROOT_DIR, config.GF_DIR)}")
    logger.info(f"SAFE_MODE_SRC: {_relpath(config.ROOT_DIR, config.SAFE_MODE_SRC)}")
    logger.info(
        "Generated candidates: "
        + ", ".join(_relpath(config.ROOT_DIR, p) for p in gf_path.generated_src_candidates())
    )

    valid: List[LinkedLang] = []
    phase1_start = time.time()

    workers = max_workers or min(32, max(1, (os.cpu_count() or 4)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(phase_1_verify, code, strat, regen_safe=regen_safe): (code, strat)
            for (code, strat) in tasks
        }

        for future in concurrent.futures.as_completed(futures):
            code, strat = futures[future]
            try:
                lang, success, msg, src = future.result()
                if success and src is not None:
                    valid.append(LinkedLang(code=lang, strategy=strat, source_path=src))
                    logger.info(f"  [OK] {lang} ({strat})")
                else:
                    first = (msg.splitlines()[0] if msg else "Unknown error")[:140]
                    logger.warning(
                        f"  [SKIP] {lang} ({strat}): Compilation failed. Human intervention required via /tools (HITL). "
                        f"Error: {first}..."
                    )
            except Exception as e:
                logger.warning(
                    f"  [SKIP] {code} ({strat}): Source missing or error. Human intervention required (HITL). Details: {e}"
                )

    logger.info(f"Phase 1 complete in {time.time() - phase1_start:.2f}s")

    pgf_path = phase_2_link(valid)

    total_duration = time.time() - start_global
    logger.info("\n=== BUILD SUMMARY ===")
    logger.info(f"Total Duration: {total_duration:.2f}s")
    logger.info(f"Languages: {len(valid)}/{len(tasks)} compiled")
    logger.info(f"PGF: {pgf_path}")

    return pgf_path