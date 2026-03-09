// architect_frontend/src/app/tools/page.tsx
"use client";

import React, {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Terminal,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  PlugZap,
  Route,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { INVENTORY } from "./inventory";
import ToolListPanel, { type GroupedTools } from "./components/ToolListPanel";
import ToolDetailsCard from "./components/ToolDetailsCard";
import ConsoleCard from "./components/ConsoleCard";

import { buildToolItems, type ToolItem } from "./lib/buildToolItems";
import { useToolRunner } from "./hooks/useToolRunner";
import { normalizeApiV1, normalizeRepoUrl } from "./utils";
import type { HealthReady } from "./types";

// ----------------------------------------------------------------------------
// API base normalization
// ----------------------------------------------------------------------------
const RAW_API_BASE =
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

const API_V1 = normalizeApiV1(RAW_API_BASE);
const REPO_URL = normalizeRepoUrl(process.env.NEXT_PUBLIC_REPO_URL || "");

// ----------------------------------------------------------------------------
// Local persistence
// ----------------------------------------------------------------------------
const LS_PREFS_KEY = "tools_dashboard_prefs_v4";
const LS_ARGS_KEY = "tools_dashboard_args_v2";

// ----------------------------------------------------------------------------
// Workflow model
// ----------------------------------------------------------------------------
type WorkflowFilter =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

type WorkflowCard = {
  title: string;
  summary: string;
  steps: string[];
  note?: string;
};

type Prefs = {
  workflowFilter: WorkflowFilter;
  powerUser: boolean;
  showLegacy: boolean;
  showTests: boolean;
  showInternal: boolean;
  wiredOnly: boolean;
  showHeavy: boolean;
  leftCollapsed: boolean;
  autoScrollConsole: boolean;
  dryRun: boolean;
};

const WORKFLOW_OPTIONS: Array<{ value: WorkflowFilter; label: string }> = [
  { value: "recommended", label: "Recommended" },
  { value: "language_integration", label: "Language Integration" },
  { value: "lexicon_work", label: "Lexicon Work" },
  { value: "build_matrix", label: "Build & Matrix" },
  { value: "qa_validation", label: "QA & Validation" },
  { value: "debug_recovery", label: "Debug & Recovery" },
  { value: "ai_assist", label: "AI Assist" },
  { value: "all", label: "All tools" },
];

const WORKFLOW_TOOL_IDS: Record<Exclude<WorkflowFilter, "all">, string[]> = {
  recommended: [
    "build_index",
    "compile_pgf",
    "language_health",
    "run_judge",
  ],
  language_integration: [
    "build_index",
    "lexicon_coverage",
    "compile_pgf",
    "language_health",
    "run_judge",
    "harvest_lexicon",
    "gap_filler",
    "bootstrap_tier1",
  ],
  lexicon_work: [
    "harvest_lexicon",
    "gap_filler",
    "lexicon_coverage",
    "seed_lexicon",
    "build_lexicon_wikidata",
    "refresh_index",
    "migrate_schema",
  ],
  build_matrix: [
    "build_index",
    "compile_pgf",
    "bootstrap_tier1",
    "rgl_scanner",
    "lexicon_scanner",
    "app_scanner",
    "qa_scanner",
  ],
  qa_validation: [
    "language_health",
    "run_judge",
    "profiler",
    "diagnostic_audit",
    "test_api_smoke",
    "test_gf_dynamic",
    "test_multilingual_generation",
    "run_smoke_tests",
    "generate_lexicon_regression_tests",
  ],
  debug_recovery: [
    "diagnostic_audit",
    "rgl_scanner",
    "lexicon_scanner",
    "app_scanner",
    "qa_scanner",
    "test_api_smoke",
    "test_gf_dynamic",
    "test_multilingual_generation",
    "bootstrap_tier1",
    "ai_refiner",
  ],
  ai_assist: ["ai_refiner", "seed_lexicon"],
};

const WORKFLOW_CARDS: Record<WorkflowFilter, WorkflowCard> = {
  recommended: {
    title: "Recommended workflow",
    summary: "Shortest safe path for most normal work.",
    steps: [
      "Build Index",
      "Compile PGF",
      "Language Health",
      "Generate sentence",
      "Run Judge",
    ],
    note: "Power user reveals hidden/debug tools inside this workflow.",
  },
  language_integration: {
    title: "Language integration workflow",
    summary: "Use this when adding or repairing one language.",
    steps: [
      "Add or change language files",
      "Build Index",
      "Lexicon Coverage",
      "Harvest / Gap Fill if needed",
      "Bootstrap Tier 1 if needed",
      "Compile PGF",
      "Language Health",
      "Generate sentence",
      "Run Judge",
    ],
    note: "Normal path first. Recovery tools appear only when Power user is enabled.",
  },
  lexicon_work: {
    title: "Lexicon workflow",
    summary: "Focused on vocabulary/data work rather than grammar work.",
    steps: [
      "Harvest or seed data",
      "Gap Fill",
      "Lexicon Coverage",
      "Build Index",
      "Language Health",
    ],
    note: "Use this when the language exists but the data is thin or messy.",
  },
  build_matrix: {
    title: "Build & Matrix workflow",
    summary: "Use this when thinking in terms of inventory/build state.",
    steps: ["Build Index", "Compile PGF", "Language Health"],
    note: "Scanners are for debugging the matrix, not for the normal path.",
  },
  qa_validation: {
    title: "QA & Validation workflow",
    summary: "Use this to answer: does it work, is it correct, is it fast?",
    steps: [
      "Language Health",
      "Generate sentence",
      "Run Judge",
      "Profiler",
    ],
    note: "Power user reveals lower-level pytest and regression tools.",
  },
  debug_recovery: {
    title: "Debug & Recovery workflow",
    summary: "Use this only when the repo/build state looks wrong.",
    steps: [
      "Diagnostic Audit",
      "Targeted scanner or targeted test",
      "Fix",
      "Build Index",
      "Compile PGF",
      "Language Health",
    ],
    note: "This is not the normal workflow.",
  },
  ai_assist: {
    title: "AI Assist workflow",
    summary: "AI should help only after deterministic tools show a real gap.",
    steps: [
      "Deterministic check fails or reveals a real gap",
      "AI assist",
      "Build Index",
      "Compile PGF",
      "Language Health",
      "Run Judge",
    ],
    note: "This view is most useful with Power user enabled.",
  },
  all: {
    title: "All tools",
    summary: "Browse the full tool universe with the current visibility settings.",
    steps: [
      "Choose a tool set",
      "Review the recommended workflow",
      "Run the selected tool",
    ],
    note: "Use the workflow dropdown to narrow the page when you know the task.",
  },
};

// ----------------------------------------------------------------------------
// LocalStorage hook (hydrates after mount; persists on change)
// ----------------------------------------------------------------------------
function safeJsonParse<T>(
  s: string
): { ok: true; value: T } | { ok: false; error: unknown } {
  try {
    return { ok: true, value: JSON.parse(s) as T };
  } catch (e) {
    return { ok: false, error: e };
  }
}

function useLocalStorageState<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(initialValue);
  const hydratedRef = useRef(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = safeJsonParse<T>(raw);
        if (parsed.ok) setValue(parsed.value);
      }
    } catch {
      // ignore
    } finally {
      hydratedRef.current = true;
    }
  }, [key]);

  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // ignore
    }
  }, [key, value]);

  return [value, setValue] as const;
}

// ----------------------------------------------------------------------------
// UI helpers
// ----------------------------------------------------------------------------
function healthBadge(label: string, value?: unknown) {
  const s =
    typeof value === "string"
      ? value
      : value == null
      ? undefined
      : String(value);

  const v = (s || "").toLowerCase();
  const ok = v === "ok" || v === "ready" || v === "up" || v === "healthy";
  const bad = v === "down" || v === "unhealthy" || v === "error" || v === "fail";

  return (
    <span className="inline-flex items-center gap-1 text-xs">
      {ok ? (
        <CheckCircle2 className="w-3 h-3 text-green-500" />
      ) : bad ? (
        <XCircle className="w-3 h-3 text-red-500" />
      ) : (
        <AlertTriangle className="w-3 h-3 text-amber-500" />
      )}
      <span className="text-slate-600">{label}:</span>
      <span className="font-mono text-slate-700">{s ?? "unknown"}</span>
    </span>
  );
}

const collator = new Intl.Collator(undefined, {
  sensitivity: "base",
  numeric: true,
});

function groupItems(items: ToolItem[]): GroupedTools {
  const byCat: GroupedTools = new Map();

  for (const it of items) {
    let byGroup = byCat.get(it.category);
    if (!byGroup) {
      byGroup = new Map();
      byCat.set(it.category, byGroup);
    }

    const existing = byGroup.get(it.group) as ToolItem[] | undefined;
    if (existing) existing.push(it);
    else byGroup.set(it.group, [it]);
  }

  byCat.forEach((byGroup) => {
    byGroup.forEach((arr) => {
      (arr as ToolItem[]).sort((a: ToolItem, b: ToolItem) =>
        collator.compare(a.title, b.title)
      );
    });
  });

  return byCat;
}

function getWorkflowIds(filter: WorkflowFilter): Set<string> | null {
  if (filter === "all") return null;
  return new Set(WORKFLOW_TOOL_IDS[filter].map((x) => x.toLowerCase()));
}

function matchesWorkflow(item: ToolItem, workflowIds: Set<string> | null) {
  if (!workflowIds) return true;

  const candidates = [
    item.wiredToolId ? String(item.wiredToolId).toLowerCase() : "",
    item.toolIdGuess ? String(item.toolIdGuess).toLowerCase() : "",
  ].filter(Boolean);

  return candidates.some((id) => workflowIds.has(id));
}

// ----------------------------------------------------------------------------
// Page
// ----------------------------------------------------------------------------
export default function ToolsDashboard() {
  const [prefs, setPrefs] = useLocalStorageState<Prefs>(LS_PREFS_KEY, {
    workflowFilter: "recommended",
    powerUser: false,
    showLegacy: true,
    showTests: true,
    showInternal: false,
    wiredOnly: false,
    showHeavy: true,
    leftCollapsed: false,
    autoScrollConsole: true,
    dryRun: false,
  });

  const workflowFilter = prefs.workflowFilter;
  const powerUser = Boolean(prefs.powerUser);
  const showLegacy = Boolean(prefs.showLegacy);
  const showTests = Boolean(prefs.showTests);
  const showInternal = Boolean(prefs.showInternal);
  const wiredOnly = Boolean(prefs.wiredOnly);
  const showHeavy = Boolean(prefs.showHeavy);
  const leftCollapsed = Boolean(prefs.leftCollapsed);
  const autoScrollConsole = Boolean(prefs.autoScrollConsole);
  const dryRun = Boolean(prefs.dryRun);

  const setBoolPref = useCallback(
    (
      k: Exclude<keyof Prefs, "workflowFilter">,
      v: boolean
    ) => setPrefs((p) => ({ ...p, [k]: v })),
    [setPrefs]
  );

  const setWorkflowFilter = useCallback(
    (v: WorkflowFilter) => setPrefs((p) => ({ ...p, workflowFilter: v })),
    [setPrefs]
  );

  const [argsByToolId, setArgsByToolId] = useLocalStorageState<
    Record<string, string>
  >(LS_ARGS_KEY, {});

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const items = useMemo(() => buildToolItems({ sort: true }), []);
  const wiredCount = useMemo(
    () => items.filter((x) => Boolean(x.wiredToolId)).length,
    [items]
  );

  const workflowIds = useMemo(
    () => getWorkflowIds(workflowFilter),
    [workflowFilter]
  );

  const workflowCard = useMemo(
    () => WORKFLOW_CARDS[workflowFilter],
    [workflowFilter]
  );

  const filteredItems = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();

    const effectiveWiredOnly = powerUser ? wiredOnly : true;
    const effectiveShowLegacy = powerUser ? showLegacy : false;
    const effectiveShowTests = powerUser ? showTests : false;
    const effectiveShowInternal = powerUser ? showInternal : false;
    const effectiveShowHeavy = powerUser ? showHeavy : true;

    return items.filter((it) => {
      if (!matchesWorkflow(it, workflowIds)) return false;
      if (!effectiveShowHeavy && it.risk === "heavy") return false;
      if (effectiveWiredOnly && !it.wiredToolId) return false;
      if (!effectiveShowLegacy && it.status === "legacy") return false;
      if (!effectiveShowTests && it.kind === "test") return false;
      if (!effectiveShowInternal && it.status === "internal") return false;
      if (!powerUser && it.hiddenInNormalMode) return false;

      if (!q) return true;

      return (
        it.title.toLowerCase().includes(q) ||
        it.path.toLowerCase().includes(q) ||
        it.category.toLowerCase().includes(q) ||
        it.group.toLowerCase().includes(q) ||
        it.toolIdGuess.toLowerCase().includes(q) ||
        (it.wiredToolId
          ? String(it.wiredToolId).toLowerCase().includes(q)
          : false)
      );
    });
  }, [
    deferredQuery,
    items,
    powerUser,
    showHeavy,
    showInternal,
    showLegacy,
    showTests,
    wiredOnly,
    workflowIds,
  ]);

  const grouped = useMemo(() => groupItems(filteredItems), [filteredItems]);

  const selected = useMemo(() => {
    if (!selectedKey) return null;
    return items.find((x) => x.key === selectedKey) || null;
  }, [items, selectedKey]);

  const selectedToolId = selected?.wiredToolId ? String(selected.wiredToolId) : null;

  useEffect(() => {
    if (!selectedKey) return;
    const stillVisible = filteredItems.some((x) => x.key === selectedKey);
    if (!stillVisible) setSelectedKey(null);
  }, [filteredItems, selectedKey]);

  // ----------------------------------------------------------------------------
  // Health
  // ----------------------------------------------------------------------------
  const [health, setHealth] = useState<HealthReady | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const refreshHealth = useCallback(async () => {
    const controller = new AbortController();
    setHealthLoading(true);
    try {
      const res = await fetch(`${API_V1}/health/ready`, {
        cache: "no-store",
        signal: controller.signal,
      });
      const text = await res.text();
      const parsed = safeJsonParse<HealthReady>(text);
      setHealth(parsed.ok ? parsed.value : null);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let cleanup: void | (() => void);
    (async () => {
      cleanup = await refreshHealth();
    })();
    return () => {
      if (cleanup) cleanup();
    };
  }, [refreshHealth]);

  // ----------------------------------------------------------------------------
  // Runner
  // ----------------------------------------------------------------------------
  const {
    consoleOutput,
    appendConsole,
    clear,
    cancelRun,
    runTool: runToolCore,
    activeToolId,
    lastStatus,
    lastResponseJson,
    visualData,
    setVisualData,
  } = useToolRunner({
    apiV1: API_V1,
    initialConsole:
      `// Tools Command Center\n` +
      `// Inventory v${INVENTORY.version} (generated ${INVENTORY.generated_on})\n` +
      `// API: ${API_V1}\n` +
      `// Normal mode shows only backend-wired runnable tools.\n` +
      `// Enable Power user (debug) to reveal the full inventory.\n`,
  });

  const runFromItem = useCallback(
    async (it: ToolItem) => {
      if (!it.wiredToolId) return;
      const toolId = String(it.wiredToolId);
      const argsStr = argsByToolId[toolId] || "";

      const dryRunFromArgs = /(^|\s)--dry(?:-run)?(\s|$)/.test(argsStr);
      const effectiveDryRun = dryRun || dryRunFromArgs;

      const res = await runToolCore(
        { title: it.title, risk: it.risk, wiredToolId: toolId, kind: it.kind },
        argsStr,
        effectiveDryRun
      );

      if (!res && !toolId) {
        appendConsole([`[ERROR] "${it.title}" is not wired.`], true);
      }
    },
    [appendConsole, argsByToolId, dryRun, runToolCore]
  );

  const visibleCount = filteredItems.length;

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-3">
          <Terminal className="w-8 h-8 text-slate-700 dark:text-slate-300" />
          Tools Command Center
        </h1>
        <p className="text-slate-500 dark:text-slate-400">
          Inventory-driven tools browser (v{INVENTORY.version},{" "}
          {INVENTORY.generated_on}).{" "}
          {!powerUser ? (
            <>Normal mode shows only backend-wired runnable tools.</>
          ) : (
            <>
              Power user mode reveals the full inventory (including non-wired,
              tests, internal, legacy).
            </>
          )}
        </p>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <PlugZap className="w-4 h-4 text-slate-500" />
            Interface
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
            <div className="lg:col-span-2">
              <div className="text-xs text-slate-500 mb-1">Search</div>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name, path, category, tool_id…"
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
              />
            </div>

            <div>
              <div className="text-xs text-slate-500 mb-1">Workflow / Tool set</div>
              <select
                value={workflowFilter}
                onChange={(e) =>
                  setWorkflowFilter(e.target.value as WorkflowFilter)
                }
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
              >
                {WORKFLOW_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-end gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                <input
                  type="checkbox"
                  checked={powerUser}
                  onChange={(e) => setBoolPref("powerUser", e.target.checked)}
                />
                Power user (debug)
              </label>

              <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setBoolPref("dryRun", e.target.checked)}
                />
                Dry run
              </label>
            </div>
          </div>

          <Card className="border-slate-200 bg-slate-50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Route className="w-4 h-4 text-slate-500" />
                {workflowCard.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-slate-600">{workflowCard.summary}</p>
              <ol className="list-decimal pl-5 text-sm text-slate-800 space-y-1">
                {workflowCard.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              {workflowCard.note ? (
                <p className="text-xs text-slate-500">{workflowCard.note}</p>
              ) : null}
            </CardContent>
          </Card>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 flex-wrap">
              {powerUser ? (
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={wiredOnly}
                      onChange={(e) => setBoolPref("wiredOnly", e.target.checked)}
                    />
                    Wired only
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showLegacy}
                      onChange={(e) => setBoolPref("showLegacy", e.target.checked)}
                    />
                    Show legacy
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showTests}
                      onChange={(e) => setBoolPref("showTests", e.target.checked)}
                    />
                    Show tests
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showInternal}
                      onChange={(e) => setBoolPref("showInternal", e.target.checked)}
                    />
                    Show internal
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showHeavy}
                      onChange={(e) => setBoolPref("showHeavy", e.target.checked)}
                    />
                    Show heavy
                  </label>
                </div>
              ) : (
                <span className="text-xs text-slate-400">
                  Advanced filters hidden. Power user reveals hidden/debug tools
                  inside the selected workflow.
                </span>
              )}
            </div>

            <div className="text-xs text-slate-500">
              API: <span className="font-mono">{API_V1}</span> • Workflow:{" "}
              <span className="font-mono">{workflowFilter}</span> • Visible:{" "}
              <span className="font-mono">{visibleCount}</span> /{" "}
              <span className="font-mono">{items.length}</span> • Wired tools:{" "}
              <span className="font-mono">{wiredCount}</span>
              {REPO_URL ? (
                <>
                  {" "}
                  • Repo: <span className="font-mono">{REPO_URL}</span>
                </>
              ) : (
                <>
                  {" "}
                  • Set <span className="font-mono">NEXT_PUBLIC_REPO_URL</span>{" "}
                  to enable file links.
                </>
              )}{" "}
              • Mode: <span className="font-mono">{dryRun ? "dry-run" : "live"}</span>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="inline-flex items-center gap-2 text-xs">
              {healthBadge("broker", health?.broker)}
              {healthBadge("storage", health?.storage)}
              {healthBadge("engine", health?.engine)}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={refreshHealth}
              disabled={healthLoading}
            >
              {healthLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Checking
                </span>
              ) : (
                "Refresh health"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-280px)]">
        {/* LEFT: Tool list */}
        <div
          className={`${
            leftCollapsed ? "lg:col-span-0 lg:hidden" : "lg:col-span-1"
          } overflow-y-auto pr-2 pb-10`}
        >
          <ToolListPanel
            grouped={grouped}
            selectedKey={selectedKey}
            activeToolId={activeToolId}
            powerUser={powerUser}
            onSelect={setSelectedKey}
            onRun={runFromItem}
          />
        </div>

        {/* RIGHT: Details + Console */}
        <div
          className={`${
            leftCollapsed ? "lg:col-span-3" : "lg:col-span-2"
          } flex flex-col h-full gap-4`}
        >
          <ToolDetailsCard
            selected={selected}
            powerUser={powerUser}
            leftCollapsed={leftCollapsed}
            onToggleLeftCollapsed={() =>
              setBoolPref("leftCollapsed", !leftCollapsed)
            }
            activeToolId={activeToolId}
            runTool={runFromItem}
            argsByToolId={argsByToolId}
            setArgsByToolId={setArgsByToolId}
            repoUrl={REPO_URL}
          />

          <ConsoleCard
            consoleOutput={consoleOutput}
            lastStatus={lastStatus}
            lastResponseJson={lastResponseJson}
            activeToolId={activeToolId}
            selectedToolId={selectedToolId ?? undefined}
            autoScroll={autoScrollConsole}
            onAutoScrollChange={(next) => setBoolPref("autoScrollConsole", next)}
            onCancel={cancelRun}
            onClear={clear}
            visualData={visualData}
            onCloseVisualizer={() => setVisualData(null)}
            visualizerHeight={500}
          />
        </div>
      </div>
    </div>
  );
}