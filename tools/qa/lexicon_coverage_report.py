# tools/qa/lexicon_coverage_report.py
"""
Lexicon Coverage Report
======================

This script produces a practical, operator-friendly “coverage” snapshot of the
filesystem lexicon under:

    data/lexicon/{lang}/

It is designed to be callable from:
- CLI:  python tools/qa/lexicon_coverage_report.py
- UI:   tool_id = "lexicon_coverage"  (see app/adapters/api/routers/tools.py)

What it reports
---------------
Per language:
- Presence of expected domain shards (core/people/science/geography/…)
- Lexeme counts by shard (supports both V2 "entries" and legacy "lemmas")
- Duplicate lemma keys across shards (collision risk)
- QID-bearing entries (semantic linkage signal)
- “Wide” dumps (e.g., wide.json) treated as QID datasets when applicable
- Schema/structure issues (best-effort, using the app’s lightweight validator)

Outputs
-------
- Always prints a human-readable summary to stdout.
- Also writes JSON + Markdown reports by default to:
    data/reports/lexicon_coverage_report.json
    data/reports/lexicon_coverage_report.md

Exit code
---------
- 0 by default
- 1 if --fail-on-errors and any schema ERROR is detected
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# -----------------------------------------------------------------------------
# Project root + imports
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prefer the canonical in-repo validator (lightweight, no jsonschema dependency)
try:
    from app.adapters.persistence.lexicon.schema import (  # type: ignore
        SchemaIssue,
        validate_lexicon_structure,
    )
except Exception:  # pragma: no cover
    SchemaIssue = None  # type: ignore
    validate_lexicon_structure = None  # type: ignore

# [REFACTOR] Use standardized logger
try:
    from utils.tool_logger import ToolLogger
    logger = ToolLogger(__file__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("LexiconCoverage")


# -----------------------------------------------------------------------------
# Targets (coverage heuristics)
# -----------------------------------------------------------------------------
DEFAULT_TARGETS = {
    "core": 150,      # “glue” lexemes
    "conc": 500,      # domain lexemes (people/science/geography/…)
    "bio_min": 50,    # semantic/QID-linked entries (heuristic)
}


# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning" | "info"
    path: str
    message: str


@dataclass(frozen=True)
class FileReport:
    rel_path: str
    shard: str
    kind: str  # "lexeme" | "wide" | "unknown"
    counts: Dict[str, int]  # by section
    total_items: int
    qid_items: int
    issues: List[Issue]


@dataclass(frozen=True)
class LanguageReport:
    lang: str
    dir_rel: str
    shard_files: List[FileReport]
    shard_totals: Dict[str, int]  # shard -> count
    total_lexemes: int
    total_qids: int
    collisions: int
    missing_shards: List[str]
    errors: int
    warnings: int
    scores: Dict[str, float]  # normalized 0..10


@dataclass(frozen=True)
class CoverageReport:
    generated_at: str
    lexicon_dir: str
    targets: Dict[str, int]
    languages: List[LanguageReport]
    totals: Dict[str, Any]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
QID_RE = re.compile(r"^Q\d+$", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_read_json(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text), None
    except Exception as e:
        return None, str(e)


def _infer_lang_from_path(path: Path, lexicon_dir: Path) -> str:
    """
    data/lexicon/fr/core.json -> "fr"
    """
    try:
        rel = path.relative_to(lexicon_dir)
        parts = rel.parts
        if len(parts) >= 2:
            return parts[0]
    except Exception:
        pass
    return "unknown"


def _is_language_dir(name: str) -> bool:
    # Enterprise default: 2-letter ISO-639-1 folder names (en, fr, …)
    # Keep permissive enough for edge cases, but avoid __pycache__/files.
    return bool(re.fullmatch(r"[a-z]{2}", name))


def _shard_name_from_file(path: Path) -> str:
    return path.stem.lower()


def _extract_sections(data: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any], bool]]:
    """
    Returns (section_name, section_dict, require_pos).
    """
    # Entries/lemmas: typical lexeme objects should carry POS.
    for section_name, require_pos in [
        ("entries", True),
        ("lemmas", True),
        ("professions", True),
        ("nationalities", True),
        ("titles", True),
        ("honours", True),
        ("name_templates", False),
    ]:
        section = data.get(section_name)
        if isinstance(section, dict):
            yield section_name, section, require_pos


def _count_qids_in_section(section: Dict[str, Any]) -> int:
    c = 0
    for _, v in section.items():
        if isinstance(v, dict) and ("qid" in v and isinstance(v.get("qid"), str)):
            c += 1
    return c


def _looks_like_wide_dump(data: Any) -> bool:
    """
    Heuristic: wide dumps often are dicts keyed by QIDs.
    """
    if not isinstance(data, dict) or not data:
        return False
    # If it has lexicon-like sections, it's not wide.
    if any(k in data for k in ("entries", "lemmas", "meta", "_meta")):
        return False
    # If a meaningful portion are QID keys, treat as wide.
    keys = list(data.keys())
    qid_keys = sum(1 for k in keys[: min(len(keys), 50)] if isinstance(k, str) and QID_RE.match(k))
    return qid_keys >= max(5, int(0.4 * min(len(keys), 50)))


def _validate_with_app_schema(lang: str, data: Any) -> List[Issue]:
    """
    Uses app.adapters.persistence.lexicon.schema.validate_lexicon_structure if available.
    """
    issues: List[Issue] = []
    if validate_lexicon_structure is None:
        return issues

    try:
        raw_issues = validate_lexicon_structure(lang, data)
    except Exception as e:
        return [Issue(level="error", path="__validator__", message=f"Validator crashed: {e}")]

    for it in raw_issues:
        # SchemaIssue is expected to have fields: level, path, message
        lvl = getattr(it, "level", "warning")
        pth = getattr(it, "path", "")
        msg = getattr(it, "message", str(it))
        issues.append(Issue(level=str(lvl), path=str(pth), message=str(msg)))
    return issues


def _analyze_file(path: Path, lexicon_dir: Path) -> FileReport:
    rel_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    shard = _shard_name_from_file(path)

    data, err = _safe_read_json(path)
    if err is not None:
        return FileReport(
            rel_path=rel_path,
            shard=shard,
            kind="unknown",
            counts={},
            total_items=0,
            qid_items=0,
            issues=[Issue(level="error", path="__file__", message=f"Failed to read JSON: {err}")],
        )

    # Wide dump?
    if _looks_like_wide_dump(data):
        # Treat each top-level QID key as an “item”
        keys = [k for k in data.keys() if isinstance(k, str)]
        qids = sum(1 for k in keys if QID_RE.match(k))
        return FileReport(
            rel_path=rel_path,
            shard=shard,
            kind="wide",
            counts={"qids": qids, "top_level_keys": len(keys)},
            total_items=len(keys),
            qid_items=qids,
            issues=[],
        )

    # Lexeme file?
    if isinstance(data, dict):
        lang = _infer_lang_from_path(path, lexicon_dir)
        counts: Dict[str, int] = {}
        qid_items = 0
        total_items = 0

        for section_name, section, _require_pos in _extract_sections(data):
            counts[section_name] = len(section)
            total_items += len(section)
            qid_items += _count_qids_in_section(section)

        issues = _validate_with_app_schema(lang, data)

        # Minimal sanity checks for meta language alignment (best-effort)
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else data.get("_meta")
        if isinstance(meta, dict):
            meta_lang = meta.get("language")
            if isinstance(meta_lang, str) and _is_language_dir(lang) and meta_lang.lower() != lang.lower():
                issues.append(
                    Issue(
                        level="warning",
                        path="meta.language",
                        message=f"meta.language='{meta_lang}' does not match folder '{lang}'.",
                    )
                )

        return FileReport(
            rel_path=rel_path,
            shard=shard,
            kind="lexeme",
            counts=counts,
            total_items=total_items,
            qid_items=qid_items,
            issues=issues,
        )

    # Unknown structure
    return FileReport(
        rel_path=rel_path,
        shard=shard,
        kind="unknown",
        counts={},
        total_items=0,
        qid_items=0,
        issues=[Issue(level="warning", path="__file__", message="Unrecognized JSON structure.")],
    )


def _score_0_10(value: int, target: int) -> float:
    if target <= 0:
        return 0.0
    ratio = min(1.0, float(value) / float(target))
    return round(ratio * 10.0, 2)


def _render_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    widths = [0] * len(rows[0])
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))
    out_lines = []
    for ri, r in enumerate(rows):
        line = "  ".join(c.ljust(widths[i]) for i, c in enumerate(r))
        out_lines.append(line)
        if ri == 0:
            out_lines.append("  ".join("-" * widths[i] for i in range(len(widths))))
    return "\n".join(out_lines)


def _render_md_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]
    out = []
    out.append("| " + " | ".join(header) + " |")
    out.append("| " + " | ".join(["---"] * len(header)) + " |")
    for r in body:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


# -----------------------------------------------------------------------------
# Main analysis
# -----------------------------------------------------------------------------
def build_report(
    lexicon_dir: Path,
    target_core: int,
    target_conc: int,
    target_bio: int,
    only_langs: Optional[List[str]] = None,
) -> CoverageReport:
    if not lexicon_dir.is_dir():
        raise FileNotFoundError(f"Lexicon directory not found: {lexicon_dir}")

    langs = sorted([p.name for p in lexicon_dir.iterdir() if p.is_dir() and _is_language_dir(p.name)])
    if only_langs:
        wanted = {x.lower().strip() for x in only_langs if x.strip()}
        langs = [x for x in langs if x.lower() in wanted]

    language_reports: List[LanguageReport] = []

    for lang in langs:
        lang_dir = lexicon_dir / lang
        json_files = sorted(lang_dir.glob("*.json"), key=lambda p: p.name.lower())

        shard_reports: List[FileReport] = [_analyze_file(p, lexicon_dir) for p in json_files]

        # shard totals + collisions across lexeme shards
        shard_totals: Dict[str, int] = {}
        shard_lemmas: Dict[str, set[str]] = {}
        total_lexemes = 0
        total_qids = 0
        errors = 0
        warnings = 0

        for fr in shard_reports:
            shard_totals[fr.shard] = fr.total_items
            total_qids += fr.qid_items

            for iss in fr.issues:
                if iss.level.lower() == "error":
                    errors += 1
                elif iss.level.lower() == "warning":
                    warnings += 1

            if fr.kind == "lexeme":
                # lemma keys live inside entries/lemmas/etc; we approximate by counting unique keys across sections
                # (for collision detection, we need actual keys -> re-read JSON only when necessary)
                # keep it fast: only do collision detection by loading once per file
                p = PROJECT_ROOT / fr.rel_path
                data, _ = _safe_read_json(p)
                keys: set[str] = set()
                if isinstance(data, dict):
                    for _, section, _req in _extract_sections(data):
                        for k in section.keys():
                            if isinstance(k, str):
                                keys.add(k)
                shard_lemmas[fr.shard] = keys
                total_lexemes += len(keys)

        # collisions: same lemma appears in more than one shard
        lemma_to_shards: Dict[str, int] = {}
        for shard, keys in shard_lemmas.items():
            for k in keys:
                lemma_to_shards[k] = lemma_to_shards.get(k, 0) + 1
        collisions = sum(1 for _, n in lemma_to_shards.items() if n >= 2)

        # Missing "expected" shards (soft expectations; do not fail)
        expected = ["core", "people", "science", "geography"]
        missing = [s for s in expected if s not in shard_totals]

        # conc: everything except core + wide (heuristic)
        core_count = shard_totals.get("core", 0)
        conc_count = sum(
            v for s, v in shard_totals.items()
            if s not in ("core", "wide")  # wide can be lexeme or qid dump; handled via kind mostly
        )

        scores = {
            "CORE": _score_0_10(core_count, target_core),
            "CONC": _score_0_10(conc_count, target_conc),
            "BIO": _score_0_10(total_qids, target_bio),
        }

        language_reports.append(
            LanguageReport(
                lang=lang,
                dir_rel=str(lang_dir.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                shard_files=shard_reports,
                shard_totals=shard_totals,
                total_lexemes=total_lexemes,
                total_qids=total_qids,
                collisions=collisions,
                missing_shards=missing,
                errors=errors,
                warnings=warnings,
                scores=scores,
            )
        )

    # Totals
    totals = {
        "languages": len(language_reports),
        "sum_lexemes": sum(l.total_lexemes for l in language_reports),
        "sum_qids": sum(l.total_qids for l in language_reports),
        "sum_collisions": sum(l.collisions for l in language_reports),
        "sum_errors": sum(l.errors for l in language_reports),
        "sum_warnings": sum(l.warnings for l in language_reports),
        "missing_core": [l.lang for l in language_reports if "core" in l.missing_shards],
    }

    return CoverageReport(
        generated_at=_now_iso(),
        lexicon_dir=str(lexicon_dir),
        targets={"core": target_core, "conc": target_conc, "bio_min": target_bio},
        languages=language_reports,
        totals=totals,
    )


def write_outputs(report: CoverageReport, out_json: Path, write_md: bool = True) -> Tuple[Path, Optional[Path]]:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")

    md_path: Optional[Path] = None
    if write_md:
        md_path = out_json.with_suffix(".md")

        # summary table
        rows = [
            ["lang", "core", "conc", "qids", "lexemes", "collisions", "errors", "warnings", "CORE", "CONC", "BIO"],
        ]
        for l in report.languages:
            core = l.shard_totals.get("core", 0)
            conc = sum(v for s, v in l.shard_totals.items() if s not in ("core", "wide"))
            rows.append(
                [
                    l.lang,
                    str(core),
                    str(conc),
                    str(l.total_qids),
                    str(l.total_lexemes),
                    str(l.collisions),
                    str(l.errors),
                    str(l.warnings),
                    f"{l.scores.get('CORE', 0.0):.2f}",
                    f"{l.scores.get('CONC', 0.0):.2f}",
                    f"{l.scores.get('BIO', 0.0):.2f}",
                ]
            )

        md = []
        md.append(f"# Lexicon Coverage Report\n")
        md.append(f"- Generated at: `{report.generated_at}`")
        md.append(f"- Lexicon dir: `{report.lexicon_dir}`")
        md.append(f"- Targets: core={report.targets['core']}, conc={report.targets['conc']}, bio_min={report.targets['bio_min']}\n")
        md.append("## Summary\n")
        md.append(_render_md_table(rows))
        md.append("\n## Totals\n")
        md.append("```json\n" + json.dumps(report.totals, indent=2) + "\n```\n")

        md_path.write_text("\n".join(md), encoding="utf-8")

    return out_json, md_path


def print_human(report: CoverageReport, include_files: bool = False) -> None:
    rows = [
        ["lang", "core", "conc", "qids", "lexemes", "collisions", "errors", "warnings", "CORE", "CONC", "BIO"],
    ]
    for l in report.languages:
        core = l.shard_totals.get("core", 0)
        conc = sum(v for s, v in l.shard_totals.items() if s not in ("core", "wide"))
        rows.append(
            [
                l.lang,
                str(core),
                str(conc),
                str(l.total_qids),
                str(l.total_lexemes),
                str(l.collisions),
                str(l.errors),
                str(l.warnings),
                f"{l.scores.get('CORE', 0.0):.2f}",
                f"{l.scores.get('CONC', 0.0):.2f}",
                f"{l.scores.get('BIO', 0.0):.2f}",
            ]
        )

    # Use Logger instead of print to ensure it's captured by the GUI
    logger.info(_render_table(rows))
    logger.info("")
    logger.info(f"Totals: {json.dumps(report.totals, indent=2)}")
    logger.info("")

    if include_files:
        for l in report.languages:
            logger.info(f"[{l.lang}] {l.dir_rel}")
            for fr in l.shard_files:
                issue_summary = ""
                if fr.issues:
                    e = sum(1 for i in fr.issues if i.level.lower() == "error")
                    w = sum(1 for i in fr.issues if i.level.lower() == "warning")
                    issue_summary = f"  issues={e}E/{w}W"
                logger.info(f"  - {fr.shard:10s}  {fr.kind:7s}  items={fr.total_items:4d}  qids={fr.qid_items:4d}{issue_summary}  {fr.rel_path}")
                for iss in fr.issues[:15]:
                    logger.info(f"      [{iss.level.upper():7s}] {iss.path}: {iss.message}")
                if len(fr.issues) > 15:
                    logger.info(f"      ... ({len(fr.issues) - 15} more)")
            if l.missing_shards:
                logger.info(f"  missing shards: {', '.join(l.missing_shards)}")
            logger.info("")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate lexicon coverage report (filesystem lexicon).")
    p.add_argument(
        "--lexicon-dir",
        default=str(PROJECT_ROOT / "data" / "lexicon"),
        help="Path to data/lexicon directory (default: data/lexicon).",
    )
    p.add_argument(
        "--lang",
        action="append",
        default=[],
        help="Limit to a specific language (repeatable). Example: --lang fr --lang en",
    )
    p.add_argument("--target-core", type=int, default=DEFAULT_TARGETS["core"])
    p.add_argument("--target-conc", type=int, default=DEFAULT_TARGETS["conc"])
    p.add_argument("--target-bio", type=int, default=DEFAULT_TARGETS["bio_min"])
    p.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "data" / "reports" / "lexicon_coverage_report.json"),
        help="Output JSON path (default: data/reports/lexicon_coverage_report.json).",
    )
    p.add_argument("--no-md", action="store_true", help="Do not write markdown companion file.")
    p.add_argument("--include-files", action="store_true", help="Print per-file breakdown.")
    p.add_argument("--fail-on-errors", action="store_true", help="Exit 1 if any schema ERROR is found.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    # [REFACTOR] Standardized Start
    if hasattr(logger, "start"):
        logger.start("Lexicon Coverage Analysis")

    args = parse_args(argv)

    lexicon_dir = Path(args.lexicon_dir).resolve()
    out_json = Path(args.out).resolve()

    report = build_report(
        lexicon_dir=lexicon_dir,
        target_core=int(args.target_core),
        target_conc=int(args.target_conc),
        target_bio=int(args.target_bio),
        only_langs=args.lang if args.lang else None,
    )

    # Always print summary (UI expects console output)
    print_human(report, include_files=bool(args.include_files))

    # Write outputs for operators
    write_outputs(report, out_json=out_json, write_md=not bool(args.no_md))

    exit_code = 0
    if args.fail_on_errors and report.totals.get("sum_errors", 0) > 0:
        exit_code = 1

    # [REFACTOR] Standardized Summary
    summary_msg = f"Report generated. Languages: {report.totals['languages']}, Errors: {report.totals['sum_errors']}."
    if hasattr(logger, "finish"):
        logger.finish(
            message=summary_msg,
            success=(exit_code == 0),
            details=report.totals
        )
    
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())