# tools/qa/ambiguity_detector.py
"""
Ambiguity Detector (AI-Assisted Quality Assurance).

This tool hunts for "Ambiguity Traps" in the grammar.
1) It generates (or accepts) sentences known to be linguistically fragile.
2) It parses them using the GF Engine.
3) It flags sentences that produce >1 Parse Tree (Syntactic Ambiguity).

Usage:
    python tools/qa/ambiguity_detector.py --lang eng --topic biography
    python tools/qa/ambiguity_detector.py --lang eng --sentence "I saw the man with the telescope"

Output:
    JSON report classifying sentences as:
      - SAFE (1 tree)
      - AMBIGUOUS (>1 trees)
      - FAIL_NO_PARSE (0 trees)
      - ERROR (exception)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Resolve PROJECT_ROOT and ensure imports work no matter where we run from ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.tool_logger import ToolLogger

log = ToolLogger("ambiguity_detector")

# --- Config import (support older/newer layouts) ---
try:
    from app.shared.config import settings
except Exception:
    try:
        from app.core.config import settings
    except Exception as e:
        log.error(f"Config import failed: {e}", fatal=True)

from app.adapters.engines.gf_wrapper import GFGrammarEngine

# --- Curated ambiguity seeds ---
STATIC_SEEDS: Dict[str, List[str]] = {
    "general": [
        "I saw the man with the telescope",  # Classic PP attachment ambiguity
        "Flying planes can be dangerous",  # Adjective vs Gerund
        "The fish is ready to eat",  # Subject vs Object
        "Time flies like an arrow",  # Noun vs Verb
    ],
    "biography": [
        "She is a French history professor",  # (French history) professor vs French (history professor)
        "He married the woman from Paris in 1990",  # Married in 1990 vs Woman from Paris (who was there in 1990)
        "The writer wrote the book on the table",  # Wrote (on the table) vs (Book on the table)
    ],
}


class AmbiguityDetector:
    def __init__(self, lang: str, pgf_path: Optional[str] = None, max_trees: int = 3):
        self.lang = (lang or "").strip()
        if not self.lang:
            log.error("--lang cannot be empty.", fatal=True)

        self.max_trees = max(0, int(max_trees))

        # Prefer explicit CLI arg; else settings.PGF_PATH (may be None and wrapper will fallback to env/default)
        lib_path = pgf_path or getattr(settings, "PGF_PATH", None)

        try:
            self.engine = GFGrammarEngine(lib_path=lib_path)
        except Exception as e:
            log.error(f"Could not initialize GFGrammarEngine: {e}", fatal=True)

        grammar = self.engine.grammar
        if not grammar:
            log.error(
                "GFGrammarEngine initialized but grammar is not loaded. "
                "Check PGF_PATH / AW_PGF_PATH (or your environment).",
                fatal=True,
            )

        self.concrete = self._resolve_concrete(self.lang)
        if not self.concrete:
            log.error(
                f"Language '{self.lang}' could not be resolved to a concrete PGF module.",
                fatal=True,
            )

    def _resolve_concrete(self, lang: str) -> Optional[str]:
        resolver = getattr(self.engine, "_resolve_concrete_name", None)
        if not callable(resolver):
            return None

        resolved = resolver(lang)
        if resolved:
            return resolved

        # Allow passing raw suffix without "Wiki" prefix.
        if not lang.startswith("Wiki"):
            return resolver(f"Wiki{lang}")

        return None

    def generate_candidates(self, topic: str) -> List[str]:
        topic = (topic or "").strip() or "general"
        seeds = STATIC_SEEDS.get(topic, STATIC_SEEDS["general"])
        log.stage("Generate", f"Loaded {len(seeds)} curated seed(s) for topic='{topic}'.")
        return seeds

    def analyze_sentence(self, sentence: str) -> Dict[str, Any]:
        sent = (sentence or "").strip()
        if not sent:
            return {"sentence": sentence, "tree_count": 0, "status": "ERROR", "error": "Empty sentence"}

        try:
            parses = self.engine.parse(sent, language=self.concrete)
            count = len(parses)

            status = "SAFE"
            if count == 0:
                status = "FAIL_NO_PARSE"
            elif count > 1:
                status = "AMBIGUOUS"

            trees: List[str] = []
            if status == "AMBIGUOUS" and self.max_trees != 0:
                cap = count if self.max_trees < 0 else min(count, self.max_trees)
                trees = [str(t) for t in parses[:cap]]

            return {
                "sentence": sent,
                "tree_count": count,
                "status": status,
                "trees": trees,
            }
        except Exception as e:
            return {
                "sentence": sent,
                "tree_count": 0,
                "status": "ERROR",
                "error": str(e),
            }

    def run_batch(self, sentences: List[str]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        stats = {"safe": 0, "ambiguous": 0, "fail": 0, "error": 0}

        for s in sentences:
            res = self.analyze_sentence(s)
            results.append(res)

            if res["status"] == "SAFE":
                stats["safe"] += 1
            elif res["status"] == "AMBIGUOUS":
                stats["ambiguous"] += 1
            elif res["status"] == "FAIL_NO_PARSE":
                stats["fail"] += 1
            else:
                stats["error"] += 1

        return {"summary": stats, "details": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect syntactic ambiguity in grammar.")
    parser.add_argument(
        "--lang",
        required=True,
        help="Target language code or Wiki concrete (e.g., eng, en, WikiEng).",
    )
    parser.add_argument("--sentence", help="Single sentence to check.")
    parser.add_argument("--topic", default="general", help="Topic for batch generation.")
    parser.add_argument("--json-out", help="Path to save JSON report.")
    parser.add_argument(
        "--pgf-path",
        help="Optional path to the .pgf file (overrides settings/env).",
    )
    parser.add_argument(
        "--max-trees",
        type=int,
        default=3,
        help="Max tree strings to include per ambiguous sentence (0 = none, -1 = all).",
    )

    args = parser.parse_args()

    mode = "Sentence Check" if args.sentence else f"Topic Batch ({args.topic})"
    log.header({"Language": args.lang, "Mode": mode, "MaxTrees": args.max_trees})

    detector = AmbiguityDetector(args.lang, pgf_path=args.pgf_path, max_trees=args.max_trees)

    # 1) Select mode
    if args.sentence:
        candidates = [args.sentence]
        log.stage("Input", "Using 1 provided sentence.")
    else:
        candidates = detector.generate_candidates(args.topic)

    # 2) Run analysis
    log.stage("Analysis", f"Parsing {len(candidates)} sentence(s) using '{detector.concrete}'...")
    report = detector.run_batch(candidates)

    # Add metadata (useful for saved reports)
    report["meta"] = {
        "lang_input": args.lang,
        "concrete": detector.concrete,
        "mode": mode,
        "topic": None if args.sentence else args.topic,
        "max_trees": args.max_trees,
    }

    # 3) Console report (stdout)
    log.info("")
    log.info("--- Metrics ---")
    log.info(f"Safe:      {report['summary']['safe']}")
    log.info(f"Ambiguous: {report['summary']['ambiguous']} (Requires disambiguation rules)")
    log.info(f"Failed:    {report['summary']['fail']} (No parse)")
    log.info(f"Errors:    {report['summary']['error']} (Exceptions)")
    log.info("---------------")

    for item in report["details"]:
        if item["status"] == "AMBIGUOUS":
            log.warning(f"Ambiguous: '{item['sentence']}'")
            log.info(f"  -> Found {item['tree_count']} interpretations.")
            for i, t in enumerate(item.get("trees", [])[:2]):
                log.info(f"     {i + 1}. {t}")
        elif item["status"] == "FAIL_NO_PARSE" and args.sentence:
            log.error(f"Parse failed: '{item['sentence']}' - No parse tree found.")

    # 4) Save JSON
    if args.json_out:
        out_path = Path(args.json_out)
        log.stage("Export", f"Saving report to {out_path}")
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to save JSON: {e}")

    success = report["summary"]["ambiguous"] == 0
    log.summary(
        {
            "Safe": report["summary"]["safe"],
            "Ambiguous": report["summary"]["ambiguous"],
            "Failed": report["summary"]["fail"],
            "Errors": report["summary"]["error"],
        },
        success=success,
    )

    # Exit code: 1 if ANY ambiguity found (so CI/CD can block ambiguous releases)
    raise SystemExit(1 if not success else 0)


if __name__ == "__main__":
    main()