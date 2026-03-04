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
const freeze = <T extends Record<string, string>>(m: T) => Object.freeze(m) as ToolDescriptions;

// ----------------------------------------------------------------------------
// Descriptions (grouped for maintainability)
// ----------------------------------------------------------------------------
const ROOT_ENTRYPOINTS = {
  "manage.py": "Primary backend CLI entrypoint (start/build/clean/generate/doctor).",
  "Run-Architect.ps1": "Launcher script (kills stale processes, starts API/worker/frontend).",
  "build_pipeline.bat": "Windows build pipeline convenience launcher.",
  "StartWSL.bat": "Starts/initializes WSL environment (Windows).",
  "GitSink.bat": "Convenience script for git housekeeping (repo-specific).",
  "context_gatherer.py": "Collects project context (file lists/metadata) for audits and inventories.",
  "generate_path_map.py": "Generates RGL path mappings (rgl_paths.json) by scanning module locations.",
  "generate_everything_matrix.py": "Convenience entrypoint to rebuild everything_matrix.json (if present).",
  "link_libraries.py": "Links/builds external dependencies required by the project (repo-specific).",
  "sync_config_from_gf.py": "Synchronizes config artifacts from GF outputs into app/config (repo-specific).",
  "smoke_test.py": "Quick end-to-end smoke validation script.",
} satisfies Record<string, string>;

const BACKEND_WIRED_TOOLS = {
  // Canonical diagnostics tool (replacement for legacy audit/check scripts)
  "tools/language_health.py": "Language health/diagnostics utility (status checks and reporting).",

  // Explicit surface tools (backend-wired)
  "tools/diagnostic_audit.py": "Forensics audit for stale artifacts / zombie outputs.",
  "tools/cleanup_root.py": "Cleans root artifacts and moves loose GF files into expected folders.",
  "tools/bootstrap_tier1.py": "Bootstraps Tier 1 language scaffolding using discovered RGL modules.",
  "tools/harvest_lexicon.py": "Bulk lexicon mining/harvesting into shard JSON files.",
  "utils/build_lexicon_from_wikidata.py": "Builds lexicon artifacts from Wikidata input.",
  "tools/ai_refiner.py": "AI-assisted refiner for build/quality tasks (gated).",
} satisfies Record<string, string>;

const GF_BUILD = {
  "builder/orchestrator.py": "Two-phase GF build orchestrator to produce the master PGF binary.",
} satisfies Record<string, string>;

const EVERYTHING_MATRIX = {
  "tools/everything_matrix/build_index.py":
    "Rebuilds everything_matrix.json by scanning repo (languages, lexicon, QA).",
  "tools/everything_matrix/app_scanner.py":
    "Scans app/frontend/backend surfaces for language support signals.",
  "tools/everything_matrix/lexicon_scanner.py":
    "Scores lexicon maturity by scanning shard coverage.",
  "tools/everything_matrix/qa_scanner.py":
    "Parses QA output/logs to update quality scoring.",
  "tools/everything_matrix/rgl_scanner.py":
    "Audits RGL grammar module presence/consistency.",
} satisfies Record<string, string>;

const QA_TOOLS = {
  "tools/qa/test_runner.py": "Canonical CSV-based QA runner (standard test suite).",
  "tools/qa/universal_test_runner.py": "Advanced CSV test runner (supports more complex constructions).",
  "tools/qa/test_suite_generator.py": "Generates empty CSV templates for manual/AI fill-in.",
  "tools/qa/batch_test_generator.py": "Bulk generation of test datasets for regression.",
  "tools/qa/eval_bios.py": "Compares generated biographies against Wikidata facts.",
  "tools/qa/lexicon_coverage_report.py": "Coverage report for intended vs implemented lexicon.",
  "tools/qa/generate_lexicon_regression_tests.py": "Builds regression tests from lexicon for CI/QA.",
} satisfies Record<string, string>;

const SCRIPTS = {
  "scripts/demo_generation.py": "Local demo of multilingual generation.",
  "scripts/demo_quad.py": "Local demo of quad output (multi-language / multi-frame).",
  "scripts/test_api_generation.py":
    "Legacy/diagnostic API generation test script (may need endpoint updates).",
  "scripts/test_tier1_load.py": "Loads Tier 1 languages to verify wrappers/PGF load behavior.",

  // Lexicon legacy scripts
  "scripts/lexicon/sync_rgl.py":
    "Legacy DB-era lexicon synchronizer (reference only unless DB pipeline exists).",
  "scripts/lexicon/wikidata_importer.py":
    "Legacy DB-era Wikidata importer (reference only unless DB pipeline exists).",
} satisfies Record<string, string>;

const UTILS = {
  // CLI-ish / important utilities
  "utils/build_lexicon_from_wikidata.py": "Offline/dump-based lexicon builder (utility CLI).",
  "utils/dump_lexicon_stats.py": "Prints lexicon coverage/size statistics (utility CLI).",
  "utils/migrate_lexicon_schema.py": "Migrates lexicon JSON shards to newer schema versions (utility CLI).",
  "utils/refresh_lexicon_index.py": "Rebuilds the fast lexicon lookup index used by API (utility CLI).",
  "utils/seed_lexicon_ai.py": "LLM-based seed generation for new language lexicons (gated).",

  // Libraries
  "utils/grammar_factory.py": "Grammar factory library (weighted topology / tiered generation).",
  "utils/logging_setup.py": "Logging configuration helpers used by tools/services.",
  "utils/wikifunctions_api_mock.py": "Local mock/stub for Wikifunctions API calls.",
} satisfies Record<string, string>;

const AI_SERVICES = {
  "ai_services/architect.py": "AI agent that generates missing language code/grammar.",
  "ai_services/surgeon.py": "AI agent that patches build failures based on compiler logs.",
  "ai_services/lexicographer.py": "AI agent that generates lexicon entries for missing data.",
  "ai_services/judge.py": "AI agent that evaluates outputs against standards.",
  "ai_services/prompts.py": "Prompt templates/config for AI services.",
  "ai_services/client.py": "Shared client wrapper to call AI services.",
} satisfies Record<string, string>;

const NLG = {
  "nlg/api.py": "NLG API module (internal).",
  "nlg/cli_frontend.py": "CLI frontend for NLG/generation experiments.",
} satisfies Record<string, string>;

const PROTOTYPES = {
  "prototypes/demo_multisentence_bio.py": "Prototype multi-sentence biography generation demo.",
  "prototypes/local_test_runner.py": "Prototype local test harness.",
  "prototypes/shared_romance_engine.py": "Prototype shared engine for romance languages.",
} satisfies Record<string, string>;

const TESTS = {
  "tests/test_api_smoke.py": "API smoke tests (fast signal).",
  "tests/test_lexicon_smoke.py": "Lexicon schema/syntax smoke tests.",
  "tests/test_gf_dynamic.py": "Validates dynamic loading/linearization of GF grammars.",
  "tests/test_multilingual_generation.py": "Multilingual generation regression tests.",
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
  if (p.startsWith("tools/")) return "Tool script.";
  if (p.startsWith("scripts/")) return "Ad-hoc script.";
  if (p.startsWith("gf/")) return "GF build tool.";
  if (p.startsWith("prototypes/")) return "Prototype script.";
  if (p.startsWith("nlg/")) return "NLG module.";

  // a few common non-python file types in this repo surface
  if (ext === "ps1") return "PowerShell script.";
  if (ext === "bat") return "Windows batch script.";
  if (ext === "json") return "JSON data/config file.";
  if (ext === "md") return "Documentation file.";

  return "Project file.";
};
