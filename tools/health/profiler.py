"""
System Performance Profiler.

Runs a standard benchmark suite against the Grammar Engine to measure:
1. Latency (Time per linearization)
2. Throughput (Sentences per second)
3. Memory Footprint (Peak allocation during batch processing)

Usage:
    python tools/health/profiler.py --lang en --iterations 1000 --verbose
    python tools/health/profiler.py --update-baseline

Output:
    Console report and exit code 1 if performance degrades > 15% vs baseline.
"""

import argparse
import time
import json
import sys
import os
import tracemalloc
import traceback
from typing import List, Dict, Any, Optional
from pathlib import Path

# --- Setup Path to import from 'app' ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(root_dir)

try:
    from app.shared.config import settings
except ImportError:
    try:
        from app.core.config import settings
    except ImportError:
        print("[FATAL] Could not find 'settings' in app.shared.config or app.core.config", file=sys.stderr)
        sys.exit(1)

# [FIX] Import GFGrammarEngine explicitly
try:
    from app.adapters.engines.gf_wrapper import GFGrammarEngine
except ImportError as e:
    print(f"[FATAL] Import failed: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

BASELINE_FILE = os.path.join(current_dir, "performance_baseline.json")

# Standard "Stress Test" Intents (mix of simple and nested structures)
STRESS_PAYLOADS = [
    # Simple Bio
    {"function": "mkBioProf", "args": ["Marie Curie", "physicist"]},
    
    # [FIX] mkEvent Arity Correction & Safety
    # Old: 4 args ["E_WWII", "war", "1939", "1945"] -> CRASHED engine (expected 3)
    # New: 3 args. We group the date. If 'mkDateRange' doesn't exist, this might fail gracefully 
    # instead of crashing the C-runtime.
    {
        "function": "mkEvent", 
        "args": [
            "E_WWII", 
            "war", 
            # Grouping years into one argument to match typical 3-arg signature (Entity -> Kind -> Date)
            {"function": "mkDateRange", "args": ["1939", "1945"]}
        ]
    },

    # Deeply nested (simulated) - The engine will try to convert these to PGF trees
    {
        "function": "mkS",
        "args": [
            {
                "function": "mkCl",
                "args": [
                    {"function": "mkNP", "args": ["the_long_winding_road_N"]},
                    {"function": "mkVP", "args": ["lead_V2", "nowhere_Adv"]}
                ]
            }
        ]
    }
]

class Profiler:
    def __init__(self, lang: str, verbose: bool = False):
        self.lang = lang
        self.verbose = verbose
        self.concrete = f"Wiki{lang.capitalize()}" # Fallback if map lookup fails
        
        if self.verbose:
            print(f"[INFO] Initializing Profiler for language: {self.lang} ({self.concrete})")
            print(f"[INFO] Loading PGF from: {settings.PGF_PATH}")
            
        try:
            # [FIX] Use GFGrammarEngine
            self.engine = GFGrammarEngine(lib_path=settings.PGF_PATH)
            if self.verbose:
                print(f"[INFO] Engine loaded successfully. Available languages: {list(self.engine.grammar.languages.keys()) if self.engine.grammar else 'None'}")
        except Exception as e:
            print(f"[ERROR] Engine load failed: {e}")
            raise e

    def run_benchmark(self, iterations: int) -> Dict[str, float]:
        """
        Runs the stress payloads 'iterations' times.
        Returns stats dict.
        """
        if self.verbose:
            print(f"[INFO] Starting Benchmark: {iterations} iterations...")
            print(f"[INFO] Warmup phase (10 iterations)...")

        # Warmup
        for i in range(10):
            intent = STRESS_PAYLOADS[i % len(STRESS_PAYLOADS)]
            try:
                ast_str = self.engine._convert_to_gf_ast(intent, self.lang)
                self.engine.linearize(ast_str, language=self.concrete)
            except Exception:
                pass
        
        if self.verbose:
            print(f"[INFO] Warmup complete. Starting collection phase...")

        # Start Memory Tracing
        tracemalloc.start()
        start_time = time.perf_counter()

        success_count = 0
        error_count = 0
        
        log_interval = max(1, iterations // 10)

        # The loop
        for i in range(iterations):
            # Rotate through stress payloads
            intent = STRESS_PAYLOADS[i % len(STRESS_PAYLOADS)]
            
            try:
                # We interpret the intent to a raw GF tree string -> Linearize
                # Note: This tests the Python Adapter + GF C-Run-time speed
                ast_str = self.engine._convert_to_gf_ast(intent, self.lang)
                self.engine.linearize(ast_str, language=self.concrete)
                success_count += 1
            except Exception:
                error_count += 1

            if self.verbose and (i + 1) % log_interval == 0:
                print(f"[PROGRESS] Completed {i + 1}/{iterations} iterations...")

        end_time = time.perf_counter()
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_time = end_time - start_time
        avg_tps = iterations / total_time if total_time > 0 else 0
        avg_latency_ms = (total_time / iterations) * 1000 if iterations > 0 else 0
        peak_mb = peak_mem / (1024 * 1024)
        
        if self.verbose:
            print(f"[INFO] Benchmark complete. Total time: {total_time:.4f}s")
            print(f"[INFO] Successes: {success_count}, Errors: {error_count}")

        return {
            "total_time_sec": round(total_time, 4),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "throughput_tps": round(avg_tps, 2),
            "peak_memory_mb": round(peak_mb, 4),
            "success_rate": round(success_count / iterations, 2)
        }

def compare_baseline(current: Dict[str, float], baseline: Dict[str, float], threshold: float = 0.15) -> List[str]:
    """
    Returns a list of regression warnings if current stats are worse than baseline by > threshold %
    """
    warnings = []
    
    # 1. Check Latency (Lower is better)
    base_lat = baseline.get("avg_latency_ms", 0)
    curr_lat = current["avg_latency_ms"]
    if base_lat > 0:
        delta = (curr_lat - base_lat) / base_lat
        if delta > threshold:
            warnings.append(f"latency_degraded: {curr_lat}ms vs {base_lat}ms (+{delta:.1%})")

    # 2. Check Memory (Lower is better)
    base_mem = baseline.get("peak_memory_mb", 0)
    curr_mem = current["peak_memory_mb"]
    if base_mem > 0:
        delta = (curr_mem - base_mem) / base_mem
        if delta > threshold:
            warnings.append(f"memory_spike: {curr_mem}MB vs {base_mem}MB (+{delta:.1%})")

    return warnings

def main():
    parser = argparse.ArgumentParser(description="Performance Profiler")
    # [FIX] Default lang 'en' (2-letter)
    parser.add_argument("--lang", default="en", help="Target language to profile")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of linearizations to run")
    parser.add_argument("--update-baseline", action="store_true", help="Overwrite the baseline file with these results")
    parser.add_argument("--threshold", type=float, default=0.15, help="Regression threshold (0.15 = 15%)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")
    if args.verbose:
        print(f"=== PERFORMANCE PROFILER ===")
        print(f"Trace ID: {trace_id}")
        print(f"Args: {vars(args)}")
        print(f"CWD: {os.getcwd()}")
        print("-" * 40)

    # 1. Run Profile
    try:
        profiler = Profiler(args.lang, verbose=args.verbose)
        stats = profiler.run_benchmark(args.iterations)
    except Exception as e:
        print(f"CRITICAL: Benchmark crashed. {e}")
        # Print full traceback for debugging import errors
        traceback.print_exc()
        sys.exit(1)

    # 2. Print Results
    print("\n--- 📊 Results ---")
    print(json.dumps(stats, indent=2))

    # 3. Baseline Comparison
    baseline_path = Path(BASELINE_FILE)
    
    if args.update_baseline:
        try:
            with open(baseline_path, 'w') as f:
                json.dump(stats, f, indent=2)
            print(f"\n✅ Baseline updated at: {baseline_path.absolute()}")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Failed to write baseline: {e}")
            sys.exit(1)

    if baseline_path.exists():
        if args.verbose:
            print(f"\n[INFO] Loading baseline from: {baseline_path}")
            
        try:
            with open(baseline_path, 'r') as f:
                baseline = json.load(f)
            
            warnings = compare_baseline(stats, baseline, args.threshold)
            
            if warnings:
                print(f"\n❌ PERFORMANCE REGRESSION DETECTED (Threshold: {args.threshold:.0%})")
                for w in warnings:
                    print(f"   - {w}")
                sys.exit(1) # Fail the build
            else:
                print("\n✅ Performance is within acceptable limits.")
        except Exception as e:
            print(f"\n[WARN] Failed to read baseline: {e}")
    else:
        print(f"\nℹ️ No baseline found at {baseline_path}. Run with --update-baseline to save this state.")

if __name__ == "__main__":
    main()