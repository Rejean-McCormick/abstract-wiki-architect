// architect_frontend/src/app/tools/descriptions.ts

/**
 * UI-friendly descriptions for known repo paths.
 * Anything not present here falls back to `defaultDesc(path)`.
 *
 * Notes:
 * - Keep this file focused on “human meaning” (what it does), not wiring state.
 * - Keys should match repo-relative POSIX-style paths (use `/`, not `\`).
 */

export type ToolDescriptions = Readonly<Record<string, string>>;

const normalizePath = (raw: string) =>
  (raw || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/^\.\//, "");

/** Freeze so accidental runtime mutation doesn't drift UI copy */
const freeze = <T extends Record<string, string>>(m: T) =>
  Object.freeze(m) as ToolDescriptions;

// ----------------------------------------------------------------------------
// Descriptions (grouped for maintainability)
// ----------------------------------------------------------------------------
const ROOT_ENTRYPOINTS = {
  "manage.py": "Primary backend CLI entrypoint for lifecycle operations (start, build, clean, doctor, generate).",
  "Run-Architect.ps1": "Windows launcher that starts the API, worker, and frontend after clearing stale processes.",
  "RUN-Architect.bat": "Windows convenience launcher for the main stack.",
  "build_pipeline.bat": "Windows convenience launcher for the build pipeline.",
  "StartWSL.bat": "Starts or initializes the WSL environment for local development.",
  "GitSink.bat": "Repo-specific git housekeeping helper.",
  "context_gatherer.py": "Collects project file and metadata context for audits and inventories.",
  "generate_path_map.py": "Scans grammar locations to generate RGL path mappings.",
  "generate_everything_matrix.py": "Convenience entrypoint to rebuild everything_matrix.json, if present in this checkout.",
  "link_libraries.py": "Links or builds external dependencies required by the repo.",
  "sync_config_from_gf.py": "Synchronizes config artifacts from GF outputs into app/config.",
  "smoke_test.py": "Quick end-to-end smoke validation script.",
  "debug_matrix.py": "Debug helper for inspecting Everything Matrix output.",
  "fix_config.py": "Repo-specific helper to repair or normalize config artifacts.",
  "fix_grammar_files.py": "Repo-specific helper to repair or normalize grammar files.",
  "disable_broken_compile.sh": "Temporarily disables known-broken compile targets to keep builds moving.",
} satisfies Record<string, string>;

const BACKEND_WIRED_TOOLS = {
  // Core maintenance / diagnostics
  "tools/language_health.py": "Hybrid language audit that checks compile status and API runtime health.",
  "tools/diagnostic_audit.py": "Forensics audit for stale artifacts, zombie outputs, and broken grammar links.",
  "tools/cleanup_root.py": "Cleans root-level artifacts and moves loose GF files into expected locations.",

  // Build / onboarding
  "tools/bootstrap_tier1.py": "Bootstraps Tier 1 language scaffolding and wrapper files.",
  "tools/harvest_lexicon.py": "Harvests lexicon data into shard JSON files from supported sources.",
  "tools/everything_matrix/build_index.py": "Rebuilds everything_matrix.json by scanning grammar, lexicon, app, and QA signals.",

  // Data / AI
  "utils/build_lexicon_from_wikidata.py": "Builds lexicon shards directly from Wikidata input.",
  "tools/ai_refiner.py": "AI-assisted repair or refinement tool for build and quality tasks (gated).",

  // Debug / health
  "tools/health/profiler.py": "Benchmarks grammar generation performance (latency, throughput, memory).",
  "tools/debug/visualize_ast.py": "Generates a JSON abstract syntax tree from a sentence or intent.",

  // QA / coverage
  "tools/qa/lexicon_coverage_report.py": "Reports lexicon shard coverage, counts, collisions, and schema issues.",
} satisfies Record<string, string>;

const GF_BUILD = {
  "builder/orchestrator/__main__.py":
    "Canonical compile entrypoint for the two-phase GF build orchestrator that produces semantik_architect.pgf.",
  "builder/orchestrator.py":
    "Compatibility entrypoint for the GF build orchestrator.",
  "builder/orchestrator/build.py":
    "Core build logic for the two-phase GF compilation and linking pipeline.",
  "builder/compiler.py": "Lower-level GF compiler helper used by the build pipeline.",
} satisfies Record<string, string>;

const EVERYTHING_MATRIX = {
  "tools/everything_matrix/build_index.py":
    "Rebuilds everything_matrix.json by scanning repo-wide language, lexicon, app, and QA signals.",
  "tools/everything_matrix/app_scanner.py":
    "Scans frontend, backend, and app surfaces for language support signals.",
  "tools/everything_matrix/lexicon_scanner.py":
    "Scores lexicon maturity by scanning shard presence, coverage, and depth.",
  "tools/everything_matrix/qa_scanner.py":
    "Parses QA outputs and test artifacts to update quality scoring.",
  "tools/everything_matrix/rgl_scanner.py":
    "Audits RGL and GF module presence, layout, and consistency.",
  "docs/everything_matrix_orchestration.md":
    "Reference doc for the Everything Matrix refresh and orchestration flow.",
} satisfies Record<string, string>;

const QA_TOOLS = {
  "tools/qa/test_runner.py": "Canonical CSV-based QA runner for the standard test suite.",
  "tools/qa/universal_test_runner.py": "Advanced CSV QA runner for more complex constructions.",
  "tools/qa/test_suite_generator.py": "Generates empty QA CSV templates for human or AI completion.",
  "tools/qa/batch_test_generator.py": "Generates bulk regression datasets for QA.",
  "tools/qa/eval_bios.py": "Compares generated biography outputs against Wikidata facts.",
  "tools/qa/lexicon_coverage_report.py": "Coverage snapshot for intended vs implemented lexicon content.",
  "tools/qa/generate_lexicon_regression_tests.py": "Builds lexicon-derived regression tests for QA and CI.",
  "tools/qa/ambiguity_detector.py": "Detects ambiguous parses or outputs that should be blocked before release.",
  "tests/integration/test_quality.py": "Golden-standard quality regression suite used by the Judge workflow.",
  "tests/test_api_smoke.py": "Fast API smoke tests for the generation stack.",
  "tests/test_lexicon_smoke.py": "Smoke tests for lexicon syntax and schema validity.",
  "tests/test_gf_dynamic.py": "Checks dynamic GF loading and linearization behavior.",
  "tests/test_multilingual_generation.py": "Regression tests for multilingual generation behavior.",
} satisfies Record<string, string>;

const SCRIPTS = {
  "scripts/demo_generation.py": "Local demo of multilingual generation.",
  "scripts/demo_quad.py": "Local demo of quad output across languages or frames.",
  "scripts/test_api_generation.py":
    "Legacy or diagnostic script that exercises API generation endpoints.",
  "scripts/test_tier1_load.py": "Loads Tier 1 languages to verify wrappers and PGF load behavior.",

  // Legacy lexicon scripts
  "scripts/lexicon/sync_rgl.py":
    "Legacy DB-era lexicon synchronizer (reference only unless the DB pipeline still exists).",
  "scripts/lexicon/wikidata_importer.py":
    "Legacy DB-era Wikidata importer (reference only unless the DB pipeline still exists).",
} satisfies Record<string, string>;

const UTILS = {
  // CLI / utility entrypoints
  "utils/build_lexicon_from_wikidata.py": "Offline or dump-based lexicon builder from Wikidata sources.",
  "utils/dump_lexicon_stats.py": "Prints lexicon size and coverage statistics.",
  "utils/migrate_lexicon_schema.py": "Migrates lexicon JSON shards to a newer schema version.",
  "utils/refresh_lexicon_index.py": "Rebuilds the fast lexicon lookup index used by the API.",
  "utils/seed_lexicon_ai.py": "LLM-assisted seed generator for new language lexicons (gated).",

  // Libraries
  "utils/grammar_factory.py": "Library for weighted topology and tiered grammar generation.",
  "utils/logging_setup.py": "Logging configuration helpers used by tools and services.",
  "utils/wikifunctions_api_mock.py": "Local mock or stub for Wikifunctions API calls.",
} satisfies Record<string, string>;

const AI_SERVICES = {
  "ai_services/architect.py": "AI agent that generates missing language code or grammar.",
  "ai_services/surgeon.py": "AI agent that patches build failures from compiler logs.",
  "ai_services/lexicographer.py": "AI agent that proposes or generates missing lexicon entries.",
  "ai_services/judge.py": "AI judge agent for qualitative evaluation and regression workflows.",
  "ai_services/prompts.py": "Prompt templates and configuration for AI services.",
  "ai_services/client.py": "Shared client wrapper for calling AI services.",
} satisfies Record<string, string>;

const NLG = {
  "nlg/api.py": "Legacy or internal NLG API module.",
  "nlg/cli_frontend.py": "CLI frontend for NLG and generation experiments.",
} satisfies Record<string, string>;

const PROTOTYPES = {
  "prototypes/demo_multisentence_bio.py": "Prototype demo for multi-sentence biography generation.",
  "prototypes/local_test_runner.py": "Prototype local test harness.",
  "prototypes/shared_romance_engine.py": "Prototype shared engine for romance-language generation.",
} satisfies Record<string, string>;

const TESTS = {
  "tests/test_api_smoke.py": "API smoke tests (fast signal).",
  "tests/test_lexicon_smoke.py": "Lexicon schema and syntax smoke tests.",
  "tests/test_gf_dynamic.py": "Validates dynamic GF loading and linearization.",
  "tests/test_multilingual_generation.py": "Multilingual generation regression tests.",
  "tests/integration/test_quality.py": "Golden-standard regression test suite used by the Judge flow.",
} satisfies Record<string, string>;

const DOCS = {
  "docs/06-ADDING_A_LANGUAGE.md": "Reference guide for onboarding and integrating a new language.",
  "docs/17-TOOLS_AND_TESTS_INVENTORY.md": "Single source of truth for dashboard tools, tests, and operational workflows.",
  "docs/16-DEV_TOOLS_AND_LAUNCHER.md": "Developer-facing guide for launchers, local tools, and operational helpers.",
  "docs/02-BUILD_SYSTEM.md": "Reference guide for the build system and PGF compilation flow.",
  "docs/03-LEXICON_ARCHITECTURE.md": "Reference guide for lexicon structure, shards, and data flow.",
  "docs/04-API_REFERENCE.md": "Reference guide for API endpoints and request shapes.",
} satisfies Record<string, string>;

// ----------------------------------------------------------------------------
// Public export (single map)
// ----------------------------------------------------------------------------
export const TOOL_DESCRIPTIONS: ToolDescriptions = freeze({
  ...ROOT_ENTRYPOINTS,
  ...BACKEND_WIRED_TOOLS,
  ...GF_BUILD,
  ...EVERYTHING_MATRIX,
  ...QA_TOOLS,
  ...SCRIPTS,
  ...UTILS,
  ...AI_SERVICES,
  ...NLG,
  ...PROTOTYPES,
  ...TESTS,
  ...DOCS,
});

// ----------------------------------------------------------------------------
// Fallback description
// ----------------------------------------------------------------------------
export const defaultDesc = (rawPath: string) => {
  const path = normalizePath(rawPath);
  const p = path.toLowerCase();
  const ext = (p.split(".").pop() || "").toLowerCase();

  if (p.startsWith("tests/")) return "Pytest test module.";
  if (p.startsWith("ai_services/")) return "AI service module.";
  if (p.startsWith("utils/")) return ext === "py" ? "Utility module." : "Utility file.";
  if (p.startsWith("tools/everything_matrix/")) return "Everything Matrix scanner or orchestration tool.";
  if (p.startsWith("tools/language_health/")) return "Language health support module.";
  if (p.startsWith("tools/qa/")) return "QA tool script.";
  if (p.startsWith("tools/health/")) return "Health or performance tool.";
  if (p.startsWith("tools/debug/")) return "Debugging tool.";
  if (p.startsWith("tools/lexicon/")) return "Lexicon data tool.";
  if (p.startsWith("tools/")) return "Tool script.";
  if (p.startsWith("scripts/")) return "Ad-hoc script.";
  if (p.startsWith("builder/")) return "Build system module.";
  if (p.startsWith("gf/")) return "GF grammar file.";
  if (p.startsWith("prototypes/")) return "Prototype script.";
  if (p.startsWith("nlg/")) return "NLG module.";
  if (p.startsWith("docs/")) return "Documentation file.";

  // a few common non-python file types in this repo surface
  if (ext === "ps1") return "PowerShell script.";
  if (ext === "bat") return "Windows batch script.";
  if (ext === "sh") return "Shell script.";
  if (ext === "json") return "JSON data or config file.";
  if (ext === "md") return "Documentation file.";

  return "Project file.";
};