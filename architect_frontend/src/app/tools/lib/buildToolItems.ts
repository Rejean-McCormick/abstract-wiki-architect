// architect_frontend/src/app/tools/lib/buildToolItems.ts
import { INVENTORY } from "../inventory";
import {
  BACKEND_TOOL_REGISTRY,
  type BackendToolId,
  type BackendToolMeta,
  type Risk,
  type ToolParameter,
} from "../backendRegistry";
import { TOOL_DESCRIPTIONS, defaultDesc } from "../descriptions";
import {
  classify,
  cliFromPath,
  riskFromPath,
  statusFromPath,
  titleFromPath,
  type Status,
  type ToolKind,
} from "../classify";

/**
 * Workflow-oriented filter IDs for the Tools page.
 * Keep "all" as a UI-level convenience bucket.
 */
export type WorkflowId =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

const DEFAULT_WORKFLOW: WorkflowId = "recommended";
const WORKFLOW_IDS: readonly WorkflowId[] = [
  "recommended",
  "language_integration",
  "lexicon_work",
  "build_matrix",
  "qa_validation",
  "debug_recovery",
  "ai_assist",
  "all",
] as const;

const WORKFLOW_ID_SET = new Set<WorkflowId>(WORKFLOW_IDS);

/**
 * Canonical ToolItem type for the Tools UI.
 * Import this everywhere (ToolListPanel, ToolDetailsCard, page.tsx, etc.)
 * so you don't end up with drifting definitions in multiple files.
 */
export type ToolItem = {
  key: string;
  title: string;
  path: string; // repo-relative (normalized with forward slashes)
  category: string;
  group: string;
  kind: ToolKind;
  risk: Risk;
  status: Status;

  desc?: string;

  cli: string[];
  notes: string[];
  uiSteps: string[];

  wiredToolId?: BackendToolId;
  toolIdGuess: string;
  commandPreview?: string;

  hiddenInNormalMode?: boolean;
  parameterDocs?: ToolParameter[];

  // --- new: workflow-aware tool page metadata ---
  workflowTags: WorkflowId[];
  primaryWorkflow: Exclude<WorkflowId, "all">;
  recommendedOrder?: number;
};

type BuildToolItemsOpts = {
  /**
   * If true, items are returned sorted. Default true.
   * (If you sort elsewhere, you can disable to save work.)
   */
  sort?: boolean;
};

type WorkflowAwareMeta = BackendToolMeta &
  Partial<{
    hidden: boolean;
    workflowTags: readonly string[];
    primaryWorkflow: string;
    recommendedOrder: number;
  }>;

const collator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });

function normalizePath(p: string) {
  return (p || "").replace(/\\/g, "/").trim();
}

/** Stable, URL-safe-ish key used by docsHref() and selection logic */
export function toolKeyFromPath(path: string) {
  const p = normalizePath(path);
  return `file-${p.replace(/[^a-zA-Z0-9]+/g, "-")}`;
}

function basenameNoExt(path: string) {
  const p = normalizePath(path);
  const base = p.split("/").pop() || p;
  return base.replace(/\.[^.]+$/, "");
}

function toolIdGuessFromPath(path: string, wiredToolId?: BackendToolId) {
  return wiredToolId || basenameNoExt(path);
}

function mergeUniqueStrings(...lists: Array<readonly (string | undefined)[]>) {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const list of lists) {
    for (const s of list) {
      const v = (s || "").trim();
      if (!v) continue;
      if (seen.has(v)) continue;
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

function isRisk(x: unknown): x is Risk {
  return x === "safe" || x === "moderate" || x === "heavy";
}

function coerceRisk(...candidates: unknown[]): Risk {
  for (const c of candidates) {
    if (isRisk(c)) return c;
  }
  return "safe";
}

function cliEquivalents(path: string): string[] {
  const p = normalizePath(path);

  if (p === "manage.py") {
    return ["python manage.py start", "python manage.py build", "python manage.py doctor"];
  }
  if (p === "builder/orchestrator.py") {
    return ["python builder/orchestrator.py", "python manage.py build"];
  }
  return cliFromPath(p);
}

function asWorkflowId(v: unknown): WorkflowId | undefined {
  if (typeof v !== "string") return undefined;
  const normalized = v.trim().toLowerCase() as WorkflowId;
  return WORKFLOW_ID_SET.has(normalized) ? normalized : undefined;
}

function dedupeWorkflows(...lists: Array<readonly (WorkflowId | undefined)[]>) {
  const out: WorkflowId[] = [];
  const seen = new Set<WorkflowId>();

  for (const list of lists) {
    for (const item of list) {
      if (!item) continue;
      if (item === "all") continue; // all is synthetic
      if (seen.has(item)) continue;
      seen.add(item);
      out.push(item);
    }
  }

  return out;
}

function normalizeWorkflowArray(values?: readonly string[]): WorkflowId[] {
  if (!values?.length) return [];
  return dedupeWorkflows(values.map(asWorkflowId));
}

function workflowHintsFromTool(
  toolIdGuess: string,
  path: string,
  category: string,
  group: string
): { tags: Exclude<WorkflowId, "all">[]; primary: Exclude<WorkflowId, "all">; order?: number } {
  const id = (toolIdGuess || "").trim().toLowerCase();
  const p = normalizePath(path).toLowerCase();
  const c = (category || "").toLowerCase();
  const g = (group || "").toLowerCase();

  switch (id) {
    case "build_index":
      return {
        tags: ["recommended", "language_integration", "build_matrix"],
        primary: "recommended",
        order: 10,
      };

    case "lexicon_coverage":
      return {
        tags: ["language_integration", "lexicon_work", "qa_validation"],
        primary: "language_integration",
        order: 20,
      };

    case "compile_pgf":
      return {
        tags: ["recommended", "language_integration", "build_matrix"],
        primary: "recommended",
        order: 30,
      };

    case "language_health":
      return {
        tags: ["recommended", "language_integration", "qa_validation"],
        primary: "recommended",
        order: 40,
      };

    case "run_judge":
      return {
        tags: ["recommended", "language_integration", "qa_validation"],
        primary: "qa_validation",
        order: 50,
      };

    case "harvest_lexicon":
      return {
        tags: ["language_integration", "lexicon_work"],
        primary: "lexicon_work",
      };

    case "gap_filler":
      return {
        tags: ["language_integration", "lexicon_work"],
        primary: "lexicon_work",
      };

    case "bootstrap_tier1":
      return {
        tags: ["language_integration", "build_matrix", "debug_recovery"],
        primary: "language_integration",
      };

    case "diagnostic_audit":
      return {
        tags: ["debug_recovery", "qa_validation"],
        primary: "debug_recovery",
      };

    case "profiler":
      return {
        tags: ["qa_validation"],
        primary: "qa_validation",
      };

    case "ai_refiner":
    case "seed_lexicon":
      return {
        tags: ["ai_assist"],
        primary: "ai_assist",
      };

    case "rgl_scanner":
    case "lexicon_scanner":
    case "app_scanner":
    case "qa_scanner":
      return {
        tags: ["build_matrix", "debug_recovery"],
        primary: "build_matrix",
      };

    case "test_api_smoke":
    case "test_gf_dynamic":
    case "test_multilingual_generation":
    case "run_smoke_tests":
    case "universal_test_runner":
    case "generate_lexicon_regression_tests":
    case "batch_test_generator":
    case "test_suite_generator":
    case "ambiguity_detector":
      return {
        tags: ["qa_validation", "debug_recovery"],
        primary: "qa_validation",
      };

    default:
      break;
  }

  // Fallback heuristics for tools not explicitly mapped yet.
  if (c.includes("ai") || g.includes("ai") || p.includes("/ai_")) {
    return { tags: ["ai_assist"], primary: "ai_assist" };
  }

  if (
    c.includes("lexicon") ||
    c.includes("data") ||
    g.includes("lexicon") ||
    p.includes("/lexicon/") ||
    p.includes("harvest_lexicon") ||
    p.includes("gap_filler")
  ) {
    return { tags: ["lexicon_work"], primary: "lexicon_work" };
  }

  if (
    c.includes("build") ||
    g.includes("everything matrix") ||
    g.includes("gf build") ||
    p.includes("everything_matrix") ||
    p.includes("orchestrator")
  ) {
    return { tags: ["build_matrix"], primary: "build_matrix" };
  }

  if (
    c.includes("qa") ||
    c.includes("test") ||
    g.includes("qa") ||
    p.includes("/qa/") ||
    p.includes("/tests/")
  ) {
    return { tags: ["qa_validation"], primary: "qa_validation" };
  }

  if (
    c.includes("maintenance") ||
    c.includes("health") ||
    c.includes("diagnostic") ||
    g.includes("diagnostic") ||
    p.includes("diagnostic") ||
    p.includes("language_health")
  ) {
    return { tags: ["debug_recovery"], primary: "debug_recovery" };
  }

  return { tags: ["recommended"], primary: "recommended" };
}

function resolveWorkflowMeta(
  toolIdGuess: string,
  path: string,
  category: string,
  group: string,
  wiredMeta?: BackendToolMeta
): {
  workflowTags: Exclude<WorkflowId, "all">[];
  primaryWorkflow: Exclude<WorkflowId, "all">;
  recommendedOrder?: number;
} {
  const meta = wiredMeta as WorkflowAwareMeta | undefined;
  const inferred = workflowHintsFromTool(toolIdGuess, path, category, group);

  const fromRegistry = normalizeWorkflowArray(meta?.workflowTags) as Exclude<WorkflowId, "all">[];
  const primaryFromRegistry = asWorkflowId(meta?.primaryWorkflow);

  const workflowTags = dedupeWorkflows(fromRegistry, inferred.tags) as Exclude<WorkflowId, "all">[];
  const primaryWorkflow =
    (primaryFromRegistry && primaryFromRegistry !== "all"
      ? primaryFromRegistry
      : inferred.primary) || DEFAULT_WORKFLOW;

  if (!workflowTags.includes(primaryWorkflow)) {
    workflowTags.unshift(primaryWorkflow);
  }

  return {
    workflowTags,
    primaryWorkflow,
    recommendedOrder:
      typeof meta?.recommendedOrder === "number" ? meta.recommendedOrder : inferred.order,
  };
}

// -----------------------------------------------------------------------------
// Module-level caches (built once)
// -----------------------------------------------------------------------------
const TOOL_ID_BY_PATH: Record<string, BackendToolId> = (() => {
  const out: Record<string, BackendToolId> = {};
  const entries = Object.entries(BACKEND_TOOL_REGISTRY) as [BackendToolId, BackendToolMeta][];

  for (const [toolId, meta] of entries) {
    const p = normalizePath(meta.path);
    if (!out[p]) out[p] = toolId;
  }
  return out;
})();

/**
 * Inventory path sources in the same order as your original page.tsx.
 * Keeping order stable helps with debugging and predictable outputs.
 */
function collectInventoryPaths(): string[] {
  const seen = new Set<string>();
  const all: string[] = [];

  const addMany = (arr?: readonly string[] | string[]) => {
    if (!arr) return;
    for (let i = 0; i < arr.length; i++) {
      const raw = arr[i];
      if (!raw) continue;
      const p = normalizePath(raw);
      if (!p) continue;
      if (seen.has(p)) continue;
      seen.add(p);
      all.push(p);
    }
  };

  addMany(INVENTORY.root_entrypoints as readonly string[]);
  addMany(INVENTORY.gf as readonly string[]);
  addMany(INVENTORY.tools?.root || []);
  addMany(INVENTORY.tools?.everything_matrix || []);
  addMany(INVENTORY.tools?.qa || []);
  addMany(INVENTORY.tools?.debug || []);
  addMany(INVENTORY.tools?.health || []);
  addMany(INVENTORY.tools?.lexicon || []);

  addMany(INVENTORY.scripts?.root || []);
  addMany(INVENTORY.scripts?.lexicon || []);
  addMany(INVENTORY.utils as readonly string[]);
  addMany(INVENTORY.ai_services as readonly string[]);
  addMany(INVENTORY.nlg as readonly string[]);
  addMany(INVENTORY.prototypes as readonly string[]);
  addMany(INVENTORY.tests?.root || []);
  addMany(INVENTORY.tests?.http_api_legacy || []);
  addMany(INVENTORY.tests?.adapters_core_integration || []);

  return all;
}

/**
 * Build ToolItem[] from the inventory snapshot plus backend wired registry.
 * Pure and cheap enough to use in useMemo(() => buildToolItems(), []).
 */
export function buildToolItems(opts: BuildToolItemsOpts = {}): ToolItem[] {
  const shouldSort = opts.sort !== false;

  const rootEntrypoints = ((INVENTORY.root_entrypoints as readonly string[]) ?? []).map(normalizePath);

  // 1) Items from inventory snapshot
  const allPaths = collectInventoryPaths();
  const presentPaths = new Set(allPaths);

  const out: ToolItem[] = [];

  for (let i = 0; i < allPaths.length; i++) {
    const path = allPaths[i];

    const cls = classify(rootEntrypoints, path);
    if (cls.excludeFromUI) continue;

    const wiredToolId = TOOL_ID_BY_PATH[path];
    const wiredMeta: BackendToolMeta | undefined = wiredToolId
      ? BACKEND_TOOL_REGISTRY[wiredToolId]
      : undefined;
    const meta = wiredMeta as WorkflowAwareMeta | undefined;
    const wired = Boolean(wiredToolId);

    const status = (cls.statusOverride ?? statusFromPath(path)) as Status;
    const risk = coerceRisk(cls.riskOverride, wiredMeta?.risk, riskFromPath(path));

    const desc = TOOL_DESCRIPTIONS[path] ?? defaultDesc(path);
    const toolIdGuess = toolIdGuessFromPath(path, wiredToolId);
    const commandPreview = wiredMeta?.cmd?.join(" ").trim() || undefined;

    const resolvedCategory = wiredMeta?.category ?? cls.category;
    const resolvedGroup = wiredMeta?.group ?? cls.group;

    const workflowMeta = resolveWorkflowMeta(
      toolIdGuess,
      path,
      resolvedCategory,
      resolvedGroup,
      wiredMeta
    );

    const cli = wired
      ? mergeUniqueStrings([commandPreview], cliEquivalents(path))
      : cliEquivalents(path);

    const notes = mergeUniqueStrings(
      cls.notes ?? [],
      [
        wired
          ? "Wired: Run is enabled (backend allowlist)."
          : "Not wired: shown for reference only (not in backend allowlist).",
      ],
      meta?.hidden || cls.hideByDefault
        ? ["Hidden in normal mode: shown via Power user or workflow-specific views."]
        : [],
      status === "legacy" ? ["Legacy/compat: may require endpoint or pipeline updates."] : [],
      status === "experimental" ? ["Experimental: not guaranteed stable."] : [],
      status === "internal" ? ["Internal module: usually not executed directly."] : []
    );

    out.push({
      key: toolKeyFromPath(path),
      title: wiredMeta?.title ?? titleFromPath(path),
      path,
      category: resolvedCategory,
      group: resolvedGroup,
      kind: cls.kind,
      risk,
      status,
      desc,
      cli,
      notes,
      uiSteps: cls.uiSteps,
      wiredToolId,
      toolIdGuess,
      commandPreview,
      hiddenInNormalMode: Boolean(meta?.hidden || cls.hideByDefault),
      parameterDocs: wiredMeta?.parameterDocs || [],
      workflowTags: workflowMeta.workflowTags,
      primaryWorkflow: workflowMeta.primaryWorkflow,
      recommendedOrder: workflowMeta.recommendedOrder,
    });
  }

  // 2) Backend-wired tools missing from inventory snapshot
  const backendEntries = Object.entries(BACKEND_TOOL_REGISTRY) as [BackendToolId, BackendToolMeta][];

  for (const [toolId, metaBase] of backendEntries) {
    const path = normalizePath(metaBase.path);
    if (presentPaths.has(path)) continue;

    const cls = classify(rootEntrypoints, path);
    if (cls.excludeFromUI) continue;

    const meta = metaBase as WorkflowAwareMeta;

    const desc = TOOL_DESCRIPTIONS[path] ?? `${metaBase.title} (backend-wired tool).`;
    const status = (cls.statusOverride ?? statusFromPath(path)) as Status;
    const risk = coerceRisk(metaBase.risk, cls.riskOverride, riskFromPath(path));
    const commandPreview = metaBase.cmd.join(" ").trim();

    const resolvedCategory = metaBase.category ?? cls.category;
    const resolvedGroup = metaBase.group ?? cls.group;

    const workflowMeta = resolveWorkflowMeta(
      toolId,
      path,
      resolvedCategory,
      resolvedGroup,
      metaBase
    );

    const notes = mergeUniqueStrings(
      cls.notes ?? [],
      [
        "Wired: Run is enabled (backend allowlist).",
        "This tool is wired but missing from the current inventory snapshot.",
      ],
      meta.hidden || cls.hideByDefault
        ? ["Hidden in normal mode: shown via Power user or workflow-specific views."]
        : [],
      status === "legacy" ? ["Legacy/compat: may require endpoint or pipeline updates."] : [],
      status === "experimental" ? ["Experimental: not guaranteed stable."] : [],
      status === "internal" ? ["Internal module: usually not executed directly."] : []
    );

    out.push({
      key: `wired-${toolId}`,
      title: metaBase.title,
      path,
      category: resolvedCategory,
      group: resolvedGroup,
      kind: cls.kind,
      risk,
      status,
      desc,
      cli: mergeUniqueStrings([commandPreview], cliEquivalents(path)),
      notes,
      uiSteps:
        cls.uiSteps?.length
          ? cls.uiSteps
          : ["Select the tool.", "Optionally add args.", "Click Run and review output."],
      wiredToolId: toolId,
      toolIdGuess: toolId,
      commandPreview,
      hiddenInNormalMode: Boolean(meta.hidden || cls.hideByDefault),
      parameterDocs: metaBase.parameterDocs || [],
      workflowTags: workflowMeta.workflowTags,
      primaryWorkflow: workflowMeta.primaryWorkflow,
      recommendedOrder: workflowMeta.recommendedOrder,
    });
  }

  if (shouldSort) {
    out.sort((a, b) => {
      const aw = a.recommendedOrder ?? Number.MAX_SAFE_INTEGER;
      const bw = b.recommendedOrder ?? Number.MAX_SAFE_INTEGER;
      if (aw !== bw) return aw - bw;

      const c1 = collator.compare(a.category, b.category);
      if (c1) return c1;
      const c2 = collator.compare(a.group, b.group);
      if (c2) return c2;
      return collator.compare(a.title, b.title);
    });
  }

  return out;
}