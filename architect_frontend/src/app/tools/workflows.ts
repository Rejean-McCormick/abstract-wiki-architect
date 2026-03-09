// architect_frontend/src/app/tools/workflows.ts
// Workflow-oriented tool bundles for the Tools dashboard.
// Purpose:
// - drive the workflow dropdown (intent selector)
// - provide the recommended workflow card text
// - map each workflow to the most relevant wired tool IDs

import type { BackendToolId } from "./backendRegistry";

export type WorkflowId =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

export type WorkflowStep = {
  title: string;
  toolId?: BackendToolId;
  args?: string;
  note?: string;
};

export type WorkflowDefinition = {
  id: WorkflowId;
  label: string;
  description: string;
  toolIds: readonly BackendToolId[];
  powerUserOnlyToolIds?: readonly BackendToolId[];
  steps: readonly WorkflowStep[];
  emptyStateHint?: string;
};

const uniq = <T extends string>(items: readonly T[]): T[] => {
  const seen = new Set<T>();
  const out: T[] = [];
  for (const item of items) {
    if (seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  return out;
};

const ALL_KNOWN_TOOL_IDS = uniq([
  // Core orchestration / maintenance
  "build_index",
  "compile_pgf",
  "language_health",
  "diagnostic_audit",
  "profiler",
  "cleanup_root",
  "visualize_ast",

  // Everything Matrix scanners
  "app_scanner",
  "lexicon_scanner",
  "qa_scanner",
  "rgl_scanner",

  // Language integration / lexicon
  "bootstrap_tier1",
  "gap_filler",
  "harvest_lexicon",
  "build_lexicon_wikidata",
  "refresh_index",
  "migrate_schema",
  "dump_stats",
  "lexicon_coverage",

  // QA / testing
  "run_smoke_tests",
  "run_judge",
  "test_api_smoke",
  "test_gf_dynamic",
  "test_multilingual_generation",
  "ambiguity_detector",
  "eval_bios",
  "universal_test_runner",
  "batch_test_generator",
  "test_suite_generator",
  "generate_lexicon_regression_tests",

  // AI
  "seed_lexicon",
  "ai_refiner",
] as const satisfies readonly BackendToolId[]);

const CORE_RECOMMENDED = [
  "build_index",
  "compile_pgf",
  "language_health",
  "run_judge",
] as const satisfies readonly BackendToolId[];

const WORKFLOWS: Record<WorkflowId, WorkflowDefinition> = {
  recommended: {
    id: "recommended",
    label: "Recommended",
    description:
      "Shortest safe path for normal work: refresh the matrix, build, validate, then judge.",
    toolIds: CORE_RECOMMENDED,
    steps: [
      {
        title: "Refresh the Everything Matrix",
        toolId: "build_index",
        args: "--regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile the PGF",
        toolId: "compile_pgf",
        args: "--verbose",
      },
      {
        title: "Validate compile + runtime",
        toolId: "language_health",
        args: "--mode both --json --verbose",
      },
      {
        title: "Generate one real sentence",
        note: "Use the dev smoke test or call /api/v1/generate/<lang>.",
      },
      {
        title: "Run judge / regression checks",
        toolId: "run_judge",
        args: "--verbose",
      },
    ],
  },

  language_integration: {
    id: "language_integration",
    label: "Language Integration",
    description:
      "Add or repair one language: discover it, fix data, compile, validate, and generate real output.",
    toolIds: [
      "build_index",
      "lexicon_coverage",
      "compile_pgf",
      "language_health",
      "run_judge",
      "harvest_lexicon",
      "gap_filler",
      "bootstrap_tier1",
    ],
    steps: [
      {
        title: "Add or change language files",
        note: "Grammar, config, and lexicon files go in place first.",
      },
      {
        title: "Refresh the Everything Matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Validate the lexicon",
        toolId: "lexicon_coverage",
        args: "--lang <lang> --include-files",
      },
      {
        title: "Harvest or fill lexical gaps if needed",
        toolId: "harvest_lexicon",
        args: "wordnet --lang <lang> ...",
        note: "Use gap_filler when coverage is thin compared with a pivot language.",
      },
      {
        title: "Bootstrap Tier 1 scaffolding if needed",
        toolId: "bootstrap_tier1",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Compile the PGF",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Validate compile + runtime",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
      {
        title: "Generate one real sentence",
        note: "Use the dev smoke test or call /api/v1/generate/<lang>.",
      },
      {
        title: "Run judge",
        toolId: "run_judge",
        args: "--langs <lang> --verbose",
      },
    ],
  },

  lexicon_work: {
    id: "lexicon_work",
    label: "Lexicon Work",
    description:
      "Vocabulary and shard work: import, fill gaps, validate, and rebuild fast indices.",
    toolIds: [
      "harvest_lexicon",
      "gap_filler",
      "lexicon_coverage",
      "refresh_index",
      "migrate_schema",
      "build_lexicon_wikidata",
      "dump_stats",
    ],
    powerUserOnlyToolIds: ["seed_lexicon"],
    steps: [
      {
        title: "Harvest / import lexical data",
        toolId: "harvest_lexicon",
      },
      {
        title: "Fill gaps against a pivot language",
        toolId: "gap_filler",
        args: "--langs <lang> --pivot en --verbose",
      },
      {
        title: "Validate coverage and schema shape",
        toolId: "lexicon_coverage",
        args: "--lang <lang> --include-files",
      },
      {
        title: "Refresh fast lexicon index",
        toolId: "refresh_index",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Re-run language health",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
    ],
  },

  build_matrix: {
    id: "build_matrix",
    label: "Build & Matrix",
    description:
      "Inventory/build-state work: rebuild the Everything Matrix, then compile the grammar binary.",
    toolIds: ["build_index", "compile_pgf"],
    powerUserOnlyToolIds: [
      "app_scanner",
      "lexicon_scanner",
      "qa_scanner",
      "rgl_scanner",
      "bootstrap_tier1",
    ],
    steps: [
      {
        title: "Refresh the Everything Matrix",
        toolId: "build_index",
        args: "--regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile the PGF",
        toolId: "compile_pgf",
        args: "--verbose",
      },
      {
        title: "Validate runtime after build",
        toolId: "language_health",
        args: "--mode both --json --verbose",
      },
    ],
    emptyStateHint: "Use scanners only when the matrix looks wrong.",
  },

  qa_validation: {
    id: "qa_validation",
    label: "QA & Validation",
    description:
      "Answer the three main questions: does it work, is it correct, and is it fast enough?",
    toolIds: ["language_health", "run_judge", "profiler"],
    powerUserOnlyToolIds: [
      "run_smoke_tests",
      "test_api_smoke",
      "test_gf_dynamic",
      "test_multilingual_generation",
      "ambiguity_detector",
      "eval_bios",
      "universal_test_runner",
      "batch_test_generator",
      "test_suite_generator",
      "generate_lexicon_regression_tests",
    ],
    steps: [
      {
        title: "Run health validation",
        toolId: "language_health",
        args: "--mode both --json --verbose",
      },
      {
        title: "Generate one real sentence",
        note: "Use the dev smoke test or call /api/v1/generate/<lang>.",
      },
      {
        title: "Run judge / regression",
        toolId: "run_judge",
        args: "--verbose",
      },
      {
        title: "Measure performance",
        toolId: "profiler",
        args: "--verbose",
      },
    ],
  },

  debug_recovery: {
    id: "debug_recovery",
    label: "Debug & Recovery",
    description:
      "Use when something is weird: stale artifacts, broken matrix signals, or failing low-level tests.",
    toolIds: ["diagnostic_audit"],
    powerUserOnlyToolIds: [
      "app_scanner",
      "lexicon_scanner",
      "qa_scanner",
      "rgl_scanner",
      "test_api_smoke",
      "test_gf_dynamic",
      "test_multilingual_generation",
      "cleanup_root",
      "visualize_ast",
    ],
    steps: [
      {
        title: "Run diagnostic audit",
        toolId: "diagnostic_audit",
        args: "--json --verbose",
      },
      {
        title: "Run a targeted scanner or low-level test",
        note: "Choose the scanner or pytest that matches the failure mode.",
      },
      {
        title: "Fix the issue, then rebuild",
        toolId: "build_index",
        args: "--regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile again",
        toolId: "compile_pgf",
        args: "--verbose",
      },
      {
        title: "Re-run language health",
        toolId: "language_health",
        args: "--mode both --json --verbose",
      },
    ],
  },

  ai_assist: {
    id: "ai_assist",
    label: "AI Assist",
    description:
      "AI helpers for recovery or acceleration after deterministic tools reveal a real gap.",
    toolIds: [],
    powerUserOnlyToolIds: ["ai_refiner", "seed_lexicon"],
    steps: [
      {
        title: "Use deterministic tools first",
        note: "Start with Build Index, Compile PGF, Language Health, or Lexicon Coverage.",
      },
      {
        title: "Run the AI helper",
        toolId: "ai_refiner",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Refresh the matrix",
        toolId: "build_index",
        args: "--langs <lang> --regen-rgl --regen-lex --regen-app --regen-qa --verbose",
      },
      {
        title: "Compile and validate again",
        toolId: "compile_pgf",
        args: "--langs <lang> --verbose",
      },
      {
        title: "Run health and judge",
        toolId: "language_health",
        args: "--mode both --langs <lang> --json --verbose",
      },
    ],
    emptyStateHint: "AI tools are hidden by default and should not lead the normal workflow.",
  },

  all: {
    id: "all",
    label: "All",
    description: "Show every known tool bundle; rely on Power user to reveal hidden and debug tools.",
    toolIds: ALL_KNOWN_TOOL_IDS,
    steps: [
      {
        title: "Pick a more specific workflow when possible",
        note: "Recommended and Language Integration are the best default starting points.",
      },
    ],
  },
};

export const WORKFLOW_ORDER = [
  "recommended",
  "language_integration",
  "lexicon_work",
  "build_matrix",
  "qa_validation",
  "debug_recovery",
  "ai_assist",
  "all",
] as const satisfies readonly WorkflowId[];

export const DEFAULT_WORKFLOW_ID: WorkflowId = "recommended";

export const WORKFLOW_OPTIONS = WORKFLOW_ORDER.map((id) => ({
  id,
  label: WORKFLOWS[id].label,
})) as ReadonlyArray<{ id: WorkflowId; label: string }>;

export function getWorkflowDefinition(workflowId: WorkflowId): WorkflowDefinition {
  return WORKFLOWS[workflowId];
}

export function getWorkflowToolIds(
  workflowId: WorkflowId,
  opts: { powerUser?: boolean } = {}
): BackendToolId[] {
  const def = WORKFLOWS[workflowId];
  const extra = opts.powerUser ? def.powerUserOnlyToolIds ?? [] : [];
  return uniq([...def.toolIds, ...extra]);
}

export function workflowIncludesTool(
  workflowId: WorkflowId,
  toolId: string | null | undefined,
  opts: { powerUser?: boolean } = {}
): boolean {
  if (!toolId) return false;
  const ids = getWorkflowToolIds(workflowId, opts);
  return ids.includes(toolId as BackendToolId);
}

export function getRecommendedWorkflowSteps(workflowId: WorkflowId): readonly WorkflowStep[] {
  return WORKFLOWS[workflowId].steps;
}

export function getWorkflowEmptyStateHint(workflowId: WorkflowId): string | undefined {
  return WORKFLOWS[workflowId].emptyStateHint;
}

export const WORKFLOWS_BY_ID = WORKFLOWS;
