from __future__ import annotations

from typing import Dict, Sequence

from .config import DEFAULT_TIMEOUT_SEC, PYTHON_EXE
from .models import ToolSpec


def py_script(
    tool_id: str,
    rel_script: str,
    description: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
    allow_positionals: bool = False,
    requires_ai_enabled: bool = False,
    flags_with_value: Sequence[str] = (),
    flags_with_multi_value: Sequence[str] = (),
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        description=description,
        rel_target=rel_script,
        cmd=(PYTHON_EXE, "-u", "{target}"),
        timeout_sec=timeout_sec,
        allow_args=allow_args,
        allowed_flags=tuple(allowed_flags),
        allow_positionals=allow_positionals,
        requires_ai_enabled=requires_ai_enabled,
        flags_with_value=tuple(flags_with_value),
        flags_with_multi_value=tuple(flags_with_multi_value),
    )


def py_module(
    tool_id: str,
    module: str,
    rel_check_path: str,
    description: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    allow_args: bool = False,
    allowed_flags: Sequence[str] = (),
    allow_positionals: bool = False,
    requires_ai_enabled: bool = False,
    flags_with_value: Sequence[str] = (),
    flags_with_multi_value: Sequence[str] = (),
) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        description=description,
        # Used for existence checks in the tools runner (module itself is executed via -m).
        rel_target=rel_check_path,
        cmd=(PYTHON_EXE, "-u", "-m", module),
        timeout_sec=timeout_sec,
        allow_args=allow_args,
        allowed_flags=tuple(allowed_flags),
        allow_positionals=allow_positionals,
        requires_ai_enabled=requires_ai_enabled,
        flags_with_value=tuple(flags_with_value),
        flags_with_multi_value=tuple(flags_with_multi_value),
    )


def build_registry() -> Dict[str, ToolSpec]:
    return {
        # --- BUILD ---
        "build_index": py_script(
            "build_index",
            "tools/everything_matrix/build_index.py",
            "Rebuilds everything_matrix.json by scanning repo (languages, lexicon, QA).",
            timeout_sec=900,
            allow_args=True,
            allowed_flags=(
                "--out",
                "--verbose",
                "--langs",
                "--force",
                "--regen-rgl",
                "--regen-lex",
                "--regen-app",
                "--regen-qa",
            ),
            allow_positionals=False,
            flags_with_value=("--out",),
            flags_with_multi_value=("--langs",),
        ),
        "app_scanner": py_script(
            "app_scanner",
            "tools/everything_matrix/app_scanner.py",
            "Scans app/frontend/backend surfaces for language support signals.",
            timeout_sec=600,
        ),
        "lexicon_scanner": py_script(
            "lexicon_scanner",
            "tools/everything_matrix/lexicon_scanner.py",
            "Scores lexicon maturity by scanning shard coverage.",
            timeout_sec=600,
        ),
        "qa_scanner": py_script(
            "qa_scanner",
            "tools/everything_matrix/qa_scanner.py",
            "Parses QA output/logs to update quality scoring.",
            timeout_sec=600,
        ),
        "rgl_scanner": py_script(
            "rgl_scanner",
            "tools/everything_matrix/rgl_scanner.py",
            "Audits RGL grammar module presence/consistency.",
            timeout_sec=600,
        ),
        "compile_pgf": py_module(
            "compile_pgf",
            "builder.orchestrator",
            "builder/orchestrator/__main__.py",
            "Two-phase GF build orchestrator to produce semantik_architect.pgf.",
            timeout_sec=1800,
            allow_args=True,
            allowed_flags=(
                "--strategy",
                "--langs",
                "--clean",
                "--verbose",
                "--max-workers",
                "--no-preflight",
                "--regen-safe",
            ),
            allow_positionals=False,
            flags_with_value=("--strategy", "--max-workers"),
            flags_with_multi_value=("--langs",),
        ),
        "bootstrap_tier1": py_script(
            "bootstrap_tier1",
            "tools/bootstrap_tier1.py",
            "Bootstraps Tier 1 languages/wrappers.",
            timeout_sec=1200,
            allow_args=True,
            allowed_flags=("--langs", "--force", "--dry-run", "--verbose"),
            allow_positionals=False,
            flags_with_multi_value=("--langs",),
        ),
        # --- DATA REFINERY ---
        "gap_filler": py_script(
            "gap_filler",
            "tools/lexicon/gap_filler.py",
            "Identifies missing vocabulary by comparing Target vs Pivot language.",
            timeout_sec=600,
            allow_args=True,
            allowed_flags=("--target", "--pivot", "--data-dir", "--json-out", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--target", "--pivot", "--data-dir", "--json-out"),
        ),
        "harvest_lexicon": py_script(
            "harvest_lexicon",
            "tools/harvest_lexicon.py",
            "Universal Lexicon Harvester. Subcommands: `wordnet` and `wikidata` (positional).",
            timeout_sec=1800,
            allow_args=True,
            allowed_flags=("--root", "--lang", "--out", "--input", "--domain"),
            allow_positionals=True,
            flags_with_value=("--root", "--lang", "--out", "--input", "--domain"),
        ),
        "build_lexicon_wikidata": py_script(
            "build_lexicon_wikidata",
            "utils/build_lexicon_from_wikidata.py",
            "Builds lexicon shards directly from Wikidata (online).",
            timeout_sec=1800,
            allow_args=True,
            allowed_flags=("--lang", "--out", "--limit", "--dry-run", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--lang", "--out", "--limit"),
        ),
        "refresh_index": py_script(
            "refresh_index",
            "utils/refresh_lexicon_index.py",
            "Rebuilds the fast lexicon lookup index used by API.",
            timeout_sec=900,
            allow_args=True,
            allowed_flags=("--langs", "--root", "--out", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--root", "--out"),
            flags_with_multi_value=("--langs",),
        ),
        "migrate_schema": py_script(
            "migrate_schema",
            "utils/migrate_lexicon_schema.py",
            "Migrates lexicon JSON shards to newer schema versions.",
            timeout_sec=1800,
            allow_args=True,
            allowed_flags=("--root", "--in-place", "--dry-run", "--from", "--to", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--root", "--from", "--to"),
        ),
        "dump_stats": py_script(
            "dump_stats",
            "utils/dump_lexicon_stats.py",
            "Prints lexicon coverage/size statistics.",
            timeout_sec=600,
            allow_args=True,
            allowed_flags=("--langs", "--root", "--format", "--verbose"),
            allow_positionals=False,
            flags_with_value=("--root", "--format"),
            flags_with_multi_value=("--langs",),
        ),
    }