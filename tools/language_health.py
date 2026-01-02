# tools/language_health.py
# Merged tool: tools/audit_languages.py  +  tools/check_all_languages.py
#
# What it does:
#   - Compile audit: runs `gf -make` against gf/Wiki*.gf (with optional cache-fast-skip)
#   - Runtime audit: calls the Architect API and POSTs a small test frame to /generate/{lang}
#
# Outputs:
#   - data/indices/audit_cache.json        (compile cache)
#   - data/reports/audit_report.json       (combined report: compile + runtime)
#
# New Features (v2.1):
#   - Rich verbose logging (--verbose)
#   - Machine-readable summary (--json)
#   - Trace ID propagation

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_DIR = "gf-rgl/src"

CACHE_FILE = "data/indices/audit_cache.json"
REPORT_FILE = "data/reports/audit_report.json"

# Include ALL RGL folders to ensure we don't fail on missing shared paths
RGL_FOLDERS = [
    "api", "abstract", "common", "prelude",
    "romance", "germanic", "scandinavian", "slavic", "uralic", "hindustani", "semitic",
    "afrikaans", "amharic", "arabic", "basque", "bulgarian", "catalan",
    "chinese", "danish", "dutch", "english", "estonian", "finnish", "french",
    "german", "greek", "hebrew", "hindi", "hungarian", "icelandic",
    "indonesian", "italian", "japanese", "korean", "latin", "latvian",
    "lithuanian", "maltese", "mongolian", "nepali", "norwegian", "persian",
    "polish", "portuguese", "punjabi", "romanian", "russian", "sindhi",
    "slovenian", "somali", "spanish", "swahili", "swedish", "thai", "turkish",
    "urdu", "vietnamese", "xhosa", "yoruba", "zulu",
]


# -----------------------------------------------------------------------------
# DATA MODELS
# -----------------------------------------------------------------------------
@dataclass
class CompileResult:
    gf_lang: str
    filename: str
    status: str  # VALID, BROKEN, SKIPPED
    error: Optional[str] = None
    duration_s: float = 0.0
    file_hash: str = ""


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
# COMPILE AUDIT
# -----------------------------------------------------------------------------
class LanguageCompilerAuditor:
    def __init__(self, gf_dir: str = GF_DIR, rgl_dir: str = RGL_DIR, use_cache: bool = False):
        self.gf_dir = gf_dir
        self.abs_rgl = os.path.abspath(rgl_dir)
        self.paths = [os.path.join(self.abs_rgl, f) for f in RGL_FOLDERS]
        self.path_str = ":".join(self.paths)
        self.use_cache = use_cache
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @staticmethod
    def _get_file_hash(filepath: str) -> str:
        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
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

    def check_file(self, file_path: str) -> CompileResult:
        filename = os.path.basename(file_path)
        gf_lang = filename.replace("Wiki", "").replace(".gf", "")
        current_hash = self._get_file_hash(file_path)

        # Fast path: skip unchanged VALID files
        if self.use_cache:
            cached = self.cache.get(filename)
            if cached and cached.get("hash") == current_hash and cached.get("status") == "VALID":
                return CompileResult(gf_lang=gf_lang, filename=filename, status="SKIPPED", file_hash=current_hash)

        start = time.time()
        cmd = ["gf", "-make", "-path", self.path_str, filename]

        try:
            proc = subprocess.run(cmd, cwd=self.gf_dir, capture_output=True, text=True)
            dur = time.time() - start

            if proc.returncode == 0:
                return CompileResult(gf_lang=gf_lang, filename=filename, status="VALID", duration_s=dur, file_hash=current_hash)

            err = self._extract_error(proc.stderr or proc.stdout)
            return CompileResult(gf_lang=gf_lang, filename=filename, status="BROKEN", error=err, duration_s=dur, file_hash=current_hash)

        except FileNotFoundError as e:
            return CompileResult(gf_lang=gf_lang, filename=filename, status="BROKEN", error=f"Missing executable: {e}", file_hash=current_hash)
        except Exception as e:
            return CompileResult(gf_lang=gf_lang, filename=filename, status="BROKEN", error=str(e), file_hash=current_hash)


def _list_gf_wiki_files(gf_dir: str = GF_DIR) -> List[str]:
    files = sorted(glob.glob(os.path.join(gf_dir, "Wiki*.gf")))
    return [f for f in files if os.path.basename(f) != "Wiki.gf" and not f.endswith(".SKIP")]


def _gf_lang_from_filename(path: str) -> str:
    base = os.path.basename(path)
    return base.replace("Wiki", "").replace(".gf", "")


# -----------------------------------------------------------------------------
# RUNTIME AUDIT (API)
# -----------------------------------------------------------------------------
class ArchitectApiRuntimeChecker:
    def __init__(self, api_url: str, api_key: Optional[str] = None, timeout_s: int = 20):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

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
            headers["x-api-key"] = self.api_key
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

        # urllib fallback
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

        # urllib fallback
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
        # Prefer modern v2 paths first, but keep legacy fallback.
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

        # Last resort guess
        self._languages_endpoint = f"{self.api_url}/api/v1/languages"
        self._generate_prefix = f"{self.api_url}/api/v1/generate"

    def discover_languages(self) -> List[str]:
        if not self._languages_endpoint:
            self._discover_endpoints()

        assert self._languages_endpoint is not None
        status, data, _raw = self._http_get_json(self._languages_endpoint)
        if status != 200 or data is None:
            return []

        # /info legacy: {"supported_languages":[...]}
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

        # /languages may return list[str] or list[{"code":...}]
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
    # Safe baseline for /generate/{lang}: Frame-like payload.
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

    # Update compile cache
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

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(new_cache, f, indent=2)

    report_obj = {
        "generated_at": time.time(),
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

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_obj, f, indent=2)

    # Standard Human-Readable Summary
    print("\n" + "=" * 70)
    print("LANGUAGE HEALTH SUMMARY")
    print("=" * 70)
    print(f"✅ Compile VALID/SKIPPED: {compile_valid}")
    print(f"❌ Compile BROKEN      : {compile_broken}")
    print(f"✅ Runtime PASS        : {runtime_pass}")
    print(f"❌ Runtime FAIL        : {runtime_fail}")
    print(f"📄 Report written to   : {REPORT_FILE}")

    if write_disable_script:
        broken_compile = [r.compile for r in rows if r.compile and r.compile.status == "BROKEN"]
        if broken_compile:
            script_path = "disable_broken_compile.sh"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n# Generated by tools/language_health.py\nset -e\n")
                for c in broken_compile:
                    err = (c.error or "").replace("'", "")
                    f.write(f"echo 'Disabling {c.filename} ({err})'\n")
                    f.write(f"mv gf/{c.filename} gf/{c.filename}.SKIP\n")
            print(f"👉 Compile disable script: {script_path}")


def _print_verbose_start(args: argparse.Namespace, trace_id: str) -> None:
    print(f"=== LANGUAGE HEALTH CHECKER STARTED ===")
    print(f"Trace ID: {trace_id}")
    print(f"Args: {vars(args)}")
    print(f"CWD: {os.getcwd()}")
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
                "lang": r.gf_lang or r.api_lang,
                "reason": r.compile.error if r.compile and r.compile.status == "BROKEN" else (r.runtime.error if r.runtime else "Unknown")
            }
            for r in rows if r.overall_status() == "FAIL"
        ]
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
    parser.add_argument("--api-key", default=os.environ.get("ARCHITECT_API_KEY"))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--langs", nargs="*", help="Optional subset (e.g., eng fra Eng Fra).")
    parser.add_argument("--no-disable-script", action="store_true")
    
    # New flags for enhanced tooling support
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", help="Output a JSON summary block at the end")
    
    args = parser.parse_args(argv)

    # Generate or reuse trace ID
    trace_id = os.environ.get("TOOL_TRACE_ID", str(uuid.uuid4()))

    if args.verbose:
        _print_verbose_start(args, trace_id)

    want_compile = args.mode in ("compile", "both")
    want_api = args.mode in ("api", "both")

    lang_filter = {x.strip() for x in (args.langs or []) if x.strip()}

    # --- Compile targets
    gf_files = _list_gf_wiki_files(GF_DIR) if want_compile else []
    gf_by_code = {_gf_lang_from_filename(p): p for p in gf_files}

    # --- Runtime targets (discover from API; fallback to gf-derived guesses)
    api_checker: Optional[ArchitectApiRuntimeChecker] = None
    api_codes: List[str] = []
    if want_api:
        if args.verbose:
            print(f"[INFO] Initializing API client against {args.api_url}")
        api_checker = ArchitectApiRuntimeChecker(api_url=args.api_url, api_key=args.api_key, timeout_s=args.timeout)
        api_codes = api_checker.discover_languages()
        if not api_codes:
            if args.verbose:
                print(f"[WARN] API discovery returned no languages, falling back to GF file list.")
            api_codes = sorted({code.lower() for code in gf_by_code.keys()})
        elif args.verbose:
            print(f"[INFO] Discovered {len(api_codes)} languages from API.")

    # --- Run compile audit
    compile_results: Dict[str, CompileResult] = {}
    compiler: Optional[LanguageCompilerAuditor] = None
    if want_compile:
        compiler = LanguageCompilerAuditor(use_cache=args.fast)
        compile_targets = list(gf_files)
        if lang_filter:
            compile_targets = [
                path for gf_code, path in gf_by_code.items()
                if (gf_code in lang_filter) or (gf_code.lower() in lang_filter)
            ]

        print(f"🧱 Compile audit: {len(compile_targets)} file(s) (threads={args.parallel}, fast={args.fast})")
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(compiler.check_file, p): p for p in compile_targets}
            for i, fut in enumerate(as_completed(futs), start=1):
                res = fut.result()
                compile_results[res.gf_lang] = res
                icon = "✅" if res.status == "VALID" else "⏩" if res.status == "SKIPPED" else "❌"
                
                # Verbose mode prints full details, standard mode prints progress bar
                if args.verbose:
                    print(f"   [{i}/{len(compile_targets)}] {icon} {res.gf_lang:<10} | {res.duration_s:.2f}s | {res.status}")
                    if res.error:
                        print(f"     ERROR: {res.error}")
                else:
                    sys.stdout.write(f"\r   [{i}/{len(compile_targets)}] {icon} {res.gf_lang:<10}")
                    sys.stdout.flush()
        if not args.verbose:
            print()

    # --- Run runtime audit
    runtime_results: Dict[str, RuntimeResult] = {}
    if want_api and api_checker:
        runtime_targets = list(api_codes)
        if lang_filter:
            runtime_targets = [c for c in runtime_targets if (c in lang_filter) or (c.lower() in lang_filter)]

        payload = _default_test_payload()
        print(f"🌐 Runtime audit: {len(runtime_targets)} language(s) (threads={args.parallel})")
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(api_checker.check_language, c, payload): c for c in runtime_targets}
            for i, fut in enumerate(as_completed(futs), start=1):
                res = fut.result()
                runtime_results[res.api_lang] = res
                icon = "✅" if res.status == "PASS" else "❌"
                
                if args.verbose:
                    print(f"   [{i}/{len(runtime_targets)}] {icon} {res.api_lang:<10} | {res.duration_ms:.2f}ms | {res.status}")
                    if res.error:
                        print(f"     ERROR: {res.error}")
                else:
                    sys.stdout.write(f"\r   [{i}/{len(runtime_targets)}] {icon} {res.api_lang:<10}")
                    sys.stdout.flush()
        if not args.verbose:
            print()

    # --- Merge into HealthRow list
    rows: List[HealthRow] = []
    used_api: set[str] = set()

    for gf_lang, comp in compile_results.items():
        api_guess = gf_lang.lower()  # best-effort mapping (WikiEng.gf -> eng)
        rt = runtime_results.get(api_guess)
        if rt:
            used_api.add(api_guess)
        rows.append(HealthRow(gf_lang=gf_lang, api_lang=(api_guess if rt else None), compile=comp, runtime=rt))

    for api_lang, rt in runtime_results.items():
        if api_lang in used_api:
            continue
        rows.append(HealthRow(gf_lang=None, api_lang=api_lang, compile=None, runtime=rt))

    rows.sort(key=lambda r: (0 if r.gf_lang else 1, r.gf_lang or "", r.api_lang or ""))

    # --- Save report/cache
    compile_cache = compiler.cache if compiler else {}
    save_report(rows, compile_cache, write_disable_script=(not args.no_disable_script))

    # --- Optional JSON Summary Output
    if args.json:
        _print_json_summary(rows, trace_id)

    # Exit code (useful for CI)
    return 2 if any(r.overall_status() == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())