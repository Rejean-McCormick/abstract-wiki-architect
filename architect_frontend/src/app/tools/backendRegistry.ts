// architect_frontend/src/app/tools/backendRegistry.ts

export type Risk = "safe" | "moderate" | "heavy";

export type ToolParameter = {
  flag: string;
  description: string;
  example?: string;
  required?: boolean;
};

export type BackendToolMeta = {
  title: string;
  path: string;
  cmd: readonly string[];
  category: string;
  group: string;
  risk: Risk;

  // Rich Metadata
  longDescription?: string;
  parameterDocs?: ToolParameter[];
  commonFailureModes?: string[];
  supportsVerbose?: boolean;
  supportsJson?: boolean;

  /**
   * UI / operator intent
   * - hidden: keep wired, but hide from normal UI (revealed in Debug/Power user)
   * - requiresAiEnabled: backend will 403 unless ARCHITECT_ENABLE_AI_TOOLS=1
   */
  hidden?: boolean;
  requiresAiEnabled?: boolean;
};

/**
 * Backend-wired tools. Tool IDs must match backend TOOL_REGISTRY allowlist tool_id values.
 * (Legacy IDs are handled via LEGACY_TOOL_ID_ALIASES below and are not listed as runnable tools.)
 */
export const BACKEND_TOOL_REGISTRY: Record<string, BackendToolMeta> = {
  // --- DIAGNOSTICS & MAINTENANCE ---
  language_health: {
    title: "Language Health",
    path: "tools/language_health.py",
    cmd: ["python", "tools/language_health.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    longDescription:
      "Comprehensive check of the language pipeline. Verifies GF compilation status and tests the API generation endpoint with a sample payload.",
    parameterDocs: [
      { flag: "--mode", description: "compile | api | both (default)", example: "--mode compile" },
      { flag: "--fast", description: "Skip re-check of VALID files using cache" },
      { flag: "--parallel", description: "Run language checks in parallel (when supported)" },
      { flag: "--api-url", description: "Override API URL used by api-mode checks", example: "--api-url http://localhost:8000" },
      { flag: "--api-key", description: "API key for api-mode checks (if required)", example: "--api-key $ARCHITECT_API_KEY" },
      { flag: "--timeout", description: "Per-request timeout (seconds)", example: "--timeout 30" },
      { flag: "--langs", description: "Limit to specific codes", example: "--langs en fr" },
      { flag: "--no-disable-script", description: "Do not disable (or rewrite) scripts as part of checks" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
      { flag: "--json", description: "Emit machine-readable JSON summary (if supported)" },
    ],
    supportsVerbose: true,
    supportsJson: true,
  },

  diagnostic_audit: {
    title: "Diagnostic Audit",
    path: "tools/diagnostic_audit.py",
    cmd: ["python", "tools/diagnostic_audit.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    longDescription:
      "Deep system audit across matrix/index, generation artifacts, contrib artifacts, and RGL presence. Highlights missing or inconsistent components.",
    parameterDocs: [
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
      { flag: "--json", description: "Emit machine-readable JSON summary (if supported)" },
    ],
    supportsVerbose: true,
    supportsJson: true,
  },

  cleanup_root: {
    title: "Cleanup Root",
    path: "tools/cleanup_root.py",
    cmd: ["python", "tools/cleanup_root.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    longDescription:
      "Moves loose GF files into their canonical folders and cleans up temporary build artifacts.",
    parameterDocs: [
      { flag: "--dry-run", description: "Show what would be moved/deleted without acting" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
      { flag: "--json", description: "Emit machine-readable JSON summary (if supported)" },
    ],
    supportsVerbose: true,
    supportsJson: true,
  },

  // --- PERFORMANCE / DEBUG ---
  profiler: {
    title: "Performance Profiler",
    path: "tools/health/profiler.py",
    cmd: ["python", "tools/health/profiler.py"],
    risk: "safe",
    category: "Diagnostics & Maintenance",
    group: "Performance",
    longDescription: "Benchmarks the Grammar Engine's latency, throughput, and memory usage.",
    parameterDocs: [
      { flag: "--lang", description: "Target language code", example: "--lang en" },
      { flag: "--iterations", description: "Number of sentences to generate", example: "--iterations 1000" },
      { flag: "--update-baseline", description: "Save current stats as the new baseline" },
      { flag: "--threshold", description: "Regression threshold (fraction). Tool fails if regression exceeds this.", example: "--threshold 0.15" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: true,
  },

  visualize_ast: {
    title: "AST Visualizer",
    path: "tools/debug/visualize_ast.py",
    cmd: ["python", "tools/debug/visualize_ast.py"],
    risk: "safe",
    category: "QA & Testing",
    group: "Debugging",
    longDescription:
      "Emits a JSON tree for the Grammatical Framework AST. Provide either --ast, or both (--sentence and --lang).",
    parameterDocs: [
      { flag: "--ast", description: "Explicit GF AST to visualize", example: '--ast "PredVP (UsePN John_PN) (UseV run_V)"' },
      { flag: "--sentence", description: "Natural language sentence to parse", example: '--sentence "The cat eats the fish"' },
      { flag: "--lang", description: "Language code of the sentence", example: "--lang en" },
      { flag: "--pgf", description: "Override PGF path", example: "--pgf gf/AbstractWiki.pgf" },
    ],
    commonFailureModes: [
      "Missing required inputs: must provide either --ast OR (--sentence AND --lang).",
      "PGF not found or cannot be loaded (check gf/AbstractWiki.pgf).",
    ],
    supportsVerbose: false,
    supportsJson: true,
  },

  // --- BUILD SYSTEM (EVERYTHING MATRIX) ---
  build_index: {
    title: "Rebuild Everything Matrix",
    path: "tools/everything_matrix/build_index.py",
    cmd: ["python", "tools/everything_matrix/build_index.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "moderate",
    longDescription:
      "Scans the repository to rebuild the Everything Matrix status index (writes a JSON matrix file).",
    parameterDocs: [
      { flag: "--out", description: "Output path for the JSON matrix", example: "--out data/indices/everything_matrix.json" },
      { flag: "--langs", description: "Limit to specific languages", example: "--langs en fr" },
      { flag: "--force", description: "Force regeneration even if caches exist" },
      { flag: "--regen-rgl", description: "Force rerun of RGL scanner" },
      { flag: "--regen-lex", description: "Force rerun of lexicon scanner" },
      { flag: "--regen-app", description: "Force rerun of app scanner" },
      { flag: "--regen-qa", description: "Force rerun of QA scanner" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  app_scanner: {
    title: "App Scanner",
    path: "tools/everything_matrix/app_scanner.py",
    cmd: ["python", "tools/everything_matrix/app_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
    longDescription: "Scans app/frontend/backend surfaces for language support signals (outputs JSON).",
    supportsVerbose: false,
    supportsJson: true,
  },

  lexicon_scanner: {
    title: "Lexicon Scanner",
    path: "tools/everything_matrix/lexicon_scanner.py",
    cmd: ["python", "tools/everything_matrix/lexicon_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
    longDescription: "Scores lexicon maturity by scanning shard coverage (outputs JSON).",
    supportsVerbose: false,
    supportsJson: true,
  },

  qa_scanner: {
    title: "QA Scanner",
    path: "tools/everything_matrix/qa_scanner.py",
    cmd: ["python", "tools/everything_matrix/qa_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
    longDescription: "Parses QA output/logs to update quality scoring (outputs JSON).",
    supportsVerbose: false,
    supportsJson: true,
  },

  rgl_scanner: {
    title: "RGL Scanner",
    path: "tools/everything_matrix/rgl_scanner.py",
    cmd: ["python", "tools/everything_matrix/rgl_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
    longDescription: "Audits RGL grammar module presence/consistency (outputs JSON).",
    supportsVerbose: false,
    supportsJson: true,
  },

  // --- GF BUILD ---
  compile_pgf: {
    title: "Compile PGF (Build Orchestrator)",
    path: "builder/orchestrator.py",
    cmd: ["python", "builder/orchestrator.py"],
    category: "Build System",
    group: "GF Build",
    risk: "heavy",
    longDescription: "Orchestrates the full compilation of the AbstractWiki grammar into a PGF binary.",
    parameterDocs: [
      { flag: "--strategy", description: "Build strategy (implementation-defined)", example: "--strategy incremental" },
      { flag: "--langs", description: "Limit build to specific languages", example: "--langs en fr" },
      { flag: "--clean", description: "Clean build artifacts before compiling" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  bootstrap_tier1: {
    title: "Bootstrap Tier 1",
    path: "tools/bootstrap_tier1.py",
    cmd: ["python", "tools/bootstrap_tier1.py"],
    category: "Build System",
    group: "Tier Bootstrapping",
    risk: "moderate",
    longDescription: "Scaffolds initial support for Tier 1 languages using RGL modules found on disk.",
    parameterDocs: [
      { flag: "--langs", description: "Target language set", example: "--langs en fr" },
      { flag: "--force", description: "Overwrite existing scaffolds if present" },
      { flag: "--dry-run", description: "Show actions without writing changes" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  // --- LEXICON & DATA ---
  gap_filler: {
    title: "Lexicon Gap Filler",
    path: "tools/lexicon/gap_filler.py",
    cmd: ["python", "tools/lexicon/gap_filler.py"],
    risk: "safe",
    category: "Lexicon & Data",
    group: "Analysis",
    longDescription: "Compares a target language lexicon against a pivot to identify missing concepts.",
    parameterDocs: [
      { flag: "--target", description: "Language to analyze", required: true, example: "--target spa" },
      { flag: "--pivot", description: "Reference language (default: eng)", example: "--pivot eng" },
      { flag: "--data-dir", description: "Override lexicon data directory", example: "--data-dir data/lexicon" },
      { flag: "--json-out", description: "Save report to file", example: "--json-out out/gaps_spa.json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: true,
  },

  harvest_lexicon: {
    title: "Harvest Lexicon",
    path: "tools/harvest_lexicon.py",
    cmd: ["python", "tools/harvest_lexicon.py"],
    category: "Lexicon & Data",
    group: "Mining & Harvesting",
    risk: "moderate",
    longDescription: "Mines vocabulary from external sources into JSON shards.",
    parameterDocs: [
      { flag: "--lang", description: "Single language to harvest", example: "--lang en" },
      { flag: "--langs", description: "Multiple languages to harvest", example: "--langs en fr" },
      { flag: "--source", description: "Harvest source identifier", example: "--source wikidata" },
      { flag: "--out", description: "Output directory for harvested shards", example: "--out data/lexicon/harvest" },
      { flag: "--root", description: "Project root override (advanced)", example: "--root /path/to/repo" },
      { flag: "--limit", description: "Limit items fetched (per language/source)", example: "--limit 5000" },
      { flag: "--max", description: "Hard cap on total items", example: "--max 100000" },
      { flag: "--dry-run", description: "Show what would be harvested without writing files" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  build_lexicon_wikidata: {
    title: "Build Lexicon from Wikidata",
    path: "tools/build_lexicon_from_wikidata.py",
    cmd: ["python", "tools/build_lexicon_from_wikidata.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "moderate",
    longDescription: "Builds lexicon shards directly from Wikidata (online).",
    parameterDocs: [
      { flag: "--lang", description: "Target language", example: "--lang en" },
      { flag: "--out", description: "Output path/directory", example: "--out data/lexicon" },
      { flag: "--limit", description: "Limit number of items", example: "--limit 5000" },
      { flag: "--dry-run", description: "Run without writing files" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  refresh_index: {
    title: "Refresh Lexicon Index",
    path: "utils/refresh_lexicon_index.py",
    cmd: ["python", "utils/refresh_lexicon_index.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "safe",
    longDescription: "Rebuilds the fast lexicon lookup index used by API.",
    parameterDocs: [
      { flag: "--langs", description: "Limit to specific languages", example: "--langs en fr" },
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--out", description: "Output path (if supported)", example: "--out data/lexicon/index.json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  migrate_schema: {
    title: "Migrate Lexicon Schema",
    path: "utils/migrate_lexicon_schema.py",
    cmd: ["python", "utils/migrate_lexicon_schema.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "moderate",
    longDescription: "Migrates lexicon JSON shards to newer schema versions.",
    parameterDocs: [
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--in-place", description: "Modify files in-place (no separate output dir)" },
      { flag: "--dry-run", description: "Show changes without writing" },
      { flag: "--from", description: "Source schema version", example: "--from v1" },
      { flag: "--to", description: "Target schema version", example: "--to v2" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  dump_stats: {
    title: "Dump Lexicon Stats",
    path: "utils/dump_lexicon_stats.py",
    cmd: ["python", "utils/dump_lexicon_stats.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "safe",
    longDescription: "Prints lexicon coverage/size statistics.",
    parameterDocs: [
      { flag: "--langs", description: "Limit to specific languages", example: "--langs en fr" },
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--format", description: "Output format", example: "--format json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  // --- QA & TESTING TOOLS ---
  ambiguity_detector: {
    title: "Ambiguity Detector (AI)",
    path: "tools/qa/ambiguity_detector.py",
    cmd: ["python", "tools/qa/ambiguity_detector.py"],
    risk: "heavy",
    category: "QA & Testing",
    group: "AI Analysis",
    requiresAiEnabled: true,
    longDescription:
      "Uses AI to generate ambiguous sentences and checks if the grammar produces multiple parse trees.",
    parameterDocs: [
      { flag: "--lang", description: "Target language", required: true, example: "--lang en" },
      { flag: "--sentence", description: "Specific sentence to analyze (optional)", example: '--sentence "I saw her duck"' },
      { flag: "--topic", description: "Topic for sentence generation", example: "--topic biography" },
      { flag: "--json-out", description: "Write JSON report to file", example: "--json-out out/ambiguity_en.json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
    supportsJson: false,
  },

  eval_bios: {
    title: "Eval Biographies",
    path: "tools/qa/eval_bios.py",
    cmd: ["python", "tools/qa/eval_bios.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    parameterDocs: [
      { flag: "--langs", description: "Languages to evaluate", example: "--langs en fr" },
      { flag: "--limit", description: "Limit items evaluated", example: "--limit 200" },
      { flag: "--out", description: "Output path for report", example: "--out out/eval_bios.json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  lexicon_coverage: {
    title: "Lexicon Coverage Report",
    path: "tools/qa/lexicon_coverage_report.py",
    cmd: ["python", "tools/qa/lexicon_coverage_report.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
    parameterDocs: [
      { flag: "--langs", description: "Languages to report", example: "--langs en fr" },
      { flag: "--out", description: "Output path", example: "--out out/lex_coverage.json" },
      { flag: "--format", description: "Output format", example: "--format json" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
      { flag: "--fail-on-errors", description: "Exit non-zero if errors are encountered" },
    ],
    supportsVerbose: true,
  },

  universal_test_runner: {
    title: "Universal Test Runner",
    path: "tools/qa/universal_test_runner.py",
    cmd: ["python", "tools/qa/universal_test_runner.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    parameterDocs: [
      { flag: "--suite", description: "Specific test suite CSV to run", example: "--suite tools/qa/generated_datasets/test_suite_en.csv" },
      { flag: "--in", description: "Input directory (if suite paths are relative)", example: "--in tools/qa/generated_datasets" },
      { flag: "--out", description: "Output report path", example: "--out out/test_results.json" },
      { flag: "--langs", description: "Filter by language", example: "--langs en fr" },
      { flag: "--limit", description: "Limit test cases executed", example: "--limit 500" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  batch_test_generator: {
    title: "Batch Test Generator",
    path: "tools/qa/batch_test_generator.py",
    cmd: ["python", "tools/qa/batch_test_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    parameterDocs: [
      { flag: "--langs", description: "Languages to generate for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      { flag: "--limit", description: "Limit examples generated", example: "--limit 2000" },
      { flag: "--seed", description: "Random seed", example: "--seed 1337" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  test_suite_generator: {
    title: "Test Suite Generator",
    path: "tools/qa/test_suite_generator.py",
    cmd: ["python", "tools/qa/test_suite_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
    parameterDocs: [
      { flag: "--langs", description: "Languages to generate templates for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  generate_lexicon_regression_tests: {
    title: "Generate Lexicon Regression Tests",
    path: "tools/qa/generate_lexicon_regression_tests.py",
    cmd: ["python", "tools/qa/generate_lexicon_regression_tests.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "heavy",
    parameterDocs: [
      { flag: "--langs", description: "Languages to generate for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      { flag: "--limit", description: "Limit cases", example: "--limit 5000" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  // --- AI TOOLS ---
  seed_lexicon: {
    title: "Seed Lexicon (AI)",
    path: "utils/seed_lexicon_ai.py",
    cmd: ["python", "utils/seed_lexicon_ai.py"],
    category: "AI Tools & Services",
    group: "AI Utilities",
    risk: "heavy",
    requiresAiEnabled: true,
    hidden: true,
    parameterDocs: [
      { flag: "--langs", description: "Languages to seed", example: "--langs sw yo" },
      { flag: "--limit", description: "Limit items seeded per language", example: "--limit 2000" },
      { flag: "--dry-run", description: "Show what would be generated without writing" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  ai_refiner: {
    title: "AI Refiner",
    path: "tools/ai_refiner.py",
    cmd: ["python", "tools/ai_refiner.py"],
    category: "AI Tools & Services",
    group: "Agents",
    risk: "heavy",
    requiresAiEnabled: true,
    hidden: true,
    parameterDocs: [
      { flag: "--langs", description: "Languages to refine", example: "--langs en fr" },
      { flag: "--dry-run", description: "Run without writing changes" },
      { flag: "--verbose", description: "Enable detailed step-by-step logs" },
    ],
    supportsVerbose: true,
  },

  // --- PYTEST (WIRED) ---
  run_smoke_tests: {
    title: "Run Smoke Tests (Lexicon)",
    path: "tests/test_lexicon_smoke.py",
    cmd: ["python", "-m", "pytest", "tests/test_lexicon_smoke.py"],
    category: "QA & Testing",
    group: "Pytest • Smoke",
    risk: "safe",
    parameterDocs: [
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression (NOTE: backend must allow the following value token)", example: '-k "smoke and not slow"' },
      { flag: "-m", description: "Run tests matching marker (NOTE: backend must allow the following value token)", example: '-m "not integration"' },
      { flag: "--maxfail", description: "Stop after N failures (NOTE: backend must allow the following value token)", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" },
    ],
    supportsVerbose: true,
  },

  run_judge: {
    title: "Run Judge (Integration)",
    path: "tests/integration/test_quality.py",
    cmd: ["python", "-m", "pytest", "tests/integration/test_quality.py"],
    category: "QA & Testing",
    group: "Pytest • Judge",
    risk: "heavy",
    parameterDocs: [
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression (NOTE: backend must allow the following value token)", example: '-k "judge and not slow"' },
      { flag: "-m", description: "Run tests matching marker (NOTE: backend must allow the following value token)", example: '-m "integration"' },
      { flag: "--maxfail", description: "Stop after N failures (NOTE: backend must allow the following value token)", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" },
    ],
    supportsVerbose: true,
  },

  test_api_smoke: {
    title: "Test API Smoke",
    path: "tests/test_api_smoke.py",
    cmd: ["python", "-m", "pytest", "tests/test_api_smoke.py"],
    category: "QA & Testing",
    group: "Pytest • API",
    risk: "safe",
    supportsVerbose: true,
  },

  test_gf_dynamic: {
    title: "Test GF Dynamic",
    path: "tests/test_gf_dynamic.py",
    cmd: ["python", "-m", "pytest", "tests/test_gf_dynamic.py"],
    category: "QA & Testing",
    group: "Pytest • GF",
    risk: "safe",
    supportsVerbose: true,
  },

  test_multilingual_generation: {
    title: "Test Multilingual Generation",
    path: "tests/test_multilingual_generation.py",
    cmd: ["python", "-m", "pytest", "tests/test_multilingual_generation.py"],
    category: "QA & Testing",
    group: "Pytest • Generation",
    risk: "safe",
    supportsVerbose: true,
  },
} as const;

export type BackendToolId = keyof typeof BACKEND_TOOL_REGISTRY;

export const WIRED_TOOL_IDS = new Set<string>(Object.keys(BACKEND_TOOL_REGISTRY));

export const TOOL_ID_BY_PATH: Record<string, string> = Object.fromEntries(
  Object.entries(BACKEND_TOOL_REGISTRY).map(([toolId, meta]) => [meta.path, toolId])
);

/**
 * Legacy tool_ids that used to exist in the UI but are not backend-wired anymore.
 * The UI should remap these before calling POST /tools/run.
 */
export const LEGACY_TOOL_ID_ALIASES: Record<string, BackendToolId> = {
  check_all_languages: "language_health",
  audit_languages: "language_health",
  test_runner: "universal_test_runner",
} as const;

/** Convenience: tool_ids that are hidden unless Debug/Power user is enabled */
export const POWER_USER_TOOL_IDS = new Set<string>(
  Object.entries(BACKEND_TOOL_REGISTRY)
    .filter(([, meta]) => Boolean(meta.hidden))
    .map(([toolId]) => toolId)
);
