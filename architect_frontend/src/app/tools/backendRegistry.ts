// architect_frontend/src/app/tools/backendRegistry.ts

export type Risk = "safe" | "moderate" | "heavy";

export type BackendToolMeta = {
  title: string;
  path: string;
  cmd: readonly string[];
  category: string;
  group: string;
  risk: Risk;

  /**
   * UI / operator intent
   * - hidden: keep wired, but hide from normal UI (revealed in Debug/Power user)
   * - legacyAlias: old tool_id kept for backward compat / power users
   * - requiresAiEnabled: backend will 403 unless ARCHITECT_ENABLE_AI_TOOLS=1
   */
  hidden?: boolean;
  legacyAlias?: boolean;
  requiresAiEnabled?: boolean;
};

/**
 * Backend-wired tools. Must match backend TOOL_REGISTRY allowlist tool_id values.
 *
 * Notes
 * - Some tool_ids are legacy aliases (audit_languages, check_all_languages, test_runner)
 *   that now point to canonical scripts on the backend; we keep them here only if we
 *   want them selectable in the UI.
 * - `path` is used only for UI mapping/diagnostics; execution should happen via tool_id
 *   against the backend /tools/run endpoint.
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
  },

  // Legacy aliases -> language_health.py (keep, but hide by default to reduce noise)
  audit_languages: {
    title: "Audit Languages (Legacy Alias)",
    path: "tools/language_health.py",
    cmd: ["python", "tools/language_health.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    legacyAlias: true,
    hidden: true,
  },
  check_all_languages: {
    title: "Check All Languages (Legacy Alias)",
    path: "tools/language_health.py",
    cmd: ["python", "tools/language_health.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
    legacyAlias: true,
    hidden: true,
  },

  diagnostic_audit: {
    title: "Diagnostic Audit",
    path: "tools/diagnostic_audit.py",
    cmd: ["python", "tools/diagnostic_audit.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
  },
  cleanup_root: {
    title: "Cleanup Root",
    path: "tools/cleanup_root.py",
    cmd: ["python", "tools/cleanup_root.py"],
    category: "Diagnostics & Maintenance",
    group: "Health & Cleanup",
    risk: "safe",
  },

  // --- BUILD SYSTEM ---
  build_index: {
    title: "Rebuild Everything Matrix",
    path: "tools/everything_matrix/build_index.py",
    cmd: ["python", "tools/everything_matrix/build_index.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "moderate",
  },
  app_scanner: {
    title: "App Scanner",
    path: "tools/everything_matrix/app_scanner.py",
    cmd: ["python", "tools/everything_matrix/app_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
  },
  lexicon_scanner: {
    title: "Lexicon Scanner",
    path: "tools/everything_matrix/lexicon_scanner.py",
    cmd: ["python", "tools/everything_matrix/lexicon_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
  },
  qa_scanner: {
    title: "QA Scanner",
    path: "tools/everything_matrix/qa_scanner.py",
    cmd: ["python", "tools/everything_matrix/qa_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
  },
  rgl_scanner: {
    title: "RGL Scanner",
    path: "tools/everything_matrix/rgl_scanner.py",
    cmd: ["python", "tools/everything_matrix/rgl_scanner.py"],
    category: "Build System",
    group: "Everything Matrix",
    risk: "safe",
  },

  compile_pgf: {
    title: "Compile PGF (Build Orchestrator)",
    path: "gf/build_orchestrator.py",
    cmd: ["python", "gf/build_orchestrator.py"],
    category: "Build System",
    group: "GF Build",
    risk: "heavy",
  },
  bootstrap_tier1: {
    title: "Bootstrap Tier 1",
    path: "tools/bootstrap_tier1.py",
    cmd: ["python", "tools/bootstrap_tier1.py"],
    category: "Build System",
    group: "Tier Bootstrapping",
    risk: "moderate",
  },

  // --- LEXICON & DATA ---
  harvest_lexicon: {
    title: "Harvest Lexicon",
    path: "tools/harvest_lexicon.py",
    cmd: ["python", "tools/harvest_lexicon.py"],
    category: "Lexicon & Data",
    group: "Mining & Harvesting",
    risk: "moderate",
  },
  build_lexicon_wikidata: {
    title: "Build Lexicon from Wikidata",
    path: "tools/build_lexicon_from_wikidata.py",
    cmd: ["python", "tools/build_lexicon_from_wikidata.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "moderate",
  },
  refresh_index: {
    title: "Refresh Lexicon Index",
    path: "utils/refresh_lexicon_index.py",
    cmd: ["python", "utils/refresh_lexicon_index.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "safe",
  },
  migrate_schema: {
    title: "Migrate Lexicon Schema",
    path: "utils/migrate_lexicon_schema.py",
    cmd: ["python", "utils/migrate_lexicon_schema.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "moderate",
  },
  dump_stats: {
    title: "Dump Lexicon Stats",
    path: "utils/dump_lexicon_stats.py",
    cmd: ["python", "utils/dump_lexicon_stats.py"],
    category: "Lexicon & Data",
    group: "Schema & Index",
    risk: "safe",
  },

  // --- QA & TESTING ---
  run_smoke_tests: {
    title: "Run Smoke Tests (Lexicon)",
    path: "tests/test_lexicon_smoke.py",
    cmd: ["python", "-m", "pytest", "tests/test_lexicon_smoke.py"],
    category: "QA & Testing",
    group: "Pytest • Smoke",
    risk: "safe",
  },
  run_judge: {
    title: "Run Judge (Integration)",
    path: "tests/integration/test_quality.py",
    cmd: ["python", "-m", "pytest", "tests/integration/test_quality.py"],
    category: "QA & Testing",
    group: "Pytest • Judge",
    risk: "heavy",
  },
  eval_bios: {
    title: "Eval Biographies",
    path: "tools/qa/eval_bios.py",
    cmd: ["python", "tools/qa/eval_bios.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
  },
  lexicon_coverage: {
    title: "Lexicon Coverage Report",
    path: "tools/qa/lexicon_coverage_report.py",
    cmd: ["python", "tools/qa/lexicon_coverage_report.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
  },

  // Legacy alias -> universal_test_runner.py (backend). Keep, but hide by default.
  test_runner: {
    title: "QA Test Runner (Legacy Alias)",
    path: "tools/qa/universal_test_runner.py",
    cmd: ["python", "tools/qa/universal_test_runner.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
    legacyAlias: true,
    hidden: true,
  },

  universal_test_runner: {
    title: "Universal Test Runner",
    path: "tools/qa/universal_test_runner.py",
    cmd: ["python", "tools/qa/universal_test_runner.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
  },
  batch_test_generator: {
    title: "Batch Test Generator",
    path: "tools/qa/batch_test_generator.py",
    cmd: ["python", "tools/qa/batch_test_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "moderate",
  },
  test_suite_generator: {
    title: "Test Suite Generator",
    path: "tools/qa/test_suite_generator.py",
    cmd: ["python", "tools/qa/test_suite_generator.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "safe",
  },
  generate_lexicon_regression_tests: {
    title: "Generate Lexicon Regression Tests",
    path: "tools/qa/generate_lexicon_regression_tests.py",
    cmd: ["python", "tools/qa/generate_lexicon_regression_tests.py"],
    category: "QA & Testing",
    group: "QA Tools",
    risk: "heavy",
  },

  // --- AI TOOLS & SERVICES ---
  seed_lexicon: {
    title: "Seed Lexicon (AI)",
    path: "utils/seed_lexicon_ai.py",
    cmd: ["python", "utils/seed_lexicon_ai.py"],
    category: "AI Tools & Services",
    group: "AI Utilities",
    risk: "heavy",
    requiresAiEnabled: true,
    hidden: true,
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
  },

  // --- TESTS (extra inventory) ---
  test_api_smoke: {
    title: "Test API Smoke",
    path: "tests/test_api_smoke.py",
    cmd: ["python", "-m", "pytest", "tests/test_api_smoke.py"],
    category: "QA & Testing",
    group: "Pytest • API",
    risk: "safe",
  },
  test_gf_dynamic: {
    title: "Test GF Dynamic",
    path: "tests/test_gf_dynamic.py",
    cmd: ["python", "-m", "pytest", "tests/test_gf_dynamic.py"],
    category: "QA & Testing",
    group: "Pytest • GF",
    risk: "safe",
  },
  test_multilingual_generation: {
    title: "Test Multilingual Generation",
    path: "tests/test_multilingual_generation.py",
    cmd: ["python", "-m", "pytest", "tests/test_multilingual_generation.py"],
    category: "QA & Testing",
    group: "Pytest • Generation",
    risk: "safe",
  },
} as const;

export type BackendToolId = keyof typeof BACKEND_TOOL_REGISTRY;

export const WIRED_TOOL_IDS = new Set<string>(Object.keys(BACKEND_TOOL_REGISTRY));

export const TOOL_ID_BY_PATH: Record<string, string> = Object.fromEntries(
  Object.entries(BACKEND_TOOL_REGISTRY).map(([toolId, meta]) => [meta.path, toolId])
);

/** Convenience: tool_ids that are hidden unless Debug/Power user is enabled */
export const POWER_USER_TOOL_IDS = new Set<string>(
  Object.entries(BACKEND_TOOL_REGISTRY)
    .filter(([, meta]) => Boolean(meta.hidden))
    .map(([toolId]) => toolId)
);
