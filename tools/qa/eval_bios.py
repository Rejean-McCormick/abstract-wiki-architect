# utils/eval_bios.py
"""
Evaluate biography rendering on a sample of Wikidata humans.

This script is intentionally lightweight and offline-friendly:

- It can:
    * read a preprocessed local JSON / JSONL / CSV file of people, OR
    * (optionally) query Wikidata SPARQL directly if `requests` is installed.

- For each person, it:
    * builds a minimal BioFrame payload (name, gender, profession, nationality),
    * renders bios via the v2.1 GFGrammarEngine,
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

This is only meant as a quick demo; for serious experiments, use a local
preprocessed dump with a stable schema.

Usage
-----

From project root:

    python utils/eval_bios.py \
        --source local \
        --input data/samples/wikidata_people_sample.jsonl \
        --langs fr it es \
        --limit 200 \
        --print-samples 5

or:

    python utils/eval_bios.py \
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
import os
import random
import sys
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ---------------------------------------------------------------------------
# Project bootstrap (run reliably from anywhere)
# ---------------------------------------------------------------------------


def _find_project_root(start: Path) -> Optional[Path]:
    """Walk up until we find a plausible repo root."""
    for p in [start, *start.parents]:
        if (p / "manage.py").exists() and (p / "app").exists():
            return p
        if (p / "pyproject.toml").exists() and (p / "app").exists():
            return p
    return None


THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _find_project_root(THIS_DIR) or _find_project_root(Path.cwd())

if PROJECT_ROOT and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep relative paths consistent (optional, but helps when launched by GUI/tool runners)
if PROJECT_ROOT:
    try:
        os.chdir(str(PROJECT_ROOT))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Imports that need the project root on sys.path
# ---------------------------------------------------------------------------

from app.adapters.engines.gf_wrapper import GFGrammarEngine  # noqa: E402
from app.core.domain.frame import BioFrame  # noqa: E402

from utils.tool_logger import ToolLogger  # noqa: E402

log = ToolLogger("eval_bios")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PersonRecord:
    """Minimal person representation for bio rendering."""

    id: str
    label: str
    gender: str = "unknown"
    profession_lemmas: List[str] = field(default_factory=list)
    nationality_lemmas: List[str] = field(default_factory=list)
    gold_bios: Dict[str, str] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Per (person, language) evaluation outcome."""

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
    """
    Normalize gender into the engine-friendly compact codes:
    - "m" / "f" / "" (unknown)
    """
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if s in {"male", "m", "man", "masculine", "q6581097"}:
        return "m"
    if s in {"female", "f", "woman", "feminine", "q6581072"}:
        return "f"
    return ""


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _load_json_records(path: Path) -> List[Dict[str, Any]]:
    log.info(f"Loading JSON records from {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        return json.loads(text)
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
    """Load person records from JSON / JSONL / CSV into PersonRecord objects."""
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        raw_records = _load_json_records(path)
    elif suffix == ".csv":
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
            gender = str(rec.get("gender") or "").strip()

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
                try:
                    gold_bios = json.loads(gold_bios_raw)
                except json.JSONDecodeError:
                    log.warning(f"Could not parse gold_bios JSON for id={pid}: {gold_bios_raw}")
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
        except Exception as exc:  # defensive
            log.error(f"Error processing record {rec}: {exc}")

    log.info(f"Loaded {len(persons)} person records from {path}")
    return persons


# ---------------------------------------------------------------------------
# Wikidata SPARQL helper (optional)
# ---------------------------------------------------------------------------


def fetch_wikidata_persons(limit: int) -> List[PersonRecord]:
    """
    Fetch a small sample of humans from Wikidata via SPARQL.

    Requires `requests`. If not installed, raises RuntimeError.
    """
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "The 'requests' library is required for --source wikidata. "
            "Install it with 'pip install requests' or use --source local."
        ) from exc

    log.info(f"Querying Wikidata SPARQL endpoint for {limit} humans…")

    endpoint = "https://query.wikidata.org/sparql"
    sparql = f"""
    SELECT ?person ?personLabel ?genderLabel ?occLabel ?natLabel
    WHERE {{
      ?person wdt:P31 wd:Q5 .
      OPTIONAL {{ ?person wdt:P21 ?gender. }}
      OPTIONAL {{ ?person wdt:P106 ?occ. }}
      OPTIONAL {{ ?person wdt:P27 ?nat. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT {limit * 5}
    """

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "semantik-architect-eval-bios/0.1 (tooling)",
    }

    resp = requests.get(endpoint, params={"query": sparql}, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    bindings = data.get("results", {}).get("bindings", [])
    agg: Dict[str, Dict[str, Any]] = {}

    def get_id(uri: str) -> str:
        return uri.rsplit("/", 1)[-1]

    for row in bindings:
        person_uri = row.get("person", {}).get("value")
        if not person_uri:
            continue
        pid = get_id(person_uri)

        rec = agg.setdefault(
            pid,
            {"id": pid, "label": "", "gender": "", "professions": set(), "nationalities": set()},
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
            continue

    persons: List[PersonRecord] = []
    for pid, rec in agg.items():
        label = rec.get("label") or pid
        gender = rec.get("gender") or ""
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

_engine: Optional[GFGrammarEngine] = None
_engine_ready: Optional[bool] = None


def _get_engine() -> Optional[GFGrammarEngine]:
    """Lazy-init GF engine and force-load grammar once via health_check()."""
    global _engine, _engine_ready

    if _engine is None:
        try:
            _engine = GFGrammarEngine()
        except Exception as e:
            log.error(f"Failed to initialize GFGrammarEngine: {e}")
            return None

    if _engine_ready is None:
        try:
            ok = asyncio.run(_engine.health_check())
        except Exception as e:
            log.error(f"GFGrammarEngine health_check() failed: {e}")
            ok = False
        _engine_ready = bool(ok)

        if not _engine_ready:
            log.error("GFGrammarEngine is not healthy (grammar not loaded / missing Wiki.pgf).")
            return None

    return _engine


def _render_bio_adapter(
    *,
    person_id: str,
    name: str,
    gender_raw: str,
    profession_lemma: str,
    nationality_lemma: str,
    lang_code: str,
) -> str:
    """
    Adapter that builds a BioFrame and renders it using GFGrammarEngine (v2.1).
    """
    engine = _get_engine()
    if engine is None:
        return ""

    gender = _normalize_gender(gender_raw)

    # Put profession/nationality in BOTH subject + properties for max back-compat.
    subject = {
        "qid": person_id,
        "name": name,
        "gender": gender,
        "profession": profession_lemma,
        "nationality": nationality_lemma,
    }
    props = {"profession": profession_lemma, "nationality": nationality_lemma}

    try:
        frame = BioFrame(frame_type="bio", subject=subject, properties=props)
    except Exception as e:
        log.warning(f"Could not build BioFrame for {person_id}: {e}")
        return ""

    try:
        sentence = asyncio.run(engine.generate(lang_code, frame))
        # sentence is typically a domain object with .text, but be defensive
        text = getattr(sentence, "text", sentence)
        return (text or "").strip()
    except Exception as e:
        log.warning(f"Rendering failed for {name} ({lang_code}): {e}")
        return ""


def evaluate_persons(
    persons: Iterable[PersonRecord],
    langs: List[str],
    max_items: Optional[int] = None,
) -> List[EvalResult]:
    """For each person and language, render and collect results."""
    results: List[EvalResult] = []
    count = 0

    for person in persons:
        if max_items is not None and count >= max_items:
            break
        count += 1

        for lang in langs:
            prof_lemma = person.profession_lemmas[0] if person.profession_lemmas else ""
            nat_lemma = person.nationality_lemmas[0] if person.nationality_lemmas else ""

            output = _render_bio_adapter(
                person_id=person.id,
                name=person.label,
                gender_raw=person.gender,
                profession_lemma=prof_lemma,
                nationality_lemma=nat_lemma,
                lang_code=lang,
            )

            rendered = bool(output)

            gold = person.gold_bios.get(lang)
            has_gold = bool(gold and gold.strip())
            exact_match = bool(has_gold and gold.strip() == output)

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
    """Print a compact textual summary to stdout."""
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
    """Save detailed results to a CSV file for later analysis."""
    log.info(f"Writing detailed results CSV to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["person_id", "lang", "rendered", "has_gold", "exact_match", "output"])
        for r in results:
            writer.writerow([r.person_id, r.lang, int(r.rendered), int(r.has_gold), int(r.exact_match), r.output])


def print_sample_outputs(
    persons: List[PersonRecord],
    results: List[EvalResult],
    langs: List[str],
    n_samples: int,
) -> None:
    """Print a few rendered bios per language for manual inspection."""
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
    parser = argparse.ArgumentParser(description="Evaluate bio rendering against Wikidata-derived people.")

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
        nargs="+",
        default=["en"],
        help="Language codes (space-separated and/or comma-separated), e.g. --langs en fr it OR --langs en,fr,it",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of persons to evaluate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling / sample selection.")
    parser.add_argument("--output-csv", type=str, help="Write detailed person-language results to this CSV path.")
    parser.add_argument("--print-samples", type=int, default=0, help="Print up to N rendered samples per language.")

    return parser.parse_args(argv)


def _parse_langs(raw_parts: List[str]) -> List[str]:
    langs: List[str] = []
    for part in raw_parts:
        for tok in str(part).split(","):
            tok = tok.strip()
            if tok:
                langs.append(tok)
    # de-dup preserving order
    seen = set()
    out: List[str] = []
    for l in langs:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    langs = _parse_langs(args.langs)
    log.header({"Source": args.source, "Langs": ",".join(langs), "Limit": args.limit})

    random.seed(args.seed)

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
    else:
        log.stage("Fetch", f"Querying Wikidata for {args.limit} persons...")
        persons = fetch_wikidata_persons(limit=args.limit)

    if not persons:
        log.error("No person records loaded; nothing to evaluate.", fatal=True)

    if args.source == "local" and len(persons) > args.limit:
        log.info(f"Subsampling {args.limit} persons out of {len(persons)} with seed={args.seed}")
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