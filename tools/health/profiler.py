"""
System Performance Profiler.

Runs a standard benchmark suite against the Grammar Engine to measure:
1. Latency (Time per linearization)
2. Throughput (Sentences per second)
3. Memory Footprint (Peak allocation during batch processing)

Usage:
    python tools/health/profiler.py --lang en --iterations 1000 --verbose
    python tools/health/profiler.py --update-baseline
    python tools/health/profiler.py --suite safe   # default (conversion + linearize)
    python tools/health/profiler.py --suite raw    # linearize-only (prebuilt valid ASTs)

Output:
    Console report and exit code 1 if performance degrades > 15% vs baseline,
    OR if any benchmark iteration fails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tracemalloc
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Project root & imports
# -----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Optional GUI-friendly logger
try:
    from utils.tool_logger import ToolLogger  # type: ignore

    log = ToolLogger("profiler")
except Exception:  # pragma: no cover
    class _FallbackLogger:
        def header(self, d: Dict[str, Any]) -> None:
            print("=== PERFORMANCE PROFILER ===")
            for k, v in d.items():
                print(f"{k}: {v}")

        def stage(self, name: str, msg: str) -> None:
            print(f"[{name}] {msg}")

        def info(self, msg: str = "") -> None:
            print(msg)

        def warning(self, msg: str) -> None:
            print(f"[WARN] {msg}")

        def error(self, msg: str) -> None:
            print(f"[ERROR] {msg}")

        def summary(self, d: Dict[str, Any], success: bool = True) -> None:
            print("\n=== SUMMARY ===")
            for k, v in d.items():
                print(f"{k}: {v}")
            print("STATUS:", "OK" if success else "FAIL")

    log = _FallbackLogger()

try:
    from app.shared.config import settings
except Exception:
    try:
        from app.core.config import settings  # type: ignore
    except Exception as e:
        print("[FATAL] Could not import settings from app.shared.config or app.core.config", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)

try:
    from app.adapters.engines.gf_wrapper import GFGrammarEngine
except Exception as e:
    print(f"[FATAL] Import failed: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

# "raw" suite needs pgf.Expr objects (still safe because ASTs are produced by our safe path)
try:
    import pgf  # type: ignore
except Exception:
    pgf = None  # type: ignore


BASELINE_FILE = Path(__file__).resolve().parent / "performance_baseline.json"


def _benchmark_key(lang: str, suite: str) -> str:
    return f"{(lang or '').strip().lower()}:{(suite or '').strip().lower()}"


def _is_failure_text(txt: str) -> bool:
    t = (txt or "").strip()
    if not t:
        return True
    if t.startswith("<LinearizeError"):
        return True
    if t.startswith("<GF Runtime Not Loaded>"):
        return True
    if t.startswith("<Language '"):
        return True
    return False


def _make_bio_payload(
    *,
    name: str,
    profession: Optional[str] = None,
    nationality: Optional[str] = None,
    gender: Optional[str] = None,
) -> Dict[str, Any]:
    # IMPORTANT: gf_wrapper._bio_fields reads profession/nationality from *subject*,
    # and _coerce_to_bio_frame will merge top-level fields into subject.
    payload: Dict[str, Any] = {"frame_type": "bio", "name": name}
    if profession:
        payload["profession"] = profession
    if nationality:
        payload["nationality"] = nationality
    if gender:
        payload["gender"] = gender
    return payload


@dataclass(frozen=True)
class SuitePrepared:
    payloads: List[Dict[str, Any]]
    ast_strings: List[str]
    expr_objects: Optional[List[Any]]  # pgf.Expr if available


class Profiler:
    def __init__(self, lang: str, verbose: bool = False):
        self.lang = (lang or "").strip()
        self.verbose = verbose

        self.engine = GFGrammarEngine()

        g = self.engine.grammar
        if not g:
            err = getattr(self.engine, "last_load_error", None) or "Unknown error"
            raise RuntimeError(f"GF grammar not loaded. PGF path: {getattr(self.engine, 'pgf_path', None)} | {err}")

        conc = self.engine._resolve_concrete_name(self.lang)
        if not conc:
            raise RuntimeError(f"Language '{self.lang}' not resolvable to a concrete grammar.")
        self.concrete = conc

        if self.verbose:
            langs = list(getattr(g, "languages", {}).keys())
            log.info(f"[INFO] PGF: {getattr(self.engine, 'pgf_path', '')}")
            log.info(f"[INFO] Concrete: {self.concrete}")
            log.info(f"[INFO] Loaded languages: {len(langs)}")

    def prepare_suite(self) -> SuitePrepared:
        # Keep this intentionally small and stable: these go through the Bio path
        # (mkBioProf/mkBioFull) and cannot trigger GF native aborts.
        payloads = [
            _make_bio_payload(name="Marie Curie", profession="physicist", nationality="polish", gender="f"),
            _make_bio_payload(name="Ada Lovelace", profession="mathematician", nationality="british", gender="f"),
            _make_bio_payload(name="Shaka", profession="warrior", nationality="zulu", gender="m"),
            _make_bio_payload(name="Alan Turing", profession="computer scientist", gender="m"),  # mkBioProf path
        ]

        ast_strings: List[str] = []
        for p in payloads:
            bio = self.engine._coerce_to_bio_frame(p)
            ast = self.engine._convert_to_gf_ast(bio, self.lang)
            ast_strings.append(ast)

        expr_objects: Optional[List[Any]] = None
        if pgf is not None:
            expr_objects = []
            for ast in ast_strings:
                expr_objects.append(pgf.readExpr(ast))

        return SuitePrepared(payloads=payloads, ast_strings=ast_strings, expr_objects=expr_objects)

    def run_benchmark(self, iterations: int, *, suite: str = "safe") -> Dict[str, Any]:
        suite = (suite or "safe").strip().lower()
        if suite not in {"safe", "raw"}:
            raise ValueError("suite must be 'safe' or 'raw'.")

        prepared = self.prepare_suite()

        warmup_n = min(10, max(0, iterations))
        if self.verbose:
            log.stage("Warmup", f"{warmup_n} iterations (suite={suite})")

        # Warmup
        for i in range(warmup_n):
            idx = i % len(prepared.ast_strings)
            if suite == "safe":
                bio = self.engine._coerce_to_bio_frame(prepared.payloads[idx])
                ast = self.engine._convert_to_gf_ast(bio, self.lang)
                _ = self.engine.linearize(ast, self.lang)
            else:
                if prepared.expr_objects is not None:
                    _ = self.engine.linearize(prepared.expr_objects[idx], self.lang)
                else:
                    _ = self.engine.linearize(prepared.ast_strings[idx], self.lang)

        if iterations <= 0:
            return {
                "lang": self.lang,
                "concrete": self.concrete,
                "suite": suite,
                "iterations": iterations,
                "total_time_sec": 0.0,
                "avg_latency_ms": 0.0,
                "throughput_tps": 0.0,
                "peak_memory_mb": 0.0,
                "success_rate": 0.0,
                "errors": 0,
            }

        if self.verbose:
            log.stage("Benchmark", f"Running {iterations} iterations (suite={suite})")

        tracemalloc.start()
        start = time.perf_counter()

        success = 0
        errors = 0
        log_interval = max(1, iterations // 10)

        for i in range(iterations):
            idx = i % len(prepared.ast_strings)

            try:
                if suite == "safe":
                    bio = self.engine._coerce_to_bio_frame(prepared.payloads[idx])
                    ast = self.engine._convert_to_gf_ast(bio, self.lang)
                    out = self.engine.linearize(ast, self.lang)
                else:
                    if prepared.expr_objects is not None:
                        out = self.engine.linearize(prepared.expr_objects[idx], self.lang)
                    else:
                        out = self.engine.linearize(prepared.ast_strings[idx], self.lang)

                if _is_failure_text(out):
                    errors += 1
                else:
                    success += 1

            except Exception:
                # Python-side exceptions are safe to catch; native aborts are prevented by design here.
                errors += 1

            if self.verbose and (i + 1) % log_interval == 0:
                log.info(f"[PROGRESS] {i + 1}/{iterations}")

        end = time.perf_counter()
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_s = max(0.0, end - start)
        denom = max(1, success + errors)

        stats: Dict[str, Any] = {
            "lang": self.lang,
            "concrete": self.concrete,
            "suite": suite,
            "iterations": iterations,
            "total_time_sec": round(total_s, 6),
            "avg_latency_ms": round((total_s / max(1, success)) * 1000.0, 4) if success else 0.0,
            "throughput_tps": round((success / total_s), 4) if total_s > 0 else 0.0,
            "peak_memory_mb": round(peak / (1024 * 1024), 6),
            "success_rate": round(success / denom, 4),
            "successes": success,
            "errors": errors,
        }

        # Provide a small sanity sample once per run (not per iteration)
        if self.verbose:
            samples: List[Tuple[str, str]] = []
            for p, ast in zip(prepared.payloads[:3], prepared.ast_strings[:3]):
                txt = self.engine.linearize(ast, self.lang)
                samples.append((p.get("name", "?"), (txt or "").strip()))
            stats["samples"] = [{"name": n, "output": t} for n, t in samples]

        return stats


def compare_baseline(current: Dict[str, Any], baseline: Dict[str, Any], threshold: float = 0.15) -> List[str]:
    warnings: List[str] = []

    def _num(d: Dict[str, Any], k: str) -> float:
        try:
            return float(d.get(k, 0) or 0)
        except Exception:
            return 0.0

    base_lat = _num(baseline, "avg_latency_ms")
    curr_lat = _num(current, "avg_latency_ms")
    if base_lat > 0:
        delta = (curr_lat - base_lat) / base_lat
        if delta > threshold:
            warnings.append(f"latency_degraded: {curr_lat}ms vs {base_lat}ms (+{delta:.1%})")

    base_mem = _num(baseline, "peak_memory_mb")
    curr_mem = _num(current, "peak_memory_mb")
    if base_mem > 0:
        delta = (curr_mem - base_mem) / base_mem
        if delta > threshold:
            warnings.append(f"memory_spike: {curr_mem}MB vs {base_mem}MB (+{delta:.1%})")

    return warnings


def _load_baselines(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_baselines(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Performance Profiler")
    parser.add_argument("--lang", default="en", help="Target language to profile (e.g., en, eng, WikiEng)")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of iterations")
    parser.add_argument("--suite", choices=["safe", "raw"], default="safe", help="safe=convert+linearize, raw=linearize-only")
    parser.add_argument("--update-baseline", action="store_true", help="Overwrite baseline for this (lang,suite)")
    parser.add_argument("--threshold", type=float, default=0.15, help="Regression threshold (0.15 = 15%)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")

    log.header(
        {
            "Trace ID": trace_id,
            "Lang": args.lang,
            "Suite": args.suite,
            "Iterations": args.iterations,
            "PGF": str(getattr(settings, "PGF_PATH", "")),
            "CWD": os.getcwd(),
        }
    )

    try:
        profiler = Profiler(args.lang, verbose=args.verbose)
        stats = profiler.run_benchmark(args.iterations, suite=args.suite)
    except Exception as e:
        log.error(f"CRITICAL: Benchmark failed: {e}")
        traceback.print_exc()
        sys.exit(1)

    log.info("")
    log.info("--- Results ---")
    log.info(json.dumps(stats, indent=2, ensure_ascii=False))

    # Fail fast if any iteration failed: benchmark is not valid if it produced errors.
    if int(stats.get("errors", 0) or 0) > 0:
        log.summary(
            {
                "Successes": stats.get("successes"),
                "Errors": stats.get("errors"),
                "Note": "One or more iterations failed; treat as FAIL.",
            },
            success=False,
        )
        sys.exit(1)

    key = _benchmark_key(args.lang, args.suite)
    baselines = _load_baselines(BASELINE_FILE)

    if args.update_baseline:
        baselines[key] = stats
        _save_baselines(BASELINE_FILE, baselines)
        log.summary({"Baseline": str(BASELINE_FILE), "Key": key, "Status": "UPDATED"}, success=True)
        sys.exit(0)

    baseline_entry: Optional[Dict[str, Any]] = None

    # Support legacy baseline format where the file itself was a single stats dict
    if any(k in baselines for k in ("avg_latency_ms", "peak_memory_mb", "throughput_tps")):
        baseline_entry = baselines
    else:
        maybe = baselines.get(key)
        baseline_entry = maybe if isinstance(maybe, dict) else None

    if baseline_entry:
        warnings = compare_baseline(stats, baseline_entry, args.threshold)
        if warnings:
            log.warning(f"PERFORMANCE REGRESSION (threshold={args.threshold:.0%})")
            for w in warnings:
                log.warning(f" - {w}")
            log.summary({"Key": key, "Regressions": len(warnings)}, success=False)
            sys.exit(1)

        log.summary({"Key": key, "Regressions": 0}, success=True)
        sys.exit(0)

    log.warning(f"No baseline found for key '{key}'. Run with --update-baseline to save this state.")
    log.summary({"Key": key, "Baseline": "MISSING"}, success=True)
    sys.exit(0)


if __name__ == "__main__":
    main()