# tools/language_health.py
# Merged tool: tools/audit_languages.py  +  tools/check_all_languages.py
#
# What it does:
#   - Compile audit: runs `gf -make` against generated/src/Wiki???.gf (auto-detected)
#     using ISO->Wiki mapping (data/config/iso_to_wiki.json) when available.
#   - Runtime audit: calls the Architect API and POSTs a small test frame to /generate/{lang}
#
# Outputs:
#   - data/indices/audit_cache.json        (compile cache)
#   - data/reports/audit_report.json       (combined report: compile + runtime)
#
# Features (v2.3):
#   - Rich verbose logging (--verbose) with secret redaction
#   - Machine-readable summary (--json)
#   - Trace ID propagation (API header: x-trace-id)
#   - Robust path resolution (run from any CWD)
#   - API key resolution (CLI > env fallbacks) with source reporting
#   - Prelude.gf path auto-discovery for GF compilation

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------------------------------------------------------
# REPO-RELATIVE PATHS
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]

CACHE_PATH = REPO_ROOT / "data" / "indices" / "audit_cache.json"
REPORT_PATH = REPO_ROOT / "data" / "reports" / "audit_report.json"

ISO_TO_WIKI_CANDIDATES = [
    REPO_ROOT / "data" / "config" / "iso_to_wiki.json",
    REPO_ROOT / "config" / "iso_to_wiki.json",
]

# Prefer the real generated language modules
COMPILE_SRC_CANDIDATES = [
    REPO_ROOT / "generated" / "src",
    REPO_ROOT / "gf" / "generated" / "src",
    REPO_ROOT / "gf",
]

RGL_ROOT = REPO_ROOT / "gf-rgl" / "src"
RGL_API = REPO_ROOT / "gf-rgl" / "src" / "api"


# -----------------------------------------------------------------------------
# DATA MODELS
# -----------------------------------------------------------------------------
@dataclass
class CompileResult:
    gf_lang: str
    filename: str  # repo-relative path (e.g. generated/src/WikiEng.gf)
    status: str  # VALID, BROKEN, SKIPPED
    error: Optional[str] = None
    duration_s: float = 0.0
    file_hash: str = ""
    iso2: Optional[str] = None


@dataclass
class RuntimeResult:
    api_lang: str
    status: str  # PASS, FAIL
    http_status: Optional[int] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    sample_text: Optional[str] = None


@dataclass
class HealthRow:
    gf_lang: Optional[str] = None
    api_lang: Optional[str] = None
    compile: Optional[CompileResult] = None
    runtime: Optional[RuntimeResult] = None

    def overall_status(self) -> str:
        if self.compile and self.compile.status == "BROKEN":
            return "FAIL"
        if self.runtime and self.runtime.status == "FAIL":
            return "FAIL"
        executed = (self.compile is not None) or (self.runtime is not None)
        return "OK" if executed else "SKIPPED"


# -----------------------------------------------------------------------------
# API KEY RESOLUTION (avoid leaking secrets + show source in verbose)
# -----------------------------------------------------------------------------
def _resolve_api_key(cli_value: Optional[str]) -> tuple[Optional[str], str]:
    """
    Priority:
      1) CLI --api-key
      2) env ARCHITECT_API_KEY
      3) env AWA_API_KEY
      4) env API_SECRET
      5) env API_KEY
    """
    if cli_value:
        v = cli_value.strip()
        if v:
            return v, "cli"

    for name in ("ARCHITECT_API_KEY", "AWA_API_KEY", "API_SECRET", "API_KEY"):
        v = os.environ.get(name)
        if v and v.strip():
            return v.strip(), f"env:{name}"

    return None, "none"


def _redact_args_for_print(args: argparse.Namespace) -> dict:
    d = dict(vars(args))
    if d.get("api_key"):
        d["api_key"] = "***redacted***"
    return d


# -----------------------------------------------------------------------------
# HELPERS: ISO <-> WIKI
# -----------------------------------------------------------------------------
def _load_iso_to_wiki() -> Tuple[Dict[str, str], Dict[str, str], Optional[Path]]:
    """
    Returns:
      iso2_to_wiki: {"en": "Eng", "fr": "Fre", ...}
      wiki_to_iso2: {"Eng": "en", "Fre": "fr", ...}
    """
    src: Optional[Path] = None
    for p in ISO_TO_WIKI_CANDIDATES:
        if p.exists():
            src = p
            break
    if not src:
        return {}, {}, None

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}, src

    iso2_to_wiki: Dict[str, str] = {}
    for iso2, v in (data or {}).items():
        if not isinstance(iso2, str):
            continue
        iso2n = iso2.strip().lower()
        if len(iso2n) != 2:
            continue

        wiki: Optional[str] = None
        if isinstance(v, str):
            wiki = v
        elif isinstance(v, dict) and v.get("wiki"):
            wiki = str(v.get("wiki"))

        if not wiki:
            continue

        w = wiki.strip()
        # accept "WikiEng", "Eng", "WikiEng.gf", etc.
        if w.lower().startswith("wiki"):
            w = w[4:]
        if w.lower().endswith(".gf"):
            w = w[:-3]
        w = w.strip()
        if not w:
            continue
        iso2_to_wiki[iso2n] = w

    wiki_to_iso2: Dict[str, str] = {}
    for iso2n, w in iso2_to_wiki.items():
        if w and w not in wiki_to_iso2:
            wiki_to_iso2[w] = iso2n

    return iso2_to_wiki, wiki_to_iso2, src


def _detect_compile_src_dir() -> Tuple[Path, str]:
    for p in COMPILE_SRC_CANDIDATES:
        if p.is_dir() and list(p.glob("Wiki*.gf")):
            return p, str(p.relative_to(REPO_ROOT))
    # fallback (still return something reasonable)
    return (REPO_ROOT / "gf"), "gf"


def _is_language_wiki_file(path: Path) -> bool:
    # Only compile per-language modules like WikiEng.gf, WikiFre.gf, WikiAra.gf.
    # Exclude things like WikiLexicon.gf.
    name = path.name
    if not name.startswith("Wiki") or not name.endswith(".gf"):
        return False
    core = name[len("Wiki") : -len(".gf")]
    # typical RGL/Wiki codes are 3 letters (Eng, Fre, Ara, ...)
    return len(core) == 3 and core.isalpha()


def _find_prelude_dirs(max_hits: int = 5) -> List[Path]:
    """
    Find directories containing Prelude.gf under likely roots.
    Keeps it cheap by searching a few roots and stopping early.
    """
    roots = [
        REPO_ROOT / "gf-rgl",
        REPO_ROOT / "gf",
        REPO_ROOT,
    ]

    found: List[Path] = []
    seen: set[Path] = set()

    for r in roots:
        if not r.exists():
            continue
        try:
            for p in r.rglob("Prelude.gf"):
                parent = p.parent.resolve()
                if parent not in seen:
                    seen.add(parent)
                    found.append(parent)
                if len(found) >= max_hits:
                    return found
        except Exception:
            # rglob can fail on weird permissions; ignore and keep going
            continue

    return found


def _build_gf_path(compile_src_dir: Path) -> str:
    # Ensure Prelude.gf can be found if it exists anywhere in-repo (or vendored).
    prelude_dirs = _find_prelude_dirs()

    parts: List[Path] = []
    for p in [*prelude_dirs, RGL_ROOT, RGL_API, REPO_ROOT / "gf", compile_src_dir, REPO_ROOT]:
        if p.exists():
            parts.append(p)

    # gf uses os.pathsep separator on the platform
    return os.pathsep.join(str(p) for p in parts)


# -----------------------------------------------------------------------------
# COMPILE AUDIT
# -----------------------------------------------------------------------------
class LanguageCompilerAuditor:
    def __init__(self, compile_src_dir: Path, use_cache: bool = False):
        self.compile_src_dir = compile_src_dir
        self.use_cache = use_cache
        self.gf_path = _build_gf_path(compile_src_dir)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if CACHE_PATH.exists():
            try:
                return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def _get_file_hash(filepath: Path) -> str:
        hasher = hashlib.sha256()
        try:
            with filepath.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            return ""
        except Exception:
            return ""

    @staticmethod
    def _extract_error(text: str) -> str:
        lines = (text or "").strip().splitlines()
        for line in lines:
            s = line.strip()
            if "does not exist" in s:
                return s
            if "constant not found" in s:
                return s
            if "syntax error" in s:
                return s
        return lines[0].strip() if lines else "Unknown Error"

    def check_file(self, iso2: Optional[str], file_path: Path) -> CompileResult:
        filename = file_path.name
        gf_lang = filename.replace("Wiki", "").replace(".gf", "")
        rel = str(file_path.resolve().relative_to(REPO_ROOT.resolve()))
        current_hash = self._get_file_hash(file_path)

        # Fast path: skip unchanged VALID files
        if self.use_cache:
            cached = self.cache.get(rel) or self.cache.get(filename)  # backward compat
            if cached and cached.get("hash") == current_hash and cached.get("status") == "VALID":
                return CompileResult(
                    gf_lang=gf_lang,
                    filename=rel,
                    status="SKIPPED",
                    file_hash=current_hash,
                    iso2=iso2,
                )

        start = time.time()
        cmd = ["gf", "-make", "-path", self.gf_path, rel]

        try:
            proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
            dur = time.time() - start

            if proc.returncode == 0:
                return CompileResult(
                    gf_lang=gf_lang,
                    filename=rel,
                    status="VALID",
                    duration_s=dur,
                    file_hash=current_hash,
                    iso2=iso2,
                )

            err = self._extract_error(proc.stderr or proc.stdout)
            return CompileResult(
                gf_lang=gf_lang,
                filename=rel,
                status="BROKEN",
                error=err,
                duration_s=dur,
                file_hash=current_hash,
                iso2=iso2,
            )

        except FileNotFoundError as e:
            return CompileResult(
                gf_lang=gf_lang,
                filename=rel,
                status="BROKEN",
                error=f"Missing executable: {e}",
                file_hash=current_hash,
                iso2=iso2,
            )
        except Exception as e:
            return CompileResult(
                gf_lang=gf_lang,
                filename=rel,
                status="BROKEN",
                error=str(e),
                file_hash=current_hash,
                iso2=iso2,
            )


def _list_compile_targets(
    compile_src_dir: Path,
    iso2_to_wiki: Dict[str, str],
    wiki_to_iso2: Dict[str, str],
    lang_filter: set[str],
) -> List[Tuple[Optional[str], Path]]:
    """
    Returns list of (iso2, path). iso2 may be None if mapping is unknown.
    """
    targets: List[Tuple[Optional[str], Path]] = []

    # If we have the iso map, drive selection by iso2 codes (what API uses).
    if iso2_to_wiki:
        wanted_iso2: Optional[set[str]] = None
        if lang_filter:
            wanted_iso2 = set()
            for token in lang_filter:
                t = token.strip()
                if not t:
                    continue
                tl = t.lower()
                if len(tl) == 2:
                    wanted_iso2.add(tl)
                elif t in wiki_to_iso2:
                    wanted_iso2.add(wiki_to_iso2[t])
                elif tl in iso2_to_wiki:
                    wanted_iso2.add(tl)

        for iso2, wiki in sorted(iso2_to_wiki.items()):
            if wanted_iso2 is not None and iso2 not in wanted_iso2:
                continue
            p = compile_src_dir / f"Wiki{wiki}.gf"
            if p.exists():
                targets.append((iso2, p))

        return targets

    # Fallback: just glob language-like Wiki???.gf
    all_files = sorted(compile_src_dir.glob("Wiki*.gf"))
    for p in all_files:
        if not _is_language_wiki_file(p):
            continue
        if p.name.endswith(".SKIP"):
            continue

        iso2 = None
        wiki = p.name[len("Wiki") : -len(".gf")]
        if wiki in wiki_to_iso2:
            iso2 = wiki_to_iso2[wiki]

        if lang_filter:
            keep = False
            if iso2 and iso2.lower() in lang_filter:
                keep = True
            if wiki.lower() in lang_filter:
                keep = True
            if not keep:
                continue

        targets.append((iso2, p))
    return targets


# -----------------------------------------------------------------------------
# RUNTIME AUDIT (API)
# -----------------------------------------------------------------------------
class ArchitectApiRuntimeChecker:
    def __init__(self, api_url: str, api_key: Optional[str] = None, timeout_s: int = 20, trace_id: Optional[str] = None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.trace_id = trace_id

        self._requests = None
        try:
            import requests  # type: ignore
            self._requests = requests
        except Exception:
            self._requests = None

        self._languages_endpoint: Optional[str] = None
        self._generate_prefix: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.trace_id:
            headers["x-trace-id"] = self.trace_id
        return headers

    def _http_get_json(self, url: str) -> Tuple[int, Any, str]:
        if self._requests:
            try:
                resp = self._requests.get(url, headers=self._headers(), timeout=self.timeout_s)
                raw = resp.text
                try:
                    return resp.status_code, resp.json(), raw
                except Exception:
                    return resp.status_code, None, raw
            except Exception as e:
                return 0, None, str(e)

        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                status = getattr(resp, "status", 200)
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return status, json.loads(raw), raw
                except Exception:
                    return status, None, raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            return e.code, None, raw
        except Exception as e:
            return 0, None, str(e)

    def _http_post_json(self, url: str, payload: Any) -> Tuple[int, Any, str, float]:
        start = time.time()

        if self._requests:
            try:
                resp = self._requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout_s)
                dur_ms = (time.time() - start) * 1000
                raw = resp.text
                try:
                    return resp.status_code, resp.json(), raw, dur_ms
                except Exception:
                    return resp.status_code, None, raw, dur_ms
            except Exception as e:
                dur_ms = (time.time() - start) * 1000
                return 0, None, str(e), dur_ms

        import urllib.error
        import urllib.request

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                dur_ms = (time.time() - start) * 1000
                status = getattr(resp, "status", 200)
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return status, json.loads(raw), raw, dur_ms
                except Exception:
                    return status, None, raw, dur_ms
        except urllib.error.HTTPError as e:
            dur_ms = (time.time() - start) * 1000
            raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            return e.code, None, raw, dur_ms
        except Exception as e:
            dur_ms = (time.time() - start) * 1000
            return 0, None, str(e), dur_ms

    def _discover_endpoints(self) -> None:
        candidates = [
            (f"{self.api_url}/api/v1/languages", f"{self.api_url}/api/v1/generate"),
            (f"{self.api_url}/languages", f"{self.api_url}/generate"),
            (f"{self.api_url}/info", f"{self.api_url}/generate"),
        ]
        for lang_url, gen_prefix in candidates:
            status, data, _raw = self._http_get_json(lang_url)
            if status == 200 and data is not None:
                self._languages_endpoint = lang_url
                self._generate_prefix = gen_prefix
                return

        self._languages_endpoint = f"{self.api_url}/api/v1/languages"
        self._generate_prefix = f"{self.api_url}/api/v1/generate"

    def discover_languages(self) -> List[str]:
        if not self._languages_endpoint:
            self._discover_endpoints()

        assert self._languages_endpoint is not None
        status, data, _raw = self._http_get_json(self._languages_endpoint)
        if status != 200 or data is None:
            return []

        if isinstance(data, dict):
            if isinstance(data.get("supported_languages"), list):
                return [str(x) for x in data["supported_languages"]]
            if isinstance(data.get("languages"), list):
                out: List[str] = []
                for item in data["languages"]:
                    if isinstance(item, dict) and item.get("code"):
                        out.append(str(item["code"]))
                return out
            return []

        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                out2: List[str] = []
                for item in data:
                    if isinstance(item, dict) and item.get("code"):
                        out2.append(str(item["code"]))
                return out2
            return [str(x) for x in data]

        return []

    def check_language(self, lang_code: str, payload: Dict[str, Any]) -> RuntimeResult:
        if not self._generate_prefix:
            self._discover_endpoints()
        assert self._generate_prefix is not None

        url = f"{self._generate_prefix}/{lang_code}"
        status, data, raw, dur_ms = self._http_post_json(url, payload)

        if status == 200 and isinstance(data, dict):
            txt = data.get("text")
            sample = str(txt)[:200] if txt else None
            return RuntimeResult(
                api_lang=lang_code,
                status="PASS",
                http_status=status,
                duration_ms=dur_ms,
                sample_text=sample,
            )

        err = raw[:500] if isinstance(raw, str) else str(raw)
        return RuntimeResult(
            api_lang=lang_code,
            status="FAIL",
            http_status=status if status != 0 else None,
            duration_ms=dur_ms,
            error=err,
        )


def _default_test_payload() -> Dict[str, Any]:
    return {
        "frame_type": "bio",
        "subject": {"name": "Alan Turing", "qid": "Q7251"},
        "properties": {"occupation": "Mathematician"},
    }


# -----------------------------------------------------------------------------
# REPORTING
# -----------------------------------------------------------------------------
def save_report(rows: List[HealthRow], old_compile_cache: Dict[str, Dict[str, Any]], write_disable_script: bool) -> None:
    compile_valid = sum(1 for r in rows if r.compile and r.compile.status in ("VALID", "SKIPPED"))
    compile_broken = sum(1 for r in rows if r.compile and r.compile.status == "BROKEN")
    runtime_pass = sum(1 for r in rows if r.runtime and r.runtime.status == "PASS")
    runtime_fail = sum(1 for r in rows if r.runtime and r.runtime.status == "FAIL")

    new_cache = dict(old_compile_cache or {})
    for row in rows:
        if not row.compile:
            continue
        c = row.compile
        new_cache[c.filename] = {
            "status": "VALID" if c.status in ("VALID", "SKIPPED") else "BROKEN",
            "hash": c.file_hash,
            "last_check": time.time(),
        }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    CACHE_PATH.write_text(json.dumps(new_cache, indent=2), encoding="utf-8")

    report_obj = {
        "generated_at": time.time(),
        "repo_root": str(REPO_ROOT),
        "summary": {
            "compile_valid_or_skipped": compile_valid,
            "compile_broken": compile_broken,
            "runtime_pass": runtime_pass,
            "runtime_fail": runtime_fail,
            "overall_ok": sum(1 for r in rows if r.overall_status() == "OK"),
            "overall_fail": sum(1 for r in rows if r.overall_status() == "FAIL"),
        },
        "results": [
            {
                "gf_lang": row.gf_lang,
                "api_lang": row.api_lang,
                "overall": row.overall_status(),
                "compile": asdict(row.compile) if row.compile else None,
                "runtime": asdict(row.runtime) if row.runtime else None,
            }
            for row in rows
        ],
    }

    REPORT_PATH.write_text(json.dumps(report_obj, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print("LANGUAGE HEALTH SUMMARY")
    print("=" * 70)
    print(f"✅ Compile VALID/SKIPPED: {compile_valid}")
    print(f"❌ Compile BROKEN      : {compile_broken}")
    print(f"✅ Runtime PASS        : {runtime_pass}")
    print(f"❌ Runtime FAIL        : {runtime_fail}")
    print(f"📄 Report written to   : {REPORT_PATH.relative_to(REPO_ROOT)}")

    if write_disable_script:
        broken_compile = [r.compile for r in rows if r.compile and r.compile.status == "BROKEN"]
        if broken_compile:
            script_path = REPO_ROOT / "disable_broken_compile.sh"
            with script_path.open("w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n# Generated by tools/language_health.py\nset -e\n")
                f.write('cd "$(dirname "$0")"\n')
                for c in broken_compile:
                    err = (c.error or "").replace("'", "")
                    f.write(f"echo 'Disabling {c.filename} ({err})'\n")
                    f.write(f"if [ -f '{c.filename}' ]; then mv '{c.filename}' '{c.filename}.SKIP'; fi\n")
            try:
                os.chmod(script_path, 0o755)
            except Exception:
                pass
            print(f"👉 Compile disable script: {script_path.name}")


def _print_verbose_start(args: argparse.Namespace, trace_id: str, compile_src_dir: Path, iso_map_path: Optional[Path], gf_path: str) -> None:
    print("=== LANGUAGE HEALTH CHECKER STARTED ===")
    print(f"Trace ID: {trace_id}")
    print(f"Args: {_redact_args_for_print(args)}")
    print(f"CWD: {os.getcwd()}")
    print(f"Repo Root: {REPO_ROOT}")
    print(f"Compile Src: {compile_src_dir.relative_to(REPO_ROOT)}")
    print(f"ISO Map: {iso_map_path.relative_to(REPO_ROOT) if iso_map_path else 'None'}")
    print(f"GF -path: {gf_path}")
    print(f"Python: {sys.version.split()[0]}")
    print("-" * 40)


def _print_json_summary(rows: List[HealthRow], trace_id: str) -> None:
    summary = {
        "trace_id": trace_id,
        "total_checked": len(rows),
        "status_counts": {
            "OK": sum(1 for r in rows if r.overall_status() == "OK"),
            "FAIL": sum(1 for r in rows if r.overall_status() == "FAIL"),
            "SKIPPED": sum(1 for r in rows if r.overall_status() == "SKIPPED"),
        },
        "failures": [
            {
                "lang": (r.api_lang or r.gf_lang),
                "reason": r.compile.error if r.compile and r.compile.status == "BROKEN" else (r.runtime.error if r.runtime else "Unknown"),
            }
            for r in rows
            if r.overall_status() == "FAIL"
        ],
    }
    print("\n--- JSON SUMMARY ---")
    print(json.dumps(summary, indent=2))
    print("--------------------")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid language audit (compile + API runtime)")
    parser.add_argument("--mode", choices=["compile", "api", "both"], default="both")
    parser.add_argument("--fast", action="store_true", help="Compile mode: skip unchanged VALID files (cache).")
    parser.add_argument("--parallel", type=int, default=(os.cpu_count() or 4))
    parser.add_argument("--api-url", default=os.environ.get("ARCHITECT_API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=None, help="API key for api-mode checks (CLI overrides env).")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--langs", nargs="*", help="Optional subset (e.g. en fr).")
    parser.add_argument("--no-disable-script", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", help="Output a JSON summary block at the end")

    args = parser.parse_args(argv)

    trace_id = os.environ.get("TOOL_TRACE_ID", str(uuid.uuid4()))

    # Resolve API key (CLI > env fallbacks)
    api_key, api_key_src = _resolve_api_key(args.api_key)
    args.api_key = api_key

    want_compile = args.mode in ("compile", "both")
    want_api = args.mode in ("api", "both")

    lang_filter = {x.strip().lower() for x in (args.langs or []) if x.strip()}

    # Resolve compile source dir and ISO map
    compile_src_dir, _label = _detect_compile_src_dir()
    iso2_to_wiki, wiki_to_iso2, iso_map_path = _load_iso_to_wiki()

    # Build GF path now (for verbose printing)
    gf_path = _build_gf_path(compile_src_dir)

    if args.verbose:
        _print_verbose_start(args, trace_id, compile_src_dir, iso_map_path, gf_path)
        if want_api:
            print(f"[INFO] API key source: {api_key_src}")

    # --- Runtime targets (discover from API; fallback to ISO map if needed)
    api_checker: Optional[ArchitectApiRuntimeChecker] = None
    api_codes: List[str] = []
    if want_api:
        if args.verbose:
            print(f"[INFO] Initializing API client against {args.api_url}")
        api_checker = ArchitectApiRuntimeChecker(
            api_url=args.api_url,
            api_key=args.api_key,
            timeout_s=args.timeout,
            trace_id=trace_id,
        )
        api_codes = api_checker.discover_languages()
        if not api_codes:
            if iso2_to_wiki:
                api_codes = sorted(iso2_to_wiki.keys())
                if args.verbose:
                    print(f"[WARN] API discovery returned no languages; falling back to iso_to_wiki.json ({len(api_codes)}).")
            elif args.verbose:
                print("[WARN] API discovery returned no languages and no iso_to_wiki.json found.")

    # --- Compile audit
    compile_results: Dict[str, CompileResult] = {}
    compiler: Optional[LanguageCompilerAuditor] = None
    if want_compile:
        compiler = LanguageCompilerAuditor(compile_src_dir=compile_src_dir, use_cache=args.fast)
        targets = _list_compile_targets(compile_src_dir, iso2_to_wiki, wiki_to_iso2, lang_filter)

        print(f"🧱 Compile audit: {len(targets)} file(s) (threads={args.parallel}, fast={args.fast})")
        if args.verbose and not targets:
            print("[WARN] No compile targets found (check generated/src and iso_to_wiki.json).")

        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(compiler.check_file, iso2, path): (iso2, path) for (iso2, path) in targets}
            for i, fut in enumerate(as_completed(futs), start=1):
                res = fut.result()
                key = (res.iso2 or res.gf_lang.lower())
                compile_results[key] = res
                icon = "✅" if res.status == "VALID" else "⏩" if res.status == "SKIPPED" else "❌"

                if args.verbose:
                    lang_label = res.iso2 or res.gf_lang
                    print(f"   [{i}/{len(targets)}] {icon} {lang_label:<5} | {res.duration_s:.2f}s | {res.status} | {res.filename}")
                    if res.error:
                        print(f"     ERROR: {res.error}")
                else:
                    sys.stdout.write(f"\r   [{i}/{len(targets)}] {icon} {(res.iso2 or res.gf_lang):<5}")
                    sys.stdout.flush()
        if not args.verbose:
            print()

    # --- Runtime audit
    runtime_results: Dict[str, RuntimeResult] = {}
    if want_api and api_checker:
        runtime_targets = list(api_codes)
        if lang_filter:
            runtime_targets = [c for c in runtime_targets if c.lower() in lang_filter]

        payload = _default_test_payload()
        print(f"🌐 Runtime audit: {len(runtime_targets)} language(s) (threads={args.parallel})")
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(api_checker.check_language, c, payload): c for c in runtime_targets}
            for i, fut in enumerate(as_completed(futs), start=1):
                res = fut.result()
                runtime_results[res.api_lang] = res
                icon = "✅" if res.status == "PASS" else "❌"

                if args.verbose:
                    print(f"   [{i}/{len(runtime_targets)}] {icon} {res.api_lang:<5} | {res.duration_ms:.2f}ms | {res.status}")
                    if res.error:
                        print(f"     ERROR: {res.error}")
                else:
                    sys.stdout.write(f"\r   [{i}/{len(runtime_targets)}] {icon} {res.api_lang:<5}")
                    sys.stdout.flush()
        if not args.verbose:
            print()

    # --- Merge into HealthRow list (join compile iso2 with runtime iso2)
    rows: List[HealthRow] = []
    used_api: set[str] = set()

    for key, comp in compile_results.items():
        api_code = comp.iso2 or key
        rt = runtime_results.get(api_code)
        if rt:
            used_api.add(api_code)
        rows.append(HealthRow(gf_lang=comp.gf_lang, api_lang=api_code, compile=comp, runtime=rt))

    for api_lang, rt in runtime_results.items():
        if api_lang in used_api:
            continue
        rows.append(HealthRow(gf_lang=None, api_lang=api_lang, compile=None, runtime=rt))

    rows.sort(key=lambda r: (0 if r.api_lang else 1, r.api_lang or "", r.gf_lang or ""))

    compile_cache = compiler.cache if compiler else {}
    save_report(rows, compile_cache, write_disable_script=(not args.no_disable_script))

    if args.json:
        _print_json_summary(rows, trace_id)

    return 2 if any(r.overall_status() == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
