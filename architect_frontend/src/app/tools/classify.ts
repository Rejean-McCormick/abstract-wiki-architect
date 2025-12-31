// architect_frontend/src/app/tools/classify.ts
import { BACKEND_TOOL_REGISTRY, type BackendToolId, type Risk } from "./backendRegistry";

export type Status = "active" | "legacy" | "experimental" | "internal";
export type Visibility = "default" | "debug";

export type ToolKind =
  | "entrypoint"
  | "tool"
  | "script"
  | "test"
  | "utility"
  | "agent"
  | "prototype";

/**
 * Files we never want to show in the Tools UI (even in debug mode).
 * These are not meaningful “runnable tools” and create noise/confusion.
 */
export const shouldExcludeFromToolsUI = (path: string): boolean => {
  const p = path.toLowerCase();

  // Python package markers / pure module markers
  if (p.endsWith("/__init__.py") || p.endsWith("__init__.py")) return true;

  // Generated outputs are not “tools” (they’re build artifacts)
  if (p.startsWith("generated/")) return true;

  // If you later add docs/config to the inventory, keep them out of Tools UI:
  if (p.startsWith("docs/")) return true;
  if (p.startsWith("config/")) return true;

  return false;
};

/**
 * Some utilities are “real tools” (runnable CLIs) even if they live under utils/.
 * Keep these visible by default.
 */
export const isRunnableUtility = (path: string): boolean => {
  const p = path.toLowerCase();
  if (!p.startsWith("utils/")) return false;

  // Allowlist known runnable utils (CLIs)
  return (
    p.includes("refresh_lexicon_index") ||
    p.includes("migrate_lexicon_schema") ||
    p.includes("dump_lexicon_stats") ||
    p.includes("seed_lexicon_ai") ||
    p.includes("build_lexicon_from_wikidata")
  );
};

/**
 * Central place to decide whether a backend-wired tool should be hidden
 * from normal users (revealed when Debug/Power user is enabled).
 *
 * Source of truth: backendRegistry.hidden flag.
 */
export const isPowerUserToolId = (toolId?: string): boolean => {
  if (!toolId) return false;
  const meta = (BACKEND_TOOL_REGISTRY as any)[toolId] as
    | (typeof BACKEND_TOOL_REGISTRY)[BackendToolId]
    | undefined;
  return Boolean(meta?.hidden);
};

export const riskFromPath = (path: string): Risk => {
  const p = path.toLowerCase();

  // HEAVY: can be slow/CPU-heavy/expensive (AI) or affects large parts of repo
  if (
    p.includes("gf/build_orchestrator") ||
    p.includes("build_orchestrator") ||
    p.includes("compile_pgf") ||
    p.includes("seed_lexicon_ai") ||
    p.includes("seed_lexicon") ||
    p.includes("ai_refiner")
  ) {
    return "heavy";
  }

  // MODERATE: may write many files / touch schema / do long-ish scans
  if (
    p.includes("migrate") ||
    p.includes("wikidata") ||
    p.includes("bootstrap_tier1") ||
    p.includes("universal_test_runner") ||
    p.includes("batch_test_generator") ||
    p.includes("build_index") ||
    p.includes("harvest_lexicon") ||
    p.includes("test_runner")
  ) {
    return "moderate";
  }

  return "safe";
};

export const statusFromPath = (path: string): Status => {
  const p = path.toLowerCase();
  if (p.startsWith("prototypes/")) return "experimental";
  if (p.startsWith("tests/http_api/")) return "legacy";
  if (p.startsWith("scripts/lexicon/")) return "legacy";
  if (p.endsWith("/__init__.py") || p.endsWith("__init__.py")) return "internal";
  if (p.includes("test_api_generation.py")) return "legacy";
  return "active";
};

export const titleFromPath = (path: string) => {
  const base = path.split("/").pop() || path;
  const stem = base.replace(/\.[^.]+$/, "");
  return stem.replace(/[_-]+/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
};

export const cliFromPath = (path: string) => {
  const ext = (path.split(".").pop() || "").toLowerCase();
  if (path.startsWith("tests/")) return [`python -m pytest ${path}`];
  if (ext === "ps1") return [`powershell -ExecutionPolicy Bypass -File ${path}`];
  if (ext === "bat" || ext === "cmd") return [path];
  if (ext === "sh") return [`bash ${path}`];
  if (ext === "py") return [`python ${path}`];
  return [path];
};

/**
 * Visibility policy:
 * - "default": stuff we expect normal users to browse/run regularly
 * - "debug": noisy/legacy/experimental/internal things that power users may want
 */
export const visibilityFromPath = (
  inventoryRootEntrypoints: readonly string[],
  path: string
): Visibility => {
  const p = path.toLowerCase();

  // Root entrypoints are always “default”
  if (inventoryRootEntrypoints.includes(path)) return "default";

  // Primary “tool surfaces”
  if (p.startsWith("tools/")) return "default";
  if (p.startsWith("gf/")) return "default";

  // Runnable CLIs under utils/ are useful in default mode
  if (isRunnableUtility(path)) return "default";

  // Everything else is debug-only (noise / reference / internal modules)
  if (p.startsWith("tests/")) return "debug";
  if (p.startsWith("scripts/")) return "debug";
  if (p.startsWith("prototypes/")) return "debug";
  if (p.startsWith("ai_services/")) return "debug";
  if (p.startsWith("nlg/")) return "debug";
  if (p.startsWith("utils/")) return "debug";

  return "debug";
};

export const classify = (
  inventoryRootEntrypoints: readonly string[],
  path: string
): {
  category: string;
  group: string;
  kind: ToolKind;
  statusOverride?: Status;
  riskOverride?: Risk;
  visibility: Visibility;
  hideByDefault: boolean;
  excludeFromUI: boolean;
  notes: string[];
  uiSteps: string[];
} => {
  const p = path.toLowerCase();
  const status = statusFromPath(path);
  const visibility = visibilityFromPath(inventoryRootEntrypoints, path);
  const excludeFromUI = shouldExcludeFromToolsUI(path);

  // If it’s excluded, still return a coherent classification (caller can filter it out).
  if (excludeFromUI) {
    return {
      category: "Internal",
      group: "Hidden",
      kind: "utility",
      statusOverride: "internal",
      visibility: "debug",
      hideByDefault: true,
      excludeFromUI: true,
      notes: ["Hidden from Tools UI (non-actionable file / artifact)."],
      uiSteps: ["(Hidden)"],
    };
  }

  if (inventoryRootEntrypoints.includes(path)) {
    return {
      category: "Launch & Entry Points",
      group: "Root",
      kind: "entrypoint",
      visibility,
      hideByDefault: visibility === "debug",
      excludeFromUI,
      notes: ["Prefer these entrypoints over ad-hoc runs when possible."],
      uiSteps: [
        "Select the entrypoint.",
        "Open in Repo for parameters.",
        "Run only if backend wiring exists.",
      ],
    };
  }

  if (path.startsWith("gf/")) {
    return {
      category: "Build System",
      group: "GF Build",
      kind: "tool",
      riskOverride: "heavy",
      visibility,
      hideByDefault: visibility === "debug",
      excludeFromUI,
      notes: [
        "Heaviest operation (CPU/time). Avoid parallel heavy runs.",
        "If build fails, run Diagnostics & Maintenance next, then retry.",
      ],
      uiSteps: ["Click Run and monitor console output.", "On failure, copy logs and inspect the tool."],
    };
  }

  if (path.startsWith("tools/everything_matrix/")) {
    return {
      category: "Build System",
      group: "Everything Matrix",
      kind: "tool",
      visibility,
      hideByDefault: visibility === "debug",
      excludeFromUI,
      notes: ["Scanners used to compute everything_matrix.json and maturity/QA signals."],
      uiSteps: ["Prefer running build_index unless debugging a specific scanner."],
    };
  }

  if (path.startsWith("tools/qa/")) {
    return {
      category: "QA & Testing",
      group: "QA Tools",
      kind: "tool",
      visibility,
      hideByDefault: visibility === "debug",
      excludeFromUI,
      notes: ["QA utilities (runners/generators/reports). Batch generators can be long-running."],
      uiSteps: [
        "Click Run and monitor output.",
        "If it generates files, check git status and review diffs.",
      ],
    };
  }

  if (path.startsWith("tools/")) {
    if (/(diagnostic|cleanup|health|doctor)/.test(p)) {
      return {
        category: "Diagnostics & Maintenance",
        group: "Health & Cleanup",
        kind: "tool",
        visibility,
        hideByDefault: visibility === "debug",
        excludeFromUI,
        notes: ["Safe to run frequently; use first when debugging."],
        uiSteps: ["Click Run and review warnings/errors.", "If files changed, verify via git diff."],
      };
    }

    if (/(lexicon|wikidata|harvest)/.test(p)) {
      return {
        category: "Lexicon & Data",
        group: "Mining & Harvesting",
        kind: "tool",
        visibility,
        hideByDefault: visibility === "debug",
        excludeFromUI,
        notes: [
          "May write many JSON shards; keep git clean. Prefer running on a branch for large refreshes.",
        ],
        uiSteps: ["Click Run and monitor output.", "Inspect generated artifacts and indices afterward."],
      };
    }

    if (/(ai_refiner)/.test(p)) {
      return {
        category: "AI Tools & Services",
        group: "Agents",
        kind: "tool",
        riskOverride: "heavy",
        visibility,
        hideByDefault: true, // force hide-by-default for AI agents in tools/
        excludeFromUI,
        notes: ["AI tools may require credentials and can be costly; run on a branch."],
        uiSteps: ["Confirm credentials/config.", "Click Run and monitor output carefully."],
      };
    }

    if (/(bootstrap_tier1)/.test(p)) {
      return {
        category: "Build System",
        group: "Tier Bootstrapping",
        kind: "tool",
        riskOverride: "moderate",
        visibility,
        hideByDefault: visibility === "debug",
        excludeFromUI,
        notes: ["Bootstraps Tier 1 scaffolding; may create or update code/artifacts."],
        uiSteps: ["Click Run.", "Review console output and git diffs afterward."],
      };
    }

    return {
      category: "Tools",
      group: "Misc Tools",
      kind: "tool",
      visibility,
      hideByDefault: visibility === "debug",
      excludeFromUI,
      notes: ["General-purpose tool script."],
      uiSteps: ["Click Run and review console output."],
    };
  }

  if (path.startsWith("scripts/lexicon/")) {
    return {
      category: "Lexicon & Data",
      group: "Legacy Lexicon Scripts",
      kind: "script",
      statusOverride: "legacy",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["Legacy DB-era scripts (reference only unless DB pipeline exists)."],
      uiSteps: [
        "Open in Repo to confirm environment assumptions.",
        "Run only in the intended legacy environment.",
      ],
    };
  }

  if (path.startsWith("scripts/")) {
    if (p.includes("demo_")) {
      return {
        category: "Demos & Prototypes",
        group: "Demos",
        kind: "script",
        visibility,
        hideByDefault: true,
        excludeFromUI,
        notes: ["Local demos. Useful for manual validation."],
        uiSteps: ["Prefer running via CLI for interactive output."],
      };
    }

    if (p.includes("test_")) {
      return {
        category: "QA & Testing",
        group: "Diagnostic Scripts",
        kind: "script",
        statusOverride: status,
        visibility,
        hideByDefault: true,
        excludeFromUI,
        notes: ["Ad-hoc diagnostic scripts; prefer pytest for repeatable regression."],
        uiSteps: ["Open in Repo to confirm args; run from CLI when needed."],
      };
    }

    return {
      category: "Scripts",
      group: "Misc Scripts",
      kind: "script",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["Ad-hoc scripts; prefer tools/ or manage.py for standardized ops."],
      uiSteps: ["Open in Repo to confirm args; run from CLI when needed."],
    };
  }

  if (path.startsWith("utils/")) {
    if (isRunnableUtility(path)) {
      // Some runnable utils are power-user tools (AI), keep hidden by default.
      const hideBecausePowerUser =
        p.includes("seed_lexicon_ai") || p.includes("seed_lexicon");

      return {
        category: hideBecausePowerUser ? "AI Tools & Services" : "Lexicon & Data",
        group: hideBecausePowerUser ? "AI Utilities" : "Schema & Index",
        kind: "utility",
        visibility: hideBecausePowerUser ? "debug" : "default",
        hideByDefault: hideBecausePowerUser ? true : false,
        excludeFromUI,
        notes: hideBecausePowerUser
          ? ["AI utility may require credentials and can be costly; run on a branch."]
          : ["Runnable utility (CLI). Often used in lexicon pipeline (schema/index/stats)."],
        uiSteps: hideBecausePowerUser
          ? ["Confirm credentials/config. Run and monitor output carefully."]
          : ["Run carefully; if it writes files, check git status and review diffs."],
      };
    }

    if (/(seed_lexicon|ai)/.test(p)) {
      return {
        category: "AI Tools & Services",
        group: "AI Utilities",
        kind: "utility",
        visibility,
        hideByDefault: true,
        excludeFromUI,
        notes: ["AI utilities may require credentials and can be costly; run on a branch."],
        uiSteps: ["Confirm credentials/config. Run and monitor output carefully."],
      };
    }

    return {
      category: "Libraries",
      group: "Utilities & Libraries",
      kind: "utility",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["Mostly library modules; not all are meant to be executed directly."],
      uiSteps: ["Use Open in Repo to confirm if it is executable."],
    };
  }

  if (path.startsWith("ai_services/")) {
    return {
      category: "AI Tools & Services",
      group: "Agents",
      kind: "agent",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["AI services/agents may require credentials/config and can be costly. Run on a branch."],
      uiSteps: ["Confirm credentials/config. Prefer invoking via backend service layer."],
    };
  }

  if (path.startsWith("nlg/")) {
    return {
      category: "Demos & Prototypes",
      group: "NLG",
      kind: "utility",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["NLG experiments and supporting modules."],
      uiSteps: ["Prefer CLI for interactive workflows."],
    };
  }

  if (path.startsWith("prototypes/")) {
    return {
      category: "Demos & Prototypes",
      group: "Experimental",
      kind: "prototype",
      statusOverride: "experimental",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["Experimental code. Not guaranteed stable."],
      uiSteps: ["Prefer CLI and isolate changes."],
    };
  }

  if (path.startsWith("tests/")) {
    let group = "Pytest";
    if (p.includes("smoke")) group = "Pytest • Smoke";
    else if (p.includes("gf")) group = "Pytest • GF Engine";
    else if (p.includes("lexicon")) group = "Pytest • Lexicon";
    else if (p.includes("frames")) group = "Pytest • Frames";
    else if (p.includes("api")) group = "Pytest • API";
    else if (p.includes("integration")) group = "Pytest • Integration";

    return {
      category: "QA & Testing",
      group,
      kind: "test",
      visibility,
      hideByDefault: true,
      excludeFromUI,
      notes: ["Prefer running via pytest for consistent, repeatable results."],
      uiSteps: ["Copy the pytest command from CLI equivalents and run locally/CI."],
    };
  }

  return {
    category: "Other",
    group: "Other",
    kind: "utility",
    visibility,
    hideByDefault: visibility === "debug",
    excludeFromUI,
    notes: ["Unclassified item."],
    uiSteps: ["Open in Repo for details."],
  };
};
