# utils/eval_bios.py
"""
Evaluate biography rendering on a sample of Wikidata humans.

This script is intentionally lightweight and offline-friendly:

- It can:
    * read a preprocessed local JSON / JSONL / CSV file of people, OR
    * (optionally) query Wikidata SPARQL directly if `requests` is installed.

- For each person, it:
    * builds a minimal "bio frame" (name, gender, professions, nationalities),
    * calls `router.render_bio(...)` for one or more languages,
    * records whether a non-empty sentence was produced,
    * optionally compares against gold reference bios if present in the input.

Input schema (LOCAL MODE, recommended)
--------------------------------------

Each record should contain at least:

    {
        "id": "Q7186",                        # Wikidata QID (or any stable id)
        "label": "Marie Curie",             # Display name
        "gender": "female",                 # 'male' / 'female' / 'other'
        "profession_lemmas": ["physicist"],
        "nationality_lemmas": ["polish"],

        # Optional: gold reference bios, keyed by language code
        "gold_bios": {
            "en": "Marie Curie was a Polish-French physicist and chemist.",
            "fr": "Marie Curie est une physicienne et chimiste polonaise-française."
        }
    }

You can store these as:

- JSON array: [ {record1}, {record2}, ... ]
- JSONL / NDJSON: one JSON object per line
- CSV: with columns
    * id, label, gender,
    * profession_lemmas (comma-separated),
    * nationality_lemmas (comma-separated),
    * gold_bios (optional JSON string)

Wikidata live mode
------------------

If you pass `--source wikidata`, the script will:

- query the public Wikidata SPARQL endpoint,
- fetch a small sample of humans with:
    * label (EN),
    * gender,
    * up to a few occupations and nationalities,
- derive `profession_lemmas` and `nationality_lemmas` from English labels.

This is *only* meant as a quick demo; for serious experiments, use a local
preprocessed dump with a stable schema.

Usage
-----

From project root:

    python utils/eval_bios_from_wikidata.py \
        --source local \
        --input data/samples/wikidata_people_sample.jsonl \
        --langs fr it es \
        --limit 200 \
        --print-samples 5

or:

    python utils/eval_bios_from_wikidata.py \
        --source wikidata \
        --limit 100 \
        --langs en fr it

Output
------

- Summary coverage per language (how many bios were rendered).
- Optional CSV with per-person, per-language outputs if `--output-csv` is set.
- Optional printed samples for manual inspection.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# [FIX] Import v2.1 Engine instead of missing 'router'
from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.core.domain.frame import BioFrame

from utils.tool_logger import ToolLogger

# Setup logging
log = ToolLogger("eval_bios")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PersonRecord:
    """
    Minimal person representation for bio rendering.

    This is intentionally small; additional fields can be added later as needed.
    """

    id: str
    label: str
    gender: str = "unknown"
    profession_lemmas: List[str] = field(default_factory=list)
    nationality_lemmas: List[str] = field(default_factory=list)
    gold_bios: Dict[str, str] = field(default_factory=dict)


@dataclass
class EvalResult:
    """
    Per (person, language) evaluation outcome.
    """

    person_id: str
    lang: str
    rendered: bool
    output: str
    has_gold: bool
    exact_match: bool


# ---------------------------------------------------------------------------
# Helpers: normalization & IO
# ---------------------------------------------------------------------------


def _normalize_gender(raw: Any) -> str:
    if raw is None:
        return "unknown"
    s = str(raw).strip().lower()
    if s in {"male", "m", "man", "masculine", "q6581097"}:
        return "male"
    if s in {"female", "f", "woman", "feminine", "q6581072"}:
        return "female"
    return "unknown"


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # Comma-separated strings in CSV
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _load_json_records(path: Path) -> List[Dict[str, Any]]:
    log.info(f"Loading JSON records from {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        return json.loads(text)
    # Fallback: NDJSON / JSONL
    records: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _load_csv_records(path: Path) -> List[Dict[str, Any]]:
    log.info(f"Loading CSV records from {path}")
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def load_local_persons(path: Path) -> List[PersonRecord]:
    """
    Load person records from JSON / JSONL / CSV into PersonRecord objects.
    """
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        raw_records = _load_json_records(path)
    elif suffix in {".csv"}:
        raw_records = _load_csv_records(path)
    else:
        raise ValueError(f"Unsupported input extension: {suffix}")

    persons: List[PersonRecord] = []

    for rec in raw_records:
        try:
            pid = str(rec.get("id") or rec.get("qid") or "").strip()
            if not pid:
                log.warning(f"Skipping record without id: {rec}")
                continue

            label = str(rec.get("label") or rec.get("name") or pid).strip()
            gender = _normalize_gender(rec.get("gender"))

            prof_lemmas = _ensure_list(
                rec.get("profession_lemmas")
                or rec.get("occupations")
                or rec.get("occupation_lemmas")
            )
            nat_lemmas = _ensure_list(
                rec.get("nationality_lemmas")
                or rec.get("nationalities")
                or rec.get("citizenship_lemmas")
            )

            gold_bios_raw = rec.get("gold_bios") or {}
            gold_bios: Dict[str, str] = {}

            if isinstance(gold_bios_raw, str):
                # Allow JSON string in CSV
                try:
                    gold_bios = json.loads(gold_bios_raw)
                except json.JSONDecodeError:
                    log.warning(
                        f"Could not parse gold_bios JSON for id={pid}: {gold_bios_raw}"
                    )
            elif isinstance(gold_bios_raw, dict):
                gold_bios = {
                    str(k): str(v).strip()
                    for k, v in gold_bios_raw.items()
                    if str(v).strip()
                }

            persons.append(
                PersonRecord(
                    id=pid,
                    label=label,
                    gender=gender,
                    profession_lemmas=prof_lemmas,
                    nationality_lemmas=nat_lemmas,
                    gold_bios=gold_bios,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.error(f"Error processing record {rec}: {exc}")

    log.info(f"Loaded {len(persons)} person records from {path}")
    return persons


# ---------------------------------------------------------------------------
# Wikidata SPARQL helper (optional)
# ---------------------------------------------------------------------------


def fetch_wikidata_persons(limit: int) -> List[PersonRecord]:
    """
    Fetch a small sample of humans from Wikidata via SPARQL.

    This uses the public SPARQL endpoint and `requests`. If `requests`
    is not installed, this function will raise a RuntimeError.

    The query retrieves:
        - QID
        - English label
        - gender
        - up to a few occupations (labels)
        - up to a few nationalities (labels)
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime-only path
        raise RuntimeError(
            "The 'requests' library is required for --source wikidata. "
            "Install it with 'pip install requests' or use --source local."
        ) from exc

    log.info(f"Querying Wikidata SPARQL endpoint for {limit} humans…")

    endpoint = "https://query.wikidata.org/sparql"

    # Simple sample; you can refine occupations/nationalities as needed.
    sparql = f"""
    SELECT ?person ?personLabel ?gender ?genderLabel ?occ ?occLabel ?nat ?natLabel
    WHERE {{
      ?person wdt:P31 wd:Q5 .
      OPTIONAL {{ ?person wdt:P21 ?gender. }}
      OPTIONAL {{ ?person wdt:P106 ?occ. }}
      OPTIONAL {{ ?person wdt:P27 ?nat. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit * 5}  # oversample for aggregation
    """

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "abstract-wiki-architect-eval/0.1 (tooling)",
    }

    resp = requests.get(endpoint, params={"query": sparql}, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    bindings = data.get("results", {}).get("bindings", [])
    agg: Dict[str, Dict[str, Any]] = {}

    def get_id(uri: str) -> str:
        # e.g. "http://www.wikidata.org/entity/Q7186" -> "Q7186"
        return uri.rsplit("/", 1)[-1]

    for row in bindings:
        person_uri = row.get("person", {}).get("value")
        if not person_uri:
            continue
        pid = get_id(person_uri)

        rec = agg.setdefault(
            pid,
            {
                "id": pid,
                "label": "",
                "gender": "",
                "professions": set(),
                "nationalities": set(),
            },
        )

        label = row.get("personLabel", {}).get("value")
        if label:
            rec["label"] = label

        gender_label = row.get("genderLabel", {}).get("value")
        if gender_label and not rec["gender"]:
            rec["gender"] = gender_label

        occ_label = row.get("occLabel", {}).get("value")
        if occ_label:
            rec["professions"].add(occ_label)

        nat_label = row.get("natLabel", {}).get("value")
        if nat_label:
            rec["nationalities"].add(nat_label)

        if len(agg) >= limit:
            # We oversampled rows but constrain final number of distinct persons
            # by dict size.
            continue

    persons: List[PersonRecord] = []
    for pid, rec in agg.items():
        label = rec.get("label") or pid
        gender = _normalize_gender(rec.get("gender"))
        # Use lower-cased English labels as canonical lemma keys
        prof_lemmas = [p.lower() for p in sorted(rec.get("professions") or [])]
        nat_lemmas = [n.lower() for n in sorted(rec.get("nationalities") or [])]

        persons.append(
            PersonRecord(
                id=pid,
                label=label,
                gender=gender,
                profession_lemmas=prof_lemmas,
                nationality_lemmas=nat_lemmas,
            )
        )

    log.info(f"Retrieved {len(persons)} distinct persons from Wikidata")
    return persons


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

# [FIX] Helper: Internal render adapter that mimics the old 'render_bio' interface
_engine = None

def _render_bio_adapter(
    name: str, 
    gender: str, 
    profession_lemma: str, 
    nationality_lemma: str, 
    lang_code: str
) -> str:
    """
    Adapts the old functional interface (render_bio) to the new Object-Oriented Engine (v2.1).
    """
    global _engine
    
    # 1. Initialize Engine (Lazy Singleton)
    if _engine is None:
        try:
            _engine = GFGrammarEngine()
        except Exception as e:
            log.error(f"Failed to initialize GFGrammarEngine: {e}")
            return ""

    if not _engine.grammar:
        log.warning("GFGrammarEngine loaded but no grammar found. Check Wiki.pgf.")
        return ""

    # 2. Construct v2.1 Frame
    frame = BioFrame(
        frame_type="bio",
        subject={
            "name": name,
            "gender": gender,
            "profession": profession_lemma,
            "nationality": nationality_lemma
        },
        # Back-compat for Entity object
        main_entity={"name": name, "gender": gender}
    )
    
    # 3. Execute
    try:
        # We run the async method synchronously here because this is a CLI script
        sentence = asyncio.run(_engine.generate(lang_code, frame))
        return sentence.text
    except Exception as e:
        log.warning(f"Rendering failed for {name} ({lang_code}): {e}")
        return ""


def evaluate_persons(
    persons: Iterable[PersonRecord],
    langs: List[str],
    max_items: Optional[int] = None,
) -> List[EvalResult]:
    """
    For each person and language, call `_render_bio_adapter` and collect results.
    """
    results: List[EvalResult] = []

    count = 0
    for person in persons:
        if max_items is not None and count >= max_items:
            break
        count += 1

        for lang in langs:
            # Choose a primary profession/nationality if available.
            prof_lemma = person.profession_lemmas[0] if person.profession_lemmas else ""
            nat_lemma = (
                person.nationality_lemmas[0] if person.nationality_lemmas else ""
            )

            output = ""
            rendered = False
            try:
                # [FIX] Call the adapter instead of missing router function
                output = _render_bio_adapter(
                    name=person.label,
                    gender=person.gender,
                    profession_lemma=prof_lemma,
                    nationality_lemma=nat_lemma,
                    lang_code=lang,
                )
                output = (output or "").strip()
                rendered = bool(output)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning(
                    f"Rendering failed for id={person.id}, lang={lang}: {exc}"
                )

            gold = person.gold_bios.get(lang)
            has_gold = gold is not None and gold.strip() != ""
            exact_match = has_gold and (gold.strip() == output)

            results.append(
                EvalResult(
                    person_id=person.id,
                    lang=lang,
                    rendered=rendered,
                    output=output,
                    has_gold=has_gold,
                    exact_match=exact_match,
                )
            )

    return results


def summarize_results(results: List[EvalResult]) -> None:
    """
    Print a compact textual summary to stdout.
    """
    if not results:
        print("No evaluation results.")
        return

    by_lang: Dict[str, List[EvalResult]] = {}
    for r in results:
        by_lang.setdefault(r.lang, []).append(r)

    print("\n=== Biography evaluation summary ===\n")
    print(f"Total person-language pairs: {len(results)}\n")

    header = (
        f"{'Lang':<6} {'Pairs':>8} {'Rendered':>10} {'Coverage%':>10} "
        f"{'HasGold':>8} {'ExactMatch':>11}"
    )
    print(header)
    print("-" * len(header))

    for lang, rs in sorted(by_lang.items()):
        total = len(rs)
        rendered = sum(1 for r in rs if r.rendered)
        has_gold = sum(1 for r in rs if r.has_gold)
        exact = sum(1 for r in rs if r.exact_match)
        coverage = 100.0 * rendered / total if total else 0.0
        exact_rate = 100.0 * exact / has_gold if has_gold else 0.0

        print(
            f"{lang:<6} {total:>8} {rendered:>10} {coverage:>9.1f}% "
            f"{has_gold:>8} {exact:>6} ({exact_rate:4.1f}%)"
        )

    print()


def dump_results_csv(results: List[EvalResult], path: Path) -> None:
    """
    Save detailed results to a CSV file for later analysis.
    """
    log.info(f"Writing detailed results CSV to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "person_id",
                "lang",
                "rendered",
                "has_gold",
                "exact_match",
                "output",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.person_id,
                    r.lang,
                    int(r.rendered),
                    int(r.has_gold),
                    int(r.exact_match),
                    r.output,
                ]
            )


def print_sample_outputs(
    persons: List[PersonRecord],
    results: List[EvalResult],
    langs: List[str],
    n_samples: int,
) -> None:
    """
    Print a few rendered bios per language for manual inspection.
    """
    if n_samples <= 0:
        return

    by_lang: Dict[str, List[EvalResult]] = {}
    for r in results:
        if r.rendered:
            by_lang.setdefault(r.lang, []).append(r)

    persons_by_id: Dict[str, PersonRecord] = {p.id: p for p in persons}

    print("\n=== Sample outputs ===\n")

    for lang in langs:
        lang_rs = by_lang.get(lang, [])
        if not lang_rs:
            print(f"[{lang}] No rendered outputs.")
            continue

        print(f"[{lang}]")
        sample = random.sample(lang_rs, min(n_samples, len(lang_rs)))
        for r in sample:
            person = persons_by_id.get(r.person_id)
            name = person.label if person else r.person_id
            print(f"- {name}: {r.output}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate render_bio() against Wikidata-derived people."
    )

    parser.add_argument(
        "--source",
        choices=["local", "wikidata"],
        default="local",
        help="Data source: 'local' JSON/CSV file or live 'wikidata' SPARQL.",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Path to local JSON/JSONL/CSV file (required for --source local).",
    )
    parser.add_argument(
        "--langs",
        type=str,
        default="en",
        help="Comma-separated list of language codes, e.g. 'en,fr,it'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of persons to evaluate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling / sample selection.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        help="Write detailed person-language results to this CSV path.",
    )
    parser.add_argument(
        "--print-samples",
        type=int,
        default=0,
        help="Print up to N rendered samples per language.",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    log.header({
        "Source": args.source,
        "Langs": args.langs,
        "Limit": args.limit
    })

    random.seed(args.seed)

    langs = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    if not langs:
        log.error("No languages specified via --langs.", fatal=True)

    if args.source == "local":
        if not args.input:
            log.error("--input is required when --source local (JSON/JSONL/CSV of people).", fatal=True)
        
        input_path = Path(args.input)
        if not input_path.exists():
            log.error(f"Input file not found: {input_path}", fatal=True)

        log.stage("Fetch", f"Loading persons from {input_path}...")
        persons = load_local_persons(input_path)

    else:  # args.source == "wikidata"
        log.stage("Fetch", f"Querying Wikidata for {args.limit} persons...")
        persons = fetch_wikidata_persons(limit=args.limit)

    if not persons:
        log.error("No person records loaded; nothing to evaluate.", fatal=True)

    # If we fetched more than limit in local mode, subsample.
    if args.source == "local" and len(persons) > args.limit:
        log.info(
            f"Subsampling {args.limit} persons out of {len(persons)} with seed={args.seed}"
        )
        persons = random.sample(persons, args.limit)

    log.stage("Evaluate", f"Rendering bios for {len(persons)} persons in {len(langs)} languages...")
    
    results = evaluate_persons(persons, langs, max_items=args.limit)
    summarize_results(results)

    if args.output_csv:
        log.stage("Export", f"Writing results to {args.output_csv}")
        dump_results_csv(results, Path(args.output_csv))

    if args.print_samples > 0:
        print_sample_outputs(persons, results, langs, args.print_samples)

    log.summary({"Total Pairs": len(results)})


if __name__ == "__main__":
    main()