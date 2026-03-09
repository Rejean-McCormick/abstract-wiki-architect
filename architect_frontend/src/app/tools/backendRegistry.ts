// architect_frontend/src/app/tools/backendRegistry.ts

export type Risk = "safe" | "moderate" | "heavy";

export type WorkflowId =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

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
   * - workflows: workflow dropdown memberships
   * - hidden: keep wired, but hide from normal UI (revealed in Debug/Power user)
   * - requiresAiEnabled: backend will 403 unless ARCHITECT_ENABLE_AI_TOOLS=1
   */
  workflows?: readonly WorkflowId[];
  hidden?: boolean;
  requiresAiEnabled?: boolean;
};

// ----------------------------------------------------------------------------
// Shared parameter docs (avoid repetition + keep wording consistent)
// ----------------------------------------------------------------------------
const P_VERBOSE: ToolParameter = {
  flag: "--verbose",
  description: "Enable detailed step-by-step logs",
};

const P_JSON: ToolParameter = {
  flag: "--json",
  description: "Emit machine-readable JSON summary (if supported)",
};

const P_DRY_RUN: ToolParameter = {
  flag: "--dry-run",
  description: "Dry run. Show what would happen without writing changes",
  example: "--dry-run",
};

function withParams(...params: ToolParameter[]) {
  return params.filter(Boolean);
}

/**
 * Backend-wired tools. Tool IDs must match backend TOOL_REGISTRY allowlist tool_id values.
 */
export const BACKEND_TOOL_REGISTRY = {
  // --- DIAGNOSTICS & MAINTENANCE ---
  language_health: {
    title: "Language Health",
    path: "tools/language_health.py",
    cmd: ["python", "tools/language_health.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    workflows: ["recommended", "language_integration", "qa_validation"],
    longDescription:
      "Comprehensive check of the language pipeline. Verifies GF compilation status and tests the API generation endpoint with a sample payload. API keys remain env-only.",
    parameterDocs: withParams(
      { flag: "--mode", description: "compile | api | both (default)", example: "--mode both" },
      { flag: "--fast", description: "Skip re-check of unchanged VALID files using cache" },
      { flag: "--parallel", description: "Parallelism level for checks", example: "--parallel 4" },
      {
        flag: "--api-url",
        description: "Override API URL used by api-mode checks",
        example: "--api-url http://127.0.0.1:8000",
      },
      { flag: "--timeout", description: "Per-request timeout (seconds)", example: "--timeout 30" },
      { flag: "--limit", description: "Limit number of languages checked (0 = all)", example: "--limit 10" },
      { flag: "--langs", description: "Limit to specific ISO-2 codes", example: "--langs en fr" },
      { flag: "--no-disable-script", description: "Do not disable or rewrite scripts during checks" },
      P_VERBOSE,
      P_JSON
    ),
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
    workflows: ["qa_validation", "debug_recovery"],
    longDescription:
      "Forensics audit across the matrix/index, generation artifacts, contrib artifacts, and RGL presence. Highlights stale, missing, or inconsistent components.",
    parameterDocs: withParams(P_VERBOSE, P_JSON),
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
    workflows: ["debug_recovery"],
    hidden: true,
    longDescription:
      "Moves loose GF files into their canonical folders and cleans up temporary build artifacts.",
    parameterDocs: withParams(P_DRY_RUN, P_VERBOSE, P_JSON),
    supportsVerbose: true,
    supportsJson: true,
  },

  // --- PERFORMANCE / DEBUG ---
  profiler: {
    title: "Performance Profiler",
    path: "tools/health/profiler.py",
    cmd: ["python", "tools/health/profiler.py"],
    category: "Diagnostics & Maintenance",
    group: "Performance",
    risk: "safe",
    workflows: ["qa_validation"],
    longDescription:
      "Benchmarks Grammar Engine latency, throughput, and memory usage. Prints structured performance output.",
    parameterDocs: withParams(
      { flag: "--lang", description: "Target language code", example: "--lang en" },
      { flag: "--iterations", description: "Number of linearizations to run", example: "--iterations 1000" },
      { flag: "--update-baseline", description: "Save current stats as the new baseline" },
      {
        flag: "--threshold",
        description: "Regression threshold (fraction). Tool fails if regression exceeds this.",
        example: "--threshold 0.15",
      },
      P_VERBOSE
    ),
    supportsVerbose: true,
    supportsJson: true,
  },

  visualize_ast: {
    title: "AST Visualizer",
    path: "tools/debug/visualize_ast.py",
    cmd: ["python", "tools/debug/visualize_ast.py"],
    category: "QA & Testing",
    group: "Debugging",
    risk: "safe",
    workflows: ["qa_validation", "debug_recovery"],
    hidden: true,
    longDescription:
      "Emits a JSON tree for the GF AST. Provide either --ast, or both --sentence and --lang.",
    parameterDocs: withParams(
      {
        flag: "--ast",
        description: "Explicit GF AST to visualize",
        example: '--ast "PredVP (UsePN John_PN) (UseV run_V)"',
      },
      {
        flag: "--sentence",
        description: "Natural-language sentence to parse",
        example: '--sentence "The cat eats the fish"',
      },
      { flag: "--lang", description: "Language code of the sentence", example: "--lang en" },
      { flag: "--pgf", description: "Override PGF path", example: "--pgf gf/semantik_architect.pgf" }
    ),
    commonFailureModes: [
      "Missing required inputs: provide either --ast OR (--sentence AND --lang).",
      "PGF not found or cannot be loaded (check gf/semantik_architect.pgf).",
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
    workflows: ["recommended", "language_integration", "build_matrix"],
    longDescription:
      "Canonical matrix-refresh entrypoint. Scans the repository and rebuilds everything_matrix.json.",
    parameterDocs: withParams(
      { flag: "--out", description: "Output path for the JSON matrix", example: "--out data/indices/everything_matrix.json" },
      { flag: "--langs", description: "Limit to specific ISO-2 languages", example: "--langs en fr" },
      { flag: "--force", description: "Force regeneration even if caches exist" },
      { flag: "--regen-rgl", description: "Force rerun of RGL scanner" },
      { flag: "--regen-lex", description: "Force rerun of lexicon scanner" },
      { flag: "--regen-app", description: "Force rerun of app scanner" },
      { flag: "--regen-qa", description: "Force rerun of QA scanner" },
      P_VERBOSE
    ),
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
    workflows: ["build_matrix", "debug_recovery"],
    hidden: true,
    longDescription: "Scans app/frontend/backend surfaces for language support signals.",
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
    workflows: ["build_matrix", "debug_recovery"],
    hidden: true,
    longDescription: "Scores lexicon maturity by scanning shard coverage.",
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
    workflows: ["build_matrix", "debug_recovery"],
    hidden: true,
    longDescription: "Parses QA output/logs to update matrix quality scoring.",
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
    workflows: ["build_matrix", "debug_recovery"],
    hidden: true,
    longDescription: "Audits RGL grammar module presence and consistency.",
    supportsVerbose: false,
    supportsJson: true,
  },

  // --- GF BUILD ---
  compile_pgf: {
    title: "Compile PGF (Build Orchestrator)",
    path: "builder/orchestrator/__main__.py",
    cmd: ["python", "-m", "builder.orchestrator"],
    category: "Build System",
    group: "GF Build",
    risk: "heavy",
    workflows: ["recommended", "language_integration", "build_matrix"],
    longDescription:
      "Two-phase build orchestrator that verifies inputs and links the Semantik Architect grammar into a PGF binary.",
    parameterDocs: withParams(
      { flag: "--strategy", description: "Build strategy", example: "--strategy AUTO" },
      { flag: "--langs", description: "Limit build to specific languages", example: "--langs en fr" },
      { flag: "--clean", description: "Clean build artifacts before compiling" },
      { flag: "--max-workers", description: "Thread pool size for compilation", example: "--max-workers 4" },
      { flag: "--no-preflight", description: "Skip RGL pin/bridge preflight checks" },
      { flag: "--regen-safe", description: "Regenerate SAFE_MODE grammars even if present" },
      P_VERBOSE
    ),
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
    workflows: ["language_integration", "build_matrix", "debug_recovery"],
    longDescription:
      "Bootstraps Tier 1 wrappers and bridge files for RGL-backed languages.",
    parameterDocs: withParams(
      { flag: "--langs", description: "Target language set", example: "--langs en fr" },
      { flag: "--force", description: "Overwrite existing scaffolds if present" },
      P_DRY_RUN,
      P_VERBOSE
    ),
    supportsVerbose: true,
    supportsJson: false,
  },

  // --- LEXICON & DATA ---
  gap_filler: {
    title: "Lexicon Gap Filler",
    path: "tools/lexicon/gap_filler.py",
    cmd: ["python", "tools/lexicon/gap_filler.py"],
    category: "Lexicon & Data",
    group: "Analysis",
    risk: "safe",
    workflows: ["language_integration", "lexicon_work"],
    longDescription:
      "Compares target and pivot lexicons to identify missing concepts. Supports current language-folder layout and legacy flat-file fallback.",
    parameterDocs: withParams(
      { flag: "--target", description: "Target language code", required: true, example: "--target fr" },
      { flag: "--pivot", description: "Pivot language code", example: "--pivot en" },
      { flag: "--data-dir", description: "Base directory to search", example: "--data-dir data/lexicon" },
      { flag: "--json-out", description: "Save gap report as JSON", example: "--json-out out/gaps_fr.json" },
      P_VERBOSE
    ),
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
    workflows: ["language_integration", "lexicon_work"],
    longDescription:
      "Universal lexicon harvester. Supports the positional subcommands `wordnet` and `wikidata`.",
    parameterDocs: withParams(
      {
        flag: "wordnet",
        description: "Subcommand: harvest from GF WordNet (positional)",
        example: "wordnet --lang en --root /path/to/gf-wordnet --out data/lexicon",
      },
      {
        flag: "wikidata",
        description: "Subcommand: harvest from explicit Wikidata QIDs (positional)",
        example: "wikidata --lang en --input qids.json --domain people --out data/lexicon",
      },
      { flag: "--lang", description: "Target language (ISO-2)", example: "--lang en" },
      {
        flag: "--root",
        description: "WordNet root, repo root, its gf/ dir, or WordNet.gf path (wordnet only)",
        example: "--root /mnt/c/MyCode/SemantiK_Architect/gf-wordnet",
      },
      { flag: "--out", description: "Output directory for shard JSON files", example: "--out data/lexicon" },
      { flag: "--input", description: "Input JSON containing QIDs (wikidata only)", example: "--input qids.json" },
      { flag: "--domain", description: "Shard/domain name (wikidata only)", example: "--domain people" }
    ),
    commonFailureModes: [
      "Missing subcommand: first arg must be 'wordnet' or 'wikidata'.",
      "Wikidata mode: missing --input qids.json.",
      "WordNet mode: missing --root pointing to a directory containing WordNet.gf.",
    ],
    supportsVerbose: false,
    supportsJson: false,
  },

  build_lexicon_wikidata: {
    title: "Build Lexicon from Wikidata",
    path: "utils/build_lexicon_from_wikidata.py",
    cmd: ["python", "utils/build_lexicon_from_wikidata.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "moderate",
    workflows: ["lexicon_work"],
    hidden: true,
    longDescription: "Builds lexicon shards directly from Wikidata.",
    parameterDocs: withParams(
      { flag: "--lang", description: "Target language", example: "--lang en" },
      { flag: "--out", description: "Output path or directory", example: "--out data/lexicon" },
      { flag: "--limit", description: "Limit number of items", example: "--limit 5000" },
      P_DRY_RUN,
      P_VERBOSE
    ),
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
    workflows: ["lexicon_work"],
    longDescription: "Rebuilds the fast lexicon lookup index used by the API.",
    parameterDocs: withParams(
      { flag: "--langs", description: "Limit to specific languages", example: "--langs en fr" },
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--out", description: "Output path", example: "--out data/lexicon/index.json" },
      P_VERBOSE
    ),
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
    workflows: ["lexicon_work"],
    hidden: true,
    longDescription: "Migrates lexicon JSON shards to newer schema versions.",
    parameterDocs: withParams(
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--in-place", description: "Modify files in-place" },
      P_DRY_RUN,
      { flag: "--from", description: "Source schema version", example: "--from v1" },
      { flag: "--to", description: "Target schema version", example: "--to v2" },
      P_VERBOSE
    ),
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
    workflows: ["lexicon_work"],
    longDescription: "Prints lexicon coverage and size statistics.",
    parameterDocs: withParams(
      { flag: "--langs", description: "Limit to specific languages", example: "--langs en fr" },
      { flag: "--root", description: "Lexicon root directory", example: "--root data/lexicon" },
      { flag: "--format", description: "Output format", example: "--format json" },
      P_VERBOSE
    ),
    supportsVerbose: true,
    supportsJson: false,
  },

  // --- QA & TESTING TOOLS ---
  ambiguity_detector: {
    title: "Ambiguity Detector (AI)",
    path: "tools/qa/ambiguity_detector.py",
    cmd: ["python", "tools/qa/ambiguity_detector.py"],
    category: "QA & Testing",
    group: "AI Analysis",
    risk: "heavy",
    workflows: ["ai_assist"],
    requiresAiEnabled: true,
    hidden: true,
    longDescription:
      "Uses AI to generate ambiguous sentences and checks whether the grammar yields multiple parse trees.",
    parameterDocs: withParams(
      { flag: "--lang", description: "Target language", required: true, example: "--lang en" },
      { flag: "--sentence", description: "Specific sentence to analyze", example: '--sentence "I saw her duck"' },
      { flag: "--topic", description: "Topic for sentence generation", example: "--topic biography" },
      { flag: "--json-out", description: "Write JSON report to a file", example: "--json-out out/ambiguity_en.json" },
      P_VERBOSE
    ),
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
    workflows: ["qa_validation"],
    hidden: true,
    longDescription: "Compares generated biographies against Wikidata facts.",
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to evaluate", example: "--langs en fr" },
      { flag: "--limit", description: "Limit items evaluated", example: "--limit 200" },
      { flag: "--out", description: "Output path for report", example: "--out out/eval_bios.json" },
      P_VERBOSE
    ),
    supportsVerbose: true,
  },

  lexicon_coverage: {
    title: "Lexicon Coverage Report",
    path: "tools/qa/lexicon_coverage_report.py",
    cmd: ["python", "tools/qa/lexicon_coverage_report.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
    workflows: ["language_integration", "lexicon_work"],
    longDescription:
      "Checks lexicon shard presence, counts, collisions, and schema/data issues for the targeted language set.",
    parameterDocs: withParams(
      { flag: "--lexicon-dir", description: "Root lexicon directory", example: "--lexicon-dir data/lexicon" },
      { flag: "--lang", description: "Target language filter (repeatable)", example: "--lang en" },
      { flag: "--target-core", description: "Expected core target size", example: "--target-core 150" },
      { flag: "--target-conc", description: "Expected conceptual target size", example: "--target-conc 500" },
      { flag: "--target-bio", description: "Minimum biography target", example: "--target-bio 50" },
      { flag: "--out", description: "Output JSON path", example: "--out out/lexicon_coverage.json" },
      { flag: "--no-md", description: "Skip Markdown output" },
      { flag: "--include-files", description: "Include per-file details in the report" },
      { flag: "--fail-on-errors", description: "Exit non-zero if errors are encountered" }
    ),
    supportsVerbose: true,
    supportsJson: false,
  },

  universal_test_runner: {
    title: "Universal Test Runner",
    path: "tools/qa/universal_test_runner.py",
    cmd: ["python", "tools/qa/universal_test_runner.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    workflows: ["qa_validation"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "--dataset-dir", description: "Directory containing CSV datasets", example: "--dataset-dir tools/qa/generated_datasets" },
      { flag: "--pattern", description: "Filename glob to select datasets", example: '--pattern "test_suite_*.csv"' },
      { flag: "--langs", description: "Filter by language codes", example: "--langs en fr" },
      { flag: "--limit", description: "Limit test cases executed", example: "--limit 500" },
      { flag: "--fail-fast", description: "Stop on first failure" },
      { flag: "--strict", description: "Treat warnings as failures / stricter assertions" },
      { flag: "--print-failures", description: "Write failing cases to a file", example: "--print-failures out/failures.txt" },
      { flag: "--json-report", description: "Write JSON report to a file", example: "--json-report out/test_results.json" },
      P_VERBOSE
    ),
    supportsVerbose: true,
  },

  batch_test_generator: {
    title: "Batch Test Generator",
    path: "tools/qa/batch_test_generator.py",
    cmd: ["python", "tools/qa/batch_test_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    workflows: ["qa_validation"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to generate for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      { flag: "--limit", description: "Limit examples generated", example: "--limit 2000" },
      { flag: "--seed", description: "Random seed", example: "--seed 1337" },
      P_VERBOSE
    ),
    supportsVerbose: true,
  },

  test_suite_generator: {
    title: "Test Suite Generator",
    path: "tools/qa/test_suite_generator.py",
    cmd: ["python", "tools/qa/test_suite_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
    workflows: ["qa_validation"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to generate templates for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      P_VERBOSE
    ),
    supportsVerbose: true,
  },

  generate_lexicon_regression_tests: {
    title: "Generate Lexicon Regression Tests",
    path: "tools/qa/generate_lexicon_regression_tests.py",
    cmd: ["python", "tools/qa/generate_lexicon_regression_tests.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "heavy",
    workflows: ["qa_validation"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to generate for", example: "--langs en fr" },
      { flag: "--out", description: "Output directory", example: "--out tools/qa/generated_datasets" },
      { flag: "--limit", description: "Limit cases", example: "--limit 5000" },
      { flag: "--lexicon-dir", description: "Lexicon root directory", example: "--lexicon-dir data/lexicon" },
      P_VERBOSE
    ),
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
    workflows: ["ai_assist", "lexicon_work"],
    requiresAiEnabled: true,
    hidden: true,
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to seed", example: "--langs sw yo" },
      { flag: "--limit", description: "Limit items seeded per language", example: "--limit 2000" },
      P_DRY_RUN,
      P_VERBOSE
    ),
    supportsVerbose: true,
  },

  ai_refiner: {
    title: "AI Refiner",
    path: "tools/ai_refiner.py",
    cmd: ["python", "tools/ai_refiner.py"],
    category: "AI Tools & Services",
    group: "Agents",
    risk: "heavy",
    workflows: ["ai_assist"],
    requiresAiEnabled: true,
    hidden: true,
    parameterDocs: withParams(
      { flag: "--langs", description: "Languages to refine", example: "--langs en fr" },
      P_DRY_RUN,
      P_VERBOSE
    ),
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
    workflows: ["qa_validation", "debug_recovery"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression", example: '-k "smoke and not slow"' },
      { flag: "-m", description: "Run tests matching marker", example: '-m "not integration"' },
      { flag: "--maxfail", description: "Stop after N failures", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" }
    ),
    supportsVerbose: true,
  },

  run_judge: {
    title: "Run Judge (Integration)",
    path: "tests/integration/test_quality.py",
    cmd: ["python", "-m", "pytest", "tests/integration/test_quality.py"],
    category: "QA & Testing",
    group: "Pytest • Judge",
    risk: "heavy",
    workflows: ["recommended", "language_integration", "qa_validation"],
    parameterDocs: withParams(
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression", example: '-k "judge and not slow"' },
      { flag: "-m", description: "Run tests matching marker", example: '-m "integration"' },
      { flag: "--maxfail", description: "Stop after N failures", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" }
    ),
    supportsVerbose: true,
  },

  test_api_smoke: {
    title: "Test API Smoke",
    path: "tests/test_api_smoke.py",
    cmd: ["python", "-m", "pytest", "tests/test_api_smoke.py"],
    category: "QA & Testing",
    group: "Pytest • API",
    risk: "safe",
    workflows: ["qa_validation", "debug_recovery"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression", example: '-k "smoke and not slow"' },
      { flag: "-m", description: "Run tests matching marker", example: '-m "not integration"' },
      { flag: "--maxfail", description: "Stop after N failures", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" }
    ),
    supportsVerbose: true,
  },

  test_gf_dynamic: {
    title: "Test GF Dynamic",
    path: "tests/test_gf_dynamic.py",
    cmd: ["python", "-m", "pytest", "tests/test_gf_dynamic.py"],
    category: "QA & Testing",
    group: "Pytest • GF",
    risk: "safe",
    workflows: ["qa_validation", "debug_recovery"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression", example: '-k "dynamic and not slow"' },
      { flag: "-m", description: "Run tests matching marker", example: '-m "not integration"' },
      { flag: "--maxfail", description: "Stop after N failures", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" }
    ),
    supportsVerbose: true,
  },

  test_multilingual_generation: {
    title: "Test Multilingual Generation",
    path: "tests/test_multilingual_generation.py",
    cmd: ["python", "-m", "pytest", "tests/test_multilingual_generation.py"],
    category: "QA & Testing",
    group: "Pytest • Generation",
    risk: "safe",
    workflows: ["qa_validation", "debug_recovery"],
    hidden: true,
    parameterDocs: withParams(
      { flag: "-q", description: "Quiet output" },
      { flag: "-vv", description: "Very verbose output" },
      { flag: "-k", description: "Filter tests by expression", example: '-k "multilingual and not slow"' },
      { flag: "-m", description: "Run tests matching marker", example: '-m "not integration"' },
      { flag: "--maxfail", description: "Stop after N failures", example: "--maxfail 1" },
      { flag: "--disable-warnings", description: "Disable warning summary" }
    ),
    supportsVerbose: true,
  },
} as const satisfies Record<string, BackendToolMeta>;

export type BackendToolId = keyof typeof BACKEND_TOOL_REGISTRY;

export type WorkflowStep = {
  title: string;
  toolId?: BackendToolId;
  args?: string;
};

export type WorkflowMeta = {
  label: string;
  description: string;
  recommendedSteps: readonly WorkflowStep[];
};

export const WORKFLOW_REGISTRY = {
  recommended: {
    label: "Recommended",
    description: "Shortest safe operator path for most day-to-day work.",
    recommendedSteps: [
      {
        title: "Refresh matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate compile + runtime",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
      { title: "Generate one sentence" },
      {
        title: "Run judge",
        toolId: "run_judge",
        args: "-q",
      },
    ],
  },

  language_integration: {
    label: "Language Integration",
    description: "Add or repair one language end to end.",
    recommendedSteps: [
      { title: "Add or change language files" },
      {
        title: "Refresh matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Validate lexicon",
        toolId: "lexicon_coverage",
        args: "--lang <lang> --include-files",
      },
      {
        title: "Harvest or fill gaps if needed",
        toolId: "harvest_lexicon",
        args: "wordnet --lang <lang> --root <gf-wordnet-root> --out data/lexicon",
      },
      {
        title: "Compare against pivot if needed",
        toolId: "gap_filler",
        args: "--target <lang> --pivot en --data-dir data/lexicon --verbose",
      },
      {
        title: "Bootstrap Tier 1 if wrappers are missing",
        toolId: "bootstrap_tier1",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Compile PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate compile + runtime",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
      { title: "Generate one sentence" },
      {
        title: "Run judge",
        toolId: "run_judge",
        args: "-q",
      },
    ],
  },

  lexicon_work: {
    label: "Lexicon Work",
    description: "Harvest, compare, validate, and index lexicon data.",
    recommendedSteps: [
      {
        title: "Harvest lexicon data",
        toolId: "harvest_lexicon",
        args: "wordnet --lang <lang> --root <gf-wordnet-root> --out data/lexicon",
      },
      {
        title: "Fill gaps against a pivot",
        toolId: "gap_filler",
        args: "--target <lang> --pivot en --data-dir data/lexicon --verbose",
      },
      {
        title: "Check coverage",
        toolId: "lexicon_coverage",
        args: "--lang <lang> --include-files",
      },
      {
        title: "Refresh lookup index",
        toolId: "refresh_index",
        args: "--langs <lang> --root data/lexicon --verbose",
      },
      {
        title: "Re-check language health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
    ],
  },

  build_matrix: {
    label: "Build & Matrix",
    description: "Inventory refresh, scanner-level inspection, and PGF build orchestration.",
    recommendedSteps: [
      {
        title: "Refresh matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
    ],
  },

  qa_validation: {
    label: "QA & Validation",
    description: "Health checks, regressions, smoke tests, and performance validation.",
    recommendedSteps: [
      {
        title: "Run language health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
      { title: "Generate one sentence" },
      {
        title: "Run judge",
        toolId: "run_judge",
        args: "-q",
      },
      {
        title: "Profile performance",
        toolId: "profiler",
        args: "--lang <lang> --iterations 1000 --verbose",
      },
      {
        title: "Run diagnostic audit if results look inconsistent",
        toolId: "diagnostic_audit",
        args: "--json --verbose",
      },
    ],
  },

  debug_recovery: {
    label: "Debug & Recovery",
    description: "Use when the repo, matrix, or runtime state looks wrong.",
    recommendedSteps: [
      {
        title: "Run diagnostic audit",
        toolId: "diagnostic_audit",
        args: "--json --verbose",
      },
      {
        title: "Run the specific scanner or smoke test you need",
      },
      {
        title: "Fix or regenerate missing assets",
      },
      {
        title: "Refresh matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
    ],
  },

  ai_assist: {
    label: "AI Assist",
    description: "AI-only tools for seeding or upgrading after deterministic tools show a real gap.",
    recommendedSteps: [
      {
        title: "Run deterministic checks first",
      },
      {
        title: "Use the AI tool you actually need",
      },
      {
        title: "Refresh matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
      {
        title: "Run judge",
        toolId: "run_judge",
        args: "-q",
      },
    ],
  },

  all: {
    label: "All",
    description: "Show the full wired registry, filtered only by visibility/risk toggles.",
    recommendedSteps: [],
  },
} as const satisfies Record<WorkflowId, WorkflowMeta>;

export const WORKFLOW_IDS = Object.freeze(Object.keys(WORKFLOW_REGISTRY) as WorkflowId[]);
export const DEFAULT_WORKFLOW_ID: WorkflowId = "recommended";

// --- Typed entries to avoid "property does not exist" on optional fields
const REGISTRY_ENTRIES = Object.entries(BACKEND_TOOL_REGISTRY) as [BackendToolId, BackendToolMeta][];

export const WIRED_TOOL_IDS = new Set<BackendToolId>(REGISTRY_ENTRIES.map(([toolId]) => toolId));

export const NORMAL_MODE_TOOL_IDS = new Set<BackendToolId>(
  REGISTRY_ENTRIES.filter(([, meta]) => !meta.hidden).map(([toolId]) => toolId)
);

export const TOOL_ID_BY_PATH: Record<string, BackendToolId> = Object.fromEntries(
  REGISTRY_ENTRIES.map(([toolId, meta]) => [meta.path, toolId])
);

/** Convenience: tool_ids that are hidden unless Debug/Power user is enabled */
export const POWER_USER_TOOL_IDS = new Set<BackendToolId>(
  REGISTRY_ENTRIES.filter(([, meta]) => Boolean(meta.hidden)).map(([toolId]) => toolId)
);

export const TOOLS_BY_WORKFLOW: Readonly<Record<WorkflowId, readonly BackendToolId[]>> = Object.freeze(
  Object.fromEntries(
    WORKFLOW_IDS.map((workflowId) => [
      workflowId,
      workflowId === "all"
        ? REGISTRY_ENTRIES.map(([toolId]) => toolId)
        : REGISTRY_ENTRIES
            .filter(([, meta]) => (meta.workflows || []).includes(workflowId))
            .map(([toolId]) => toolId),
    ])
  ) as Record<WorkflowId, readonly BackendToolId[]>
);

/** Helper: validate a string as a wired BackendToolId */
export function resolveBackendToolId(id: string): BackendToolId | null {
  return (WIRED_TOOL_IDS as Set<string>).has(id) ? (id as BackendToolId) : null;
}

/** Helper: get meta */
export function getBackendToolMeta(id: string): BackendToolMeta | null {
  const resolved = resolveBackendToolId(id);
  return resolved ? BACKEND_TOOL_REGISTRY[resolved] : null;
}

/** Helper: get workflow metadata */
export function getWorkflowMeta(id: string): WorkflowMeta | null {
  return (WORKFLOW_REGISTRY as Record<string, WorkflowMeta | undefined>)[id] ?? null;
}

// ----------------------------------------------------------------------------
// Dev-only sanity checks (warn, don’t throw)
// ----------------------------------------------------------------------------
if (process.env.NODE_ENV !== "production") {
  const seenPaths = new Map<string, BackendToolId>();

  for (const [toolId, meta] of REGISTRY_ENTRIES) {
    const prev = seenPaths.get(meta.path);
    if (prev && prev !== toolId) {
      // eslint-disable-next-line no-console
      console.warn(`[backendRegistry] Duplicate path "${meta.path}" for tool_ids: ${prev}, ${toolId}`);
    } else {
      seenPaths.set(meta.path, toolId);
    }
  }

  for (const [toolId, meta] of REGISTRY_ENTRIES) {
    for (const workflowId of meta.workflows || []) {
      if (!(workflowId in WORKFLOW_REGISTRY)) {
        // eslint-disable-next-line no-console
        console.warn(`[backendRegistry] Unknown workflow "${workflowId}" on tool_id "${toolId}"`);
      }
    }
  }
}