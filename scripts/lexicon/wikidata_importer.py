# scripts/lexicon/wikidata_importer.py
# =========================================================================
# WIKIDATA LINKER (JSON Lexicon Shards)
#
# This script enriches the filesystem lexicon under:
#   data/lexicon/{lang}/*.json
#
# It links lexicon entries to Wikidata Items (Q-IDs) by label matching:
# 1) Scans lexicon shards for entries missing metadata.wikidata_id
# 2) Uses the entry lemma (in that language) as the lookup label
# 3) Queries Wikidata SPARQL endpoint in batches
# 4) Writes metadata.wikidata_id back to the JSON shard (optional --apply)
# 5) Maintains a local cache to avoid repeated lookups
# 6) Optionally validates shards via app.adapters.persistence.lexicon.schema
#
# Notes:
# - This is heuristic label matching. Manual review is recommended for
#   ambiguous terms.
# - Defaults to POS filter: N / NOUN / PROPN (skips function-word skeletons).
# =========================================================================

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Project root & optional validator import
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    # Project validator (preferred)
    from app.adapters.persistence.lexicon.schema import raise_if_invalid  # type: ignore
except Exception:
    raise_if_invalid = None  # type: ignore


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

DEFAULT_USER_AGENT = os.getenv(
    "WIKIDATA_USER_AGENT",
    "AbstractWikiArchitect/2.2 (https://abstractwiki.org; contact: admin@abstractwiki.org)",
)

DEFAULT_BATCH_SIZE = 25
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 30

# Always exclude common “bad hits”
EXCLUDE_INSTANCE_OF_QIDS = {
    "Q4167410",   # Wikimedia disambiguation page
    "Q13406463",  # Wikimedia list article
    "Q11266439",  # Wikimedia template
}

LEMMA_SECTIONS = ("entries", "lemmas", "professions", "nationalities", "titles", "honours")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    # Avoid timezone dependency; this is used as an audit stamp only.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sparql_escape(s: str) -> str:
    # Escape for a SPARQL string literal
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").replace("\r", " ").strip()
    return s


def _is_missing_qid(entry: Dict[str, Any]) -> bool:
    md = entry.get("metadata")
    if not isinstance(md, dict):
        return True
    qid = md.get("wikidata_id")
    return qid is None or (isinstance(qid, str) and qid.strip() == "")


def _ensure_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    md = entry.get("metadata")
    if not isinstance(md, dict):
        md = {}
        entry["metadata"] = md
    return md


def _iter_sections(data: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    for name in LEMMA_SECTIONS:
        section = data.get(name)
        if isinstance(section, dict):
            yield name, section


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _lang_from_meta(data: Dict[str, Any], fallback: str) -> str:
    meta = data.get("meta") or data.get("_meta") or {}
    if isinstance(meta, dict):
        lang = meta.get("language")
        if isinstance(lang, str) and lang.strip():
            return lang.strip()
    return fallback


def _domain_from_meta(data: Dict[str, Any], fallback: str) -> str:
    meta = data.get("meta") or data.get("_meta") or {}
    if isinstance(meta, dict):
        dom = meta.get("domain")
        if isinstance(dom, str) and dom.strip():
            return dom.strip()
    return fallback


def _load_cache(path: Path) -> Dict[str, Optional[str]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            # values can be qid string or null
            return {str(k): (v if (v is None or isinstance(v, str)) else None) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_cache(path: Path, cache: Dict[str, Optional[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


@dataclass
class LookupResult:
    qid_by_label: Dict[str, str]
    missing_labels: List[str]


def _http_get_with_backoff(
    url: str,
    params: Dict[str, str],
    headers: Dict[str, str],
    timeout_s: int,
    max_retries: int = 5,
) -> Optional[requests.Response]:
    backoff = 1.0
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout_s)
            if resp.status_code in (429, 503, 502, 504):
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            return resp
        except requests.RequestException:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
    return None


def fetch_wikidata_ids_exact(
    *,
    lang_code: str,
    labels: List[str],
    user_agent: str,
    timeout_s: int,
) -> LookupResult:
    """
    Exact label match using language-tagged literals: "label"@xx
    Returns first/best item per label (best = highest sitelinks if available).
    """
    clean = [l.strip() for l in labels if isinstance(l, str) and l.strip()]
    if not clean:
        return LookupResult({}, [])

    values_str = " ".join([f"\"{_sparql_escape(l)}\"@{lang_code}" for l in clean])

    # Note: keep the query simple & fast; disambiguation/list/template are filtered out.
    query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?label ?item ?sitelinks WHERE {{
  VALUES ?label {{ {values_str} }}
  ?item rdfs:label ?label .
  OPTIONAL {{ ?item wikibase:sitelinks ?sitelinks . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q4167410 . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q13406463 . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q11266439 . }}
}}
"""

    headers = {"User-Agent": user_agent, "Accept": "application/sparql-results+json"}
    resp = _http_get_with_backoff(
        WIKIDATA_SPARQL_URL,
        params={"format": "json", "query": query},
        headers=headers,
        timeout_s=timeout_s,
    )
    if resp is None or resp.status_code != 200:
        return LookupResult({}, clean)

    data = resp.json()
    bindings = data.get("results", {}).get("bindings", [])

    # Collect candidates per label
    candidates: Dict[str, List[Tuple[int, str]]] = {}
    for b in bindings:
        label = b.get("label", {}).get("value")
        item_url = b.get("item", {}).get("value")
        if not isinstance(label, str) or not isinstance(item_url, str):
            continue
        qid = item_url.rsplit("/", 1)[-1]
        sitelinks_val = b.get("sitelinks", {}).get("value")
        try:
            sitelinks = int(sitelinks_val) if sitelinks_val is not None else 0
        except Exception:
            sitelinks = 0
        candidates.setdefault(label, []).append((sitelinks, qid))

    qid_by_label: Dict[str, str] = {}
    for label, cands in candidates.items():
        # pick highest sitelinks; tie-breaker: first
        cands.sort(key=lambda x: x[0], reverse=True)
        qid_by_label[label] = cands[0][1]

    missing = [l for l in clean if l not in qid_by_label]
    return LookupResult(qid_by_label, missing)


def fetch_wikidata_ids_fallback_casefold(
    *,
    lang_code: str,
    labels: List[str],
    user_agent: str,
    timeout_s: int,
) -> Dict[str, str]:
    """
    Case-insensitive fallback using VALUES ?needle { "x" "y" } and
    LCASE comparisons against rdfs:label in lang_code.
    Returns mapping from original label -> QID (best sitelinks per label).
    """
    clean = [l.strip() for l in labels if isinstance(l, str) and l.strip()]
    if not clean:
        return {}

    values_str = " ".join([f"\"{_sparql_escape(l)}\"" for l in clean])

    query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?needle ?item ?sitelinks WHERE {{
  VALUES ?needle {{ {values_str} }}
  ?item rdfs:label ?lbl .
  FILTER(lang(?lbl) = "{lang_code}")
  FILTER(LCASE(STR(?lbl)) = LCASE(STR(?needle)))
  OPTIONAL {{ ?item wikibase:sitelinks ?sitelinks . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q4167410 . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q13406463 . }}
  FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q11266439 . }}
}}
"""

    headers = {"User-Agent": user_agent, "Accept": "application/sparql-results+json"}
    resp = _http_get_with_backoff(
        WIKIDATA_SPARQL_URL,
        params={"format": "json", "query": query},
        headers=headers,
        timeout_s=timeout_s,
    )
    if resp is None or resp.status_code != 200:
        return {}

    data = resp.json()
    bindings = data.get("results", {}).get("bindings", [])

    # Collect candidates per needle
    candidates: Dict[str, List[Tuple[int, str]]] = {}
    for b in bindings:
        needle = b.get("needle", {}).get("value")
        item_url = b.get("item", {}).get("value")
        if not isinstance(needle, str) or not isinstance(item_url, str):
            continue
        qid = item_url.rsplit("/", 1)[-1]
        sitelinks_val = b.get("sitelinks", {}).get("value")
        try:
            sitelinks = int(sitelinks_val) if sitelinks_val is not None else 0
        except Exception:
            sitelinks = 0
        candidates.setdefault(needle, []).append((sitelinks, qid))

    out: Dict[str, str] = {}
    for needle, cands in candidates.items():
        cands.sort(key=lambda x: x[0], reverse=True)
        out[needle] = cands[0][1]
    return out


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def enrich_file(
    *,
    path: Path,
    lang_code: str,
    cache: Dict[str, Optional[str]],
    batch_size: int,
    sleep_s: float,
    user_agent: str,
    timeout_s: int,
    apply: bool,
    validate: bool,
    pos_allowlist: Optional[set[str]],
    skip_uppercase_short: bool,
    source_tag: str,
) -> Tuple[int, int, int]:
    """
    Returns: (scanned_entries, updated_entries, unresolved_entries)
    """
    data = _read_json(path)

    inferred_lang = _lang_from_meta(data, lang_code)
    domain = _domain_from_meta(data, path.stem)

    # Collect pending labels
    pending: List[Tuple[str, Dict[str, Any]]] = []  # (label, entry_ref)
    scanned = 0
    for _, section in _iter_sections(data):
        for _, entry in section.items():
            if not isinstance(entry, dict):
                continue
            scanned += 1

            lemma = entry.get("lemma")
            if not isinstance(lemma, str) or not lemma.strip():
                continue

            if pos_allowlist is not None:
                pos = entry.get("pos")
                if isinstance(pos, str) and pos_allowlist and pos.strip() not in pos_allowlist:
                    continue
                if not isinstance(pos, str):
                    # If POS missing and allowlist is in effect, skip conservatively.
                    continue

            if skip_uppercase_short:
                if lemma.isupper() and len(re.sub(r"[^A-Z]", "", lemma)) <= 3:
                    continue

            if not _is_missing_qid(entry):
                continue

            pending.append((lemma.strip(), entry))

    if not pending:
        if validate and raise_if_invalid is not None:
            raise_if_invalid(inferred_lang, data)
        return scanned, 0, 0

    # Resolve labels in batches
    updated = 0
    unresolved = 0

    # Deduplicate by label but keep refs for updates
    label_to_entries: Dict[str, List[Dict[str, Any]]] = {}
    for label, entry in pending:
        label_to_entries.setdefault(label, []).append(entry)

    labels = list(label_to_entries.keys())
    total = len(labels)

    for start in range(0, total, batch_size):
        batch = labels[start : start + batch_size]

        # Use cache first
        remaining: List[str] = []
        qid_hits: Dict[str, str] = {}
        for label in batch:
            cache_key = f"{inferred_lang}:{label}"
            if cache_key in cache and cache[cache_key]:
                qid_hits[label] = str(cache[cache_key])
            else:
                remaining.append(label)

        # Exact SPARQL
        if remaining:
            exact = fetch_wikidata_ids_exact(
                lang_code=inferred_lang,
                labels=remaining,
                user_agent=user_agent,
                timeout_s=timeout_s,
            )
            qid_hits.update(exact.qid_by_label)

            # Cache exact hits
            for label, qid in exact.qid_by_label.items():
                cache[f"{inferred_lang}:{label}"] = qid

            # Fallback casefold for misses
            if exact.missing_labels:
                fb = fetch_wikidata_ids_fallback_casefold(
                    lang_code=inferred_lang,
                    labels=exact.missing_labels,
                    user_agent=user_agent,
                    timeout_s=timeout_s,
                )
                for label, qid in fb.items():
                    if label not in qid_hits:
                        qid_hits[label] = qid
                    cache[f"{inferred_lang}:{label}"] = qid

                # Cache “no result” for still-missing, to reduce repeated calls
                still_missing = [l for l in exact.missing_labels if l not in fb]
                for label in still_missing:
                    cache[f"{inferred_lang}:{label}"] = None

        # Apply updates for this batch
        for label in batch:
            entries = label_to_entries.get(label, [])
            if label in qid_hits:
                qid = qid_hits[label]
                for entry in entries:
                    md = _ensure_metadata(entry)
                    md["wikidata_id"] = qid
                    md["source"] = source_tag
                    md["linked_at"] = _now_iso()
                    md["match_lang"] = inferred_lang
                    updated += 1
            else:
                unresolved += len(entries)

        if sleep_s > 0:
            time.sleep(sleep_s)

    # Validate & write
    if validate and raise_if_invalid is not None:
        raise_if_invalid(inferred_lang, data)

    if apply:
        _write_json(path, data)

    return scanned, updated, unresolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link lexicon shard entries to Wikidata QIDs (label match)."
    )
    parser.add_argument(
        "--lexicon-dir",
        default=str(PROJECT_ROOT / "data" / "lexicon"),
        help="Root lexicon directory (default: data/lexicon).",
    )
    parser.add_argument(
        "--lang",
        action="append",
        default=[],
        help="Language code to process (repeatable). Use 'all' to scan all subfolders.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Domain shard to process (repeatable): core, people, science, geography, ...",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes back to disk. If omitted, runs as dry-run.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Disable lexicon schema validation (if validator is available).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Labels per Wikidata query (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help=f"Seconds to sleep between batches (default: {DEFAULT_SLEEP_SECONDS}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header for Wikidata requests.",
    )
    parser.add_argument(
        "--cache",
        default=str(PROJECT_ROOT / "data" / "indices" / "wikidata_label_cache.json"),
        help="Cache file path (default: data/indices/wikidata_label_cache.json).",
    )
    parser.add_argument(
        "--pos",
        action="append",
        default=["N", "NOUN", "PROPN"],
        help="Allowed POS tags (repeatable). Default: N, NOUN, PROPN. Use --pos '*' to disable filtering.",
    )
    parser.add_argument(
        "--no-skip-uppercase-short",
        action="store_true",
        help="Do not skip lemmas that are short uppercase tokens (default skips e.g. 'IS').",
    )
    parser.add_argument(
        "--source-tag",
        default="wikidata_label_match",
        help="Value to write into metadata.source for new links.",
    )

    args = parser.parse_args()

    lexicon_dir = Path(args.lexicon_dir)
    if not lexicon_dir.exists():
        raise SystemExit(f"Lexicon directory not found: {lexicon_dir}")

    # Determine languages
    langs: List[str]
    if not args.lang:
        langs = ["all"]
    else:
        langs = args.lang

    if "all" in [l.lower() for l in langs]:
        langs = sorted([p.name for p in lexicon_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])

    # Domains filter
    domains = set([d.strip() for d in args.domain if isinstance(d, str) and d.strip()])

    # POS filter
    pos_list = [p.strip() for p in args.pos if isinstance(p, str) and p.strip()]
    if "*" in pos_list:
        pos_allowlist = None
    else:
        pos_allowlist = set(pos_list)

    skip_uppercase_short = not args.no_skip_uppercase_short
    validate = (not args.no_validate) and (raise_if_invalid is not None)

    cache_path = Path(args.cache)
    cache = _load_cache(cache_path)

    total_scanned = 0
    total_updated = 0
    total_unresolved = 0

    for lang in langs:
        lang_dir = lexicon_dir / lang
        if not lang_dir.exists():
            print(f"⚠️  Skipping missing language dir: {lang_dir}")
            continue

        shard_files = sorted(lang_dir.glob("*.json"))
        if domains:
            shard_files = [p for p in shard_files if p.stem in domains]

        if not shard_files:
            print(f"ℹ️  No shards found for {lang} (domains filter={sorted(domains) if domains else 'none'})")
            continue

        print(f"\n== {lang} == ({len(shard_files)} shard files)")
        for shard in shard_files:
            try:
                scanned, updated, unresolved = enrich_file(
                    path=shard,
                    lang_code=lang,
                    cache=cache,
                    batch_size=args.batch_size,
                    sleep_s=args.sleep,
                    user_agent=args.user_agent,
                    timeout_s=args.timeout,
                    apply=args.apply,
                    validate=validate,
                    pos_allowlist=pos_allowlist,
                    skip_uppercase_short=skip_uppercase_short,
                    source_tag=args.source_tag,
                )
                total_scanned += scanned
                total_updated += updated
                total_unresolved += unresolved

                action = "WROTE" if args.apply else "DRY-RUN"
                print(f"  {action} {shard.name}: scanned={scanned} updated={updated} unresolved={unresolved}")

            except Exception as e:
                print(f"  ❌ {shard.name}: {e}")

    _save_cache(cache_path, cache)

    print("\n== Summary ==")
    print(f"  scanned:     {total_scanned}")
    print(f"  updated:     {total_updated}")
    print(f"  unresolved:  {total_unresolved}")
    print(f"  cache:       {cache_path}")
    print(f"  validate:    {'on' if validate else 'off'}")
    print(f"  mode:        {'apply' if args.apply else 'dry-run'}")


if __name__ == "__main__":
    main()
