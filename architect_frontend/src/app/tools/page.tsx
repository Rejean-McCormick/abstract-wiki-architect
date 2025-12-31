// architect_frontend/src/app/tools/page.tsx
"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Terminal,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  Info,
  ExternalLink,
  Copy,
  PlugZap,
  AlertTriangle,
  Search,
  Eye,
  EyeOff,
  Filter,
  ChevronRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { INVENTORY } from "./inventory";
import { BACKEND_TOOL_REGISTRY, type BackendToolId } from "./backendRegistry";
import { TOOL_DESCRIPTIONS, defaultDesc } from "./descriptions";
import {
  classify,
  cliFromPath,
  riskFromPath,
  statusFromPath,
  titleFromPath,
  type Status,
  type ToolKind,
} from "./classify";
import {
  copyToClipboard,
  docsHref,
  normalizeApiV1,
  normalizeRepoUrl,
  parseCliArgs,
  repoFileUrl,
} from "./utils";
import { RiskBadge, StatusBadge, WiringBadge } from "./components/Badges";
import { iconForCategory } from "./components/icons";

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------
type HealthReady = {
  broker?: string;
  storage?: string;
  engine?: string;
};

type ToolRunResponse = {
  success: boolean;
  output?: string;
  error?: string;
  return_code?: number; // legacy
  exit_code?: number; // current backend
  tool_id?: string;
  command?: string;
  truncated?: boolean;
  duration_ms?: number;
};

type ToolItem = {
  key: string;
  title: string;
  path: string;
  category: string;
  group: string;
  kind: ToolKind;
  risk: "safe" | "moderate" | "heavy";
  status: Status;
  desc?: string;
  cli: string[];
  notes: string[];
  uiSteps: string[];
  wiredToolId?: string; // if wired, exact backend allowlisted tool_id
  toolIdGuess: string; // best-effort guess for display/search
  commandPreview?: string; // backend registry command preview (if wired)
  hiddenInNormalMode?: boolean; // derived (debug-only)
};

const TOOL_ID_BY_PATH: Record<string, string> = Object.fromEntries(
  Object.entries(BACKEND_TOOL_REGISTRY).map(([toolId, meta]) => [meta.path, toolId])
);

const WIRED_TOOL_IDS = new Set<string>(Object.keys(BACKEND_TOOL_REGISTRY));

// ----------------------------------------------------------------------------
// API base normalization (supports both host base and /api/v1 base).
// ----------------------------------------------------------------------------
const RAW_API_BASE =
  process.env.NEXT_PUBLIC_ARCHITECT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

const API_V1 = normalizeApiV1(RAW_API_BASE);
const REPO_URL = normalizeRepoUrl(process.env.NEXT_PUBLIC_REPO_URL || "");

// ----------------------------------------------------------------------------
// UI Helpers
// ----------------------------------------------------------------------------
function healthBadge(label: string, value?: string) {
  const v = (value || "").toLowerCase();
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
      <span className="font-mono text-slate-700">{value ?? "unknown"}</span>
    </span>
  );
}

function clampLines(n: number) {
  // tailwind line-clamp-x class generator guard
  if (n <= 1) return "line-clamp-1";
  if (n === 2) return "line-clamp-2";
  if (n === 3) return "line-clamp-3";
  return "line-clamp-4";
}

// ----------------------------------------------------------------------------
// Page
// ----------------------------------------------------------------------------
export default function ToolsDashboard() {
  const [activeToolId, setActiveToolId] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const [consoleOutput, setConsoleOutput] = useState<string>(
    `// Tools Command Center\n` +
      `// Inventory v${INVENTORY.version} (generated ${INVENTORY.generated_on})\n` +
      `// API: ${API_V1}\n` +
      `// Normal mode shows only backend-wired runnable tools.\n` +
      `// Enable Power user (debug) to reveal the full inventory.`
  );

  const [lastStatus, setLastStatus] = useState<"success" | "error" | null>(null);
  const [query, setQuery] = useState("");

  // Power user (debug) gate
  const [powerUser, setPowerUser] = useState(false);

  // Advanced filters (only meaningful in power-user mode)
  const [showLegacy, setShowLegacy] = useState(true);
  const [showTests, setShowTests] = useState(true);
  const [showInternal, setShowInternal] = useState(false);
  const [wiredOnly, setWiredOnly] = useState(false);
  const [showHeavy, setShowHeavy] = useState(true);

  // UI affordances
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [autoScrollConsole, setAutoScrollConsole] = useState(true);

  const consoleRef = useRef<HTMLTextAreaElement | null>(null);

  const [health, setHealth] = useState<HealthReady | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const [argsByToolId, setArgsByToolId] = useState<Record<string, string>>({});

  const refreshHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await fetch(`${API_V1}/health/ready`, { cache: "no-store" });
      const data = (await res.json()) as HealthReady;
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    refreshHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll console to bottom on output changes (opt-out)
  useEffect(() => {
    if (!autoScrollConsole) return;
    const el = consoleRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [consoleOutput, autoScrollConsole]);

  const items: ToolItem[] = useMemo(() => {
    const allPaths: string[] = [];

    allPaths.push(...(INVENTORY.root_entrypoints as readonly string[]));
    allPaths.push(...(INVENTORY.gf as readonly string[]));
    allPaths.push(...(INVENTORY.tools.root || []));
    allPaths.push(...(INVENTORY.tools.everything_matrix || []));
    allPaths.push(...(INVENTORY.tools.qa || []));
    allPaths.push(...(INVENTORY.scripts.root || []));
    allPaths.push(...(INVENTORY.scripts.lexicon || []));
    allPaths.push(...(INVENTORY.utils as readonly string[]));
    allPaths.push(...(INVENTORY.ai_services as readonly string[]));
    allPaths.push(...(INVENTORY.nlg as readonly string[]));
    allPaths.push(...(INVENTORY.prototypes as readonly string[]));
    allPaths.push(...(INVENTORY.tests.root || []));
    allPaths.push(...(INVENTORY.tests.http_api_legacy || []));
    allPaths.push(...(INVENTORY.tests.adapters_core_integration || []));

    const out: ToolItem[] = [];

    // 1) Build items from inventory (repo browsing)
    for (const path of allPaths) {
      const cls = classify(INVENTORY.root_entrypoints as readonly string[], path);

      // Respect classify() exclusion policy (keeps UI noise down even in debug)
      if (cls.excludeFromUI) continue;

      const status = cls.statusOverride ?? statusFromPath(path);
      const risk = cls.riskOverride ?? riskFromPath(path);
      const desc = TOOL_DESCRIPTIONS[path] ?? defaultDesc(path);

      const wiredToolId = TOOL_ID_BY_PATH[path];
      const toolIdGuess = wiredToolId || (path.split("/").pop() || path).replace(/\.[^.]+$/, "");
      const wired = Boolean(wiredToolId);

      const cli =
        path === "manage.py"
          ? ["python manage.py start", "python manage.py build", "python manage.py doctor"]
          : path === "gf/build_orchestrator.py"
          ? ["python gf/build_orchestrator.py", "python manage.py build"]
          : cliFromPath(path);

      const notes = [
        ...cls.notes,
        ...(wired
          ? ["Wired: Run is enabled (backend allowlist)."]
          : ["Not wired: shown for reference only (not in backend allowlist)."]),
        ...(status === "legacy" ? ["Legacy/compat: may require endpoint or pipeline updates."] : []),
        ...(status === "experimental" ? ["Experimental: not guaranteed stable."] : []),
        ...(status === "internal" ? ["Internal module: usually not executed directly."] : []),
      ];

      const commandPreview = wiredToolId
        ? (BACKEND_TOOL_REGISTRY[wiredToolId as BackendToolId]?.cmd || []).join(" ").trim()
        : undefined;

      out.push({
        key: `file-${path.replace(/[^a-zA-Z0-9]+/g, "-")}`,
        title: titleFromPath(path),
        path,
        category: cls.category,
        group: cls.group,
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
        hiddenInNormalMode: cls.hideByDefault || false,
      });
    }

    // 2) Add any backend-wired tools not present in inventory snapshot
    const presentPaths = new Set(allPaths);
    for (const [toolId, meta] of Object.entries(BACKEND_TOOL_REGISTRY)) {
      if (presentPaths.has(meta.path)) continue;

      const path = meta.path;
      const desc = TOOL_DESCRIPTIONS[path] ?? `${meta.title} (backend-wired tool).`;
      const status: Status = statusFromPath(path);
      const risk = meta.risk ?? riskFromPath(path);

      out.push({
        key: `wired-${toolId}`,
        title: meta.title,
        path,
        category: meta.category,
        group: meta.group,
        kind: "tool",
        risk,
        status,
        desc,
        cli: [meta.cmd.join(" ")],
        notes: [
          "Wired: Run is enabled (backend allowlist).",
          "This tool is wired but missing from the current inventory snapshot.",
        ],
        uiSteps: ["Select the tool.", "Optionally add args.", "Click Run and review console output."],
        wiredToolId: toolId,
        toolIdGuess: toolId,
        commandPreview: meta.cmd.join(" "),
        hiddenInNormalMode: false,
      });
    }

    out.sort(
      (a, b) =>
        a.category.localeCompare(b.category) ||
        a.group.localeCompare(b.group) ||
        a.title.localeCompare(b.title)
    );

    return out;
  }, []);

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase();

    // Normal mode is intentionally conservative:
    // - wired only
    // - hide legacy/tests/internal
    // - hide heavy tools unless toggled (default: hidden in normal mode)
    const effectiveWiredOnly = powerUser ? wiredOnly : true;
    const effectiveShowLegacy = powerUser ? showLegacy : false;
    const effectiveShowTests = powerUser ? showTests : false;
    const effectiveShowInternal = powerUser ? showInternal : false;
    const effectiveShowHeavy = powerUser ? showHeavy : false;

    return items.filter((it) => {
      if (!effectiveShowHeavy && it.risk === "heavy") return false;

      if (effectiveWiredOnly && !it.wiredToolId) return false;
      if (!effectiveShowLegacy && it.status === "legacy") return false;
      if (!effectiveShowTests && it.kind === "test") return false;
      if (!effectiveShowInternal && it.status === "internal") return false;

      // In normal mode, respect classify() visibility/hideByDefault (if provided)
      if (!powerUser && it.hiddenInNormalMode) return false;

      if (!q) return true;

      return (
        it.title.toLowerCase().includes(q) ||
        it.path.toLowerCase().includes(q) ||
        it.category.toLowerCase().includes(q) ||
        it.group.toLowerCase().includes(q) ||
        it.toolIdGuess.toLowerCase().includes(q) ||
        (it.wiredToolId ? it.wiredToolId.toLowerCase().includes(q) : false)
      );
    });
  }, [items, query, powerUser, showLegacy, showTests, showInternal, wiredOnly, showHeavy]);

  const grouped = useMemo(() => {
    const byCat = new Map<string, Map<string, ToolItem[]>>();
    for (const it of filteredItems) {
      if (!byCat.has(it.category)) byCat.set(it.category, new Map());
      const byGroup = byCat.get(it.category)!;
      if (!byGroup.has(it.group)) byGroup.set(it.group, []);
      byGroup.get(it.group)!.push(it);
    }
    for (const [, byGroup] of byCat) {
      for (const [g, arr] of byGroup) {
        arr.sort((a, b) => a.title.localeCompare(b.title));
        byGroup.set(g, arr);
      }
    }
    return byCat;
  }, [filteredItems]);

  const selected = useMemo(
    () => (selectedKey ? items.find((x) => x.key === selectedKey) || null : null),
    [items, selectedKey]
  );

  // If the selected item becomes invisible under the current filters, clear selection
  useEffect(() => {
    if (!selectedKey) return;
    const stillVisible = filteredItems.some((x) => x.key === selectedKey);
    if (!stillVisible) setSelectedKey(null);
  }, [filteredItems, selectedKey]);

  const wiredCount = useMemo(() => items.filter((x) => Boolean(x.wiredToolId)).length, [items]);
  const visibleCount = filteredItems.length;

  const runTool = async (it: ToolItem) => {
    const toolId = it.wiredToolId;
    if (!toolId) return;

    const argsStr = argsByToolId[toolId] || "";
    const args = parseCliArgs(argsStr);

    const requiresConfirm = it.risk === "heavy" || it.risk === "moderate";
    if (requiresConfirm) {
      const ok = window.confirm(
        `Run "${it.title}"?\n\nRisk: ${it.risk.toUpperCase()}\nTool ID: ${toolId}\nArgs: ${args.join(
          " "
        )}\n\nProceed?`
      );
      if (!ok) return;
    }

    setActiveToolId(toolId);
    setLastStatus(null);

    setConsoleOutput((prev) => {
      const header =
        `\n\n> Executing: ${it.title}\n` +
        `  tool_id=${toolId}\n` +
        `  args=${args.join(" ")}\n` +
        `----------------------------------------`;
      return prev + header;
    });

    try {
      const res = await fetch(`${API_V1}/tools/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool_id: toolId, args }),
      });

      let data: ToolRunResponse | null = null;
      try {
        data = (await res.json()) as ToolRunResponse;
      } catch {
        data = { success: false, error: await res.text() };
      }

      const rc =
        typeof data?.exit_code === "number"
          ? data.exit_code
          : typeof data?.return_code === "number"
          ? data.return_code
          : data?.success
          ? 0
          : -1;

      if (data?.success) {
        setLastStatus("success");
        setConsoleOutput((prev) => {
          const cmd = data?.command ? `\n[COMMAND]\n${data.command}\n` : "";
          const out = data?.output ? `\n[OUTPUT]\n${data.output}\n` : "\n[OUTPUT]\n";
          const meta =
            typeof data?.duration_ms === "number" || data?.truncated
              ? `\n[META]${typeof data?.duration_ms === "number" ? ` duration_ms=${data.duration_ms}` : ""}${
                  data?.truncated ? " truncated=true" : ""
                }\n`
              : "";
          return prev + `${cmd}${meta}${out}\n[SUCCESS] exit_code=${rc}`;
        });
      } else {
        setLastStatus("error");
        setConsoleOutput((prev) => {
          const cmd = data?.command ? `\n[COMMAND]\n${data.command}\n` : "";
          const out = data?.output ? `\n[OUTPUT]\n${data.output}\n` : "";
          const err = data?.error ? `\n[ERROR]\n${data.error}\n` : "\n[ERROR]\nUnknown error";
          const meta =
            typeof data?.duration_ms === "number" || data?.truncated
              ? `\n[META]${typeof data?.duration_ms === "number" ? ` duration_ms=${data.duration_ms}` : ""}${
                  data?.truncated ? " truncated=true" : ""
                }\n`
              : "";
          return prev + `${cmd}${meta}${out}${err}\n[FAILED] exit_code=${rc}`;
        });
      }
    } catch (e: any) {
      setLastStatus("error");
      setConsoleOutput((prev) => prev + `\n[NETWORK ERROR]: ${e?.message || String(e)}`);
    } finally {
      setActiveToolId(null);
    }
  };

  const selectedToolId = selected?.wiredToolId || null;

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      {/* HEADER */}
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-3">
          <Terminal className="w-8 h-8 text-slate-700 dark:text-slate-300" />
          Tools Command Center
        </h1>
        <p className="text-slate-500 dark:text-slate-400">
          Inventory-driven tools browser (v{INVENTORY.version}, {INVENTORY.generated_on}).{" "}
          {!powerUser ? (
            <>Normal mode shows only backend-wired runnable tools.</>
          ) : (
            <>Power user mode reveals the full inventory (including non-wired, tests, internal, legacy).</>
          )}
        </p>
      </div>

      {/* CONTROLS */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="w-4 h-4 text-slate-500" />
            Interface
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2">
              <div className="text-xs text-slate-500 mb-1 flex items-center gap-2">
                <Search className="w-3 h-3" />
                Search
              </div>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name, path, category, tool_id…"
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
              />
            </div>

            <div className="flex items-end gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                <input
                  type="checkbox"
                  checked={powerUser}
                  onChange={(e) => setPowerUser(e.target.checked)}
                />
                Power user (debug)
              </label>

              {/* Advanced toggles only when in power-user mode */}
              {powerUser ? (
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                    <Filter className="w-3 h-3" /> Filters:
                  </span>

                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input type="checkbox" checked={wiredOnly} onChange={(e) => setWiredOnly(e.target.checked)} />
                    Wired only
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input type="checkbox" checked={showLegacy} onChange={(e) => setShowLegacy(e.target.checked)} />
                    Show legacy
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input type="checkbox" checked={showTests} onChange={(e) => setShowTests(e.target.checked)} />
                    Show tests
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showInternal}
                      onChange={(e) => setShowInternal(e.target.checked)}
                    />
                    Show internal
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input type="checkbox" checked={showHeavy} onChange={(e) => setShowHeavy(e.target.checked)} />
                    Show heavy
                  </label>
                </div>
              ) : (
                <span className="text-xs text-slate-400">(advanced filters hidden)</span>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="text-xs text-slate-500">
              API: <span className="font-mono">{API_V1}</span> • Visible:{" "}
              <span className="font-mono">{visibleCount}</span> / <span className="font-mono">{items.length}</span> • Wired tools:{" "}
              <span className="font-mono">{wiredCount}</span>
              {REPO_URL ? (
                <>
                  {" "}
                  • Repo: <span className="font-mono">{REPO_URL}</span>
                </>
              ) : (
                <>
                  {" "}
                  • Set <span className="font-mono">NEXT_PUBLIC_REPO_URL</span> to enable file links.
                </>
              )}
            </div>

            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-2 text-xs">
                <PlugZap className="w-4 h-4 text-slate-500" />
                {healthBadge("broker", health?.broker)}
                {healthBadge("storage", health?.storage)}
                {healthBadge("engine", health?.engine)}
              </span>
              <Button variant="outline" size="sm" className="h-8" onClick={refreshHealth} disabled={healthLoading}>
                {healthLoading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Checking
                  </span>
                ) : (
                  "Refresh health"
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-280px)]">
        {/* LEFT: Menu */}
        <div
          className={`${
            leftCollapsed ? "lg:col-span-0 lg:hidden" : "lg:col-span-1"
          } space-y-4 overflow-y-auto pr-2 pb-10`}
        >
          {[...grouped.entries()]
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([cat, byGroup]) => (
              <div key={cat} className="space-y-2">
                <div className="flex items-center gap-2">
                  {iconForCategory(cat)}
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">{cat}</h2>
                  <span className="text-xs text-slate-400">
                    ({[...byGroup.values()].reduce((n, arr) => n + arr.length, 0)})
                  </span>
                </div>

                {[...byGroup.entries()]
                  .sort((a, b) => a[0].localeCompare(b[0]))
                  .map(([groupName, groupItems]) => (
                    <div key={groupName} className="space-y-2">
                      <div className="text-xs font-semibold text-slate-400 pl-1">{groupName}</div>
                      <div className="grid gap-2">
                        {groupItems.map((it) => {
                          const isSelected = selectedKey === it.key;
                          const isRunning = !!it.wiredToolId && activeToolId === it.wiredToolId;

                          return (
                            <div
                              key={it.key}
                              className={`rounded-lg border bg-white transition-all ${
                                isSelected ? "border-blue-400 shadow-sm" : "border-slate-200"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3 p-3">
                                <button
                                  onClick={() => setSelectedKey(it.key)}
                                  className="flex-1 text-left"
                                  disabled={activeToolId !== null}
                                >
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-semibold text-slate-800 text-sm">{it.title}</span>
                                    <WiringBadge wired={Boolean(it.wiredToolId)} hidden={!powerUser && Boolean(it.hiddenInNormalMode)} />
                                    <RiskBadge risk={it.risk} />
                                    <StatusBadge status={it.status} />
                                  </div>
                                  <div className="text-[11px] text-slate-400 font-mono mt-1 truncate">{it.path}</div>
                                  {it.desc ? (
                                    <div className={`text-xs text-slate-500 mt-1 ${clampLines(2)}`}>{it.desc}</div>
                                  ) : null}
                                </button>

                                <div className="flex flex-col gap-2 shrink-0">
                                  <Link
                                    href={docsHref(it.key)}
                                    className="inline-flex items-center justify-center gap-1 text-xs rounded-md border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50"
                                    onClick={() => setSelectedKey(it.key)}
                                  >
                                    Docs <ExternalLink className="w-3 h-3" />
                                  </Link>

                                  <Button
                                    size="sm"
                                    className="h-8 px-3"
                                    onClick={() => runTool(it)}
                                    disabled={activeToolId !== null || !it.wiredToolId}
                                    variant={it.risk === "heavy" ? "destructive" : "default"}
                                    title={it.wiredToolId ? "Run (backend-wired)" : "Run disabled (not in backend allowlist)"}
                                  >
                                    {isRunning ? (
                                      <span className="inline-flex items-center gap-2">
                                        <Loader2 className="w-4 h-4 animate-spin" /> Running
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-2">
                                        <Play className="w-4 h-4" /> Run
                                      </span>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
              </div>
            ))}
        </div>

        {/* RIGHT: Details + Console */}
        <div className={`${leftCollapsed ? "lg:col-span-3" : "lg:col-span-2"} flex flex-col h-full gap-4`}>
          {/* Details */}
          <Card className="border-slate-200">
            <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <button
                  className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-800"
                  title={leftCollapsed ? "Show tool list" : "Hide tool list"}
                  onClick={() => setLeftCollapsed((v) => !v)}
                >
                  {leftCollapsed ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                  <ChevronRight className={`w-4 h-4 transition-transform ${leftCollapsed ? "rotate-180" : ""}`} />
                </button>
                Selected Item
              </CardTitle>

              {selected ? (
                <Link
                  href={docsHref(selected.key)}
                  className="text-xs text-slate-600 hover:text-slate-900 inline-flex items-center gap-1"
                >
                  Jump to docs <ExternalLink className="w-3 h-3" />
                </Link>
              ) : (
                <span className="text-xs text-slate-400">None selected</span>
              )}
            </CardHeader>

            <CardContent className="px-4 pb-4 text-sm">
              {selected ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold">{selected.title}</span>
                    <WiringBadge wired={Boolean(selected.wiredToolId)} hidden={!powerUser && Boolean(selected.hiddenInNormalMode)} />
                    <RiskBadge risk={selected.risk} />
                    <StatusBadge status={selected.status} />
                    <span className="text-xs text-slate-500">
                      {selected.category} / {selected.group} • <span className="font-mono">{selected.kind}</span>
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="rounded-md border border-slate-200 p-3 bg-white">
                      <div className="text-xs text-slate-500 mb-1">Path</div>
                      <div className="font-mono text-xs break-all">{selected.path}</div>
                      <div className="mt-2 flex gap-2 flex-wrap">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => copyToClipboard(selected.path)}
                        >
                          <Copy className="w-3 h-3 mr-1" /> Copy
                        </Button>
                        {repoFileUrl(REPO_URL, selected.path) ? (
                          <a
                            href={repoFileUrl(REPO_URL, selected.path)}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs rounded-md border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50"
                          >
                            Open in Repo <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : null}
                      </div>
                    </div>

                    <div className="rounded-md border border-slate-200 p-3 bg-white">
                      <div className="text-xs text-slate-500 mb-1">Run (backend tool_id)</div>
                      <div className="font-mono text-xs flex items-center justify-between gap-2">
                        <span>{selected.wiredToolId ?? "—"}</span>
                        <button
                          className="text-slate-500 hover:text-slate-800 disabled:opacity-50"
                          onClick={() => selected.wiredToolId && copyToClipboard(selected.wiredToolId)}
                          disabled={!selected.wiredToolId}
                          title="Copy tool_id"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>

                      {!selected.wiredToolId ? (
                        <div className="mt-2 text-[11px] text-slate-500">
                          Not wired (not in backend allowlist). Enable <b>Power user (debug)</b> to browse inventory and decide what
                          to wire. (Guess: <span className="font-mono">{selected.toolIdGuess}</span>)
                        </div>
                      ) : (
                        <>
                          <div className="mt-2 text-[11px] text-slate-500">
                            Command preview: <span className="font-mono">{selected.commandPreview || "(unknown)"}</span>
                          </div>

                          <div className="mt-3">
                            <div className="text-xs text-slate-500 mb-1">Args (optional)</div>
                            <input
                              value={argsByToolId[selected.wiredToolId] || ""}
                              onChange={(e) =>
                                setArgsByToolId((prev) => ({
                                  ...prev,
                                  [selected.wiredToolId as string]: e.target.value,
                                }))
                              }
                              placeholder='e.g. --lang fr --dry-run'
                              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-blue-200"
                              disabled={activeToolId !== null}
                            />
                            <div className="mt-2 flex items-center gap-2 flex-wrap">
                              <Button
                                onClick={() => runTool(selected)}
                                disabled={activeToolId !== null}
                                variant={selected.risk === "heavy" ? "destructive" : "default"}
                                size="sm"
                                className="h-8"
                              >
                                {activeToolId === selected.wiredToolId ? (
                                  <span className="inline-flex items-center gap-2">
                                    <Loader2 className="w-4 h-4 animate-spin" /> Running
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-2">
                                    <Play className="w-4 h-4" /> Run selected
                                  </span>
                                )}
                              </Button>

                              <Button
                                variant="outline"
                                size="sm"
                                className="h-8"
                                onClick={() =>
                                  copyToClipboard(
                                    JSON.stringify(
                                      {
                                        tool_id: selected.wiredToolId,
                                        args: parseCliArgs(argsByToolId[selected.wiredToolId] || ""),
                                      },
                                      null,
                                      2
                                    )
                                  )
                                }
                                disabled={!selected.wiredToolId}
                              >
                                <Copy className="w-4 h-4 mr-1" /> Copy payload
                              </Button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {selected.desc ? <div className="text-slate-700">{selected.desc}</div> : null}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                      <div className="text-xs text-slate-500 mb-2">CLI equivalents</div>
                      <div className="space-y-1">
                        {selected.cli.map((cmd) => (
                          <div key={cmd} className="font-mono text-xs flex items-center justify-between gap-2">
                            <span className="truncate">{cmd}</span>
                            <button
                              className="text-slate-500 hover:text-slate-800"
                              onClick={() => copyToClipboard(cmd)}
                              title="Copy command"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                      <div className="text-xs text-slate-500 mb-2">Interface steps</div>
                      <div className="space-y-1">
                        {selected.uiSteps.map((n) => (
                          <div key={n} className="text-xs text-slate-700">
                            • {n}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-md border border-slate-200 p-3">
                    <div className="text-xs text-slate-500 mb-2">Notes</div>
                    <div className="space-y-1">
                      {selected.notes.map((n) => (
                        <div key={n} className="text-xs text-slate-700">
                          • {n}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="text-xs text-slate-500">
                    tool_id (guess): <span className="font-mono">{selected.toolIdGuess}</span>
                    {selected.wiredToolId ? (
                      <>
                        {" "}
                        • wired tool_id: <span className="font-mono">{selected.wiredToolId}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="text-slate-500 text-sm">Select an item from the left to view details.</div>
              )}
            </CardContent>
          </Card>

          {/* Console */}
          <Card className="flex-1 flex flex-col bg-slate-950 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="py-3 px-4 border-b border-slate-800 bg-slate-900/50 flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-slate-400" />
                <CardTitle className="text-xs font-mono uppercase tracking-widest text-slate-400">
                  Console Output
                </CardTitle>
              </div>
              <div className="flex items-center gap-3">
                {selectedToolId ? (
                  <span className="text-[10px] text-slate-500 font-mono">
                    active_tool: {activeToolId ?? "—"} • selected: {selectedToolId}
                  </span>
                ) : (
                  <span className="text-[10px] text-slate-500 font-mono">active_tool: {activeToolId ?? "—"}</span>
                )}

                <label className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                  <input
                    type="checkbox"
                    checked={autoScrollConsole}
                    onChange={(e) => setAutoScrollConsole(e.target.checked)}
                  />
                  autoscroll
                </label>

                {lastStatus === "success" && (
                  <span className="flex items-center gap-1 text-xs text-green-500">
                    <CheckCircle2 className="w-3 h-3" /> Success
                  </span>
                )}
                {lastStatus === "error" && (
                  <span className="flex items-center gap-1 text-xs text-red-500">
                    <XCircle className="w-3 h-3" /> Failed
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-slate-500 hover:text-slate-300"
                  onClick={() => setConsoleOutput("// Console cleared.")}
                >
                  Clear
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-slate-500 hover:text-slate-300"
                  onClick={() => copyToClipboard(consoleOutput)}
                  title="Copy console"
                >
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 p-0 relative group">
              <textarea
                ref={consoleRef}
                readOnly
                value={consoleOutput}
                className="w-full h-full bg-slate-950 text-slate-300 font-mono text-xs p-4 resize-none focus:outline-none scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent"
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* FULL REFERENCE (debug-only) */}
      {powerUser ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Info className="w-4 h-4 text-slate-500" />
              Reference (click to expand)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-slate-600">
              Every item below is linkable via its anchor. Use the left menu “Docs” button.
            </p>

            {[...grouped.entries()]
              .sort((a, b) => a[0].localeCompare(b[0]))
              .map(([cat, byGroup]) => (
                <div key={cat} className="space-y-2">
                  <div className="flex items-center gap-2">
                    {iconForCategory(cat)}
                    <h3 className="font-semibold text-slate-800">{cat}</h3>
                  </div>

                  {[...byGroup.entries()]
                    .sort((a, b) => a[0].localeCompare(b[0]))
                    .map(([groupName, groupItems]) => (
                      <div key={groupName} className="space-y-2 pl-2">
                        <div className="text-xs font-semibold text-slate-500">{groupName}</div>

                        <div className="space-y-2">
                          {groupItems.map((it) => (
                            <details key={it.key} id={it.key} className="rounded-lg border border-slate-200 bg-white">
                              <summary className="cursor-pointer select-none list-none px-4 py-3 flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-semibold text-sm text-slate-800">{it.title}</span>
                                  <WiringBadge
                                    wired={Boolean(it.wiredToolId)}
                                    hidden={!powerUser && Boolean(it.hiddenInNormalMode)}
                                  />
                                  <RiskBadge risk={it.risk} />
                                  <StatusBadge status={it.status} />
                                  <span className="font-mono text-[11px] text-slate-500">{it.path}</span>
                                </div>
                                <span className="text-xs text-slate-500">Expand</span>
                              </summary>

                              <div className="px-4 pb-4 pt-1 text-sm text-slate-700 space-y-3">
                                {it.desc ? <div className="text-slate-600">{it.desc}</div> : null}

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                                    <div className="text-xs text-slate-500 mb-1">tool_id</div>
                                    <div className="font-mono text-xs flex items-center justify-between gap-2">
                                      <span>{it.wiredToolId ?? "—"}</span>
                                      <button
                                        className="text-slate-500 hover:text-slate-800 disabled:opacity-50"
                                        onClick={() => it.wiredToolId && copyToClipboard(it.wiredToolId)}
                                        disabled={!it.wiredToolId}
                                        title="Copy tool_id"
                                      >
                                        <Copy className="w-3 h-3" />
                                      </button>
                                    </div>

                                    <div className="mt-2 flex gap-2 flex-wrap">
                                      <Button
                                        size="sm"
                                        onClick={() => runTool(it)}
                                        disabled={activeToolId !== null || !it.wiredToolId}
                                        variant={it.risk === "heavy" ? "destructive" : "default"}
                                        title={it.wiredToolId ? "Run (backend-wired)" : "Run disabled (not wired)"}
                                      >
                                        <Play className="w-4 h-4 mr-1" /> Run
                                      </Button>

                                      <Button variant="outline" size="sm" onClick={() => copyToClipboard(it.path)}>
                                        <Copy className="w-4 h-4 mr-1" /> Copy path
                                      </Button>

                                      {repoFileUrl(REPO_URL, it.path) ? (
                                        <a
                                          href={repoFileUrl(REPO_URL, it.path)}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="inline-flex items-center gap-1 text-xs rounded-md border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50"
                                        >
                                          Open in Repo <ExternalLink className="w-3 h-3" />
                                        </a>
                                      ) : null}
                                    </div>

                                    {it.wiredToolId ? (
                                      <div className="mt-3">
                                        <div className="text-xs text-slate-500 mb-1">Args</div>
                                        <input
                                          value={argsByToolId[it.wiredToolId] || ""}
                                          onChange={(e) =>
                                            setArgsByToolId((prev) => ({
                                              ...prev,
                                              [it.wiredToolId as string]: e.target.value,
                                            }))
                                          }
                                          placeholder='e.g. --lang fr --dry-run'
                                          className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-blue-200"
                                          disabled={activeToolId !== null}
                                        />
                                        <div className="mt-2 text-[11px] text-slate-500">
                                          Command preview:{" "}
                                          <span className="font-mono">{it.commandPreview || "(unknown)"}</span>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="mt-3 text-[11px] text-slate-500">
                                        tool_id guess: <span className="font-mono">{it.toolIdGuess}</span>
                                      </div>
                                    )}
                                  </div>

                                  <div className="rounded-md border border-slate-200 p-3 bg-slate-50">
                                    <div className="text-xs text-slate-500 mb-1">CLI</div>
                                    <div className="space-y-1">
                                      {it.cli.map((cmd) => (
                                        <div key={cmd} className="font-mono text-xs flex items-center justify-between gap-2">
                                          <span className="truncate">{cmd}</span>
                                          <button
                                            className="text-slate-500 hover:text-slate-800"
                                            onClick={() => copyToClipboard(cmd)}
                                            title="Copy command"
                                          >
                                            <Copy className="w-3 h-3" />
                                          </button>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div className="rounded-md border border-slate-200 p-3">
                                    <div className="text-xs text-slate-500 mb-2">Interface steps</div>
                                    <div className="space-y-1">
                                      {it.uiSteps.map((n) => (
                                        <div key={n} className="text-xs text-slate-700">
                                          • {n}
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <div className="rounded-md border border-slate-200 p-3">
                                    <div className="text-xs text-slate-500 mb-2">Notes</div>
                                    <div className="space-y-1">
                                      {it.notes.map((n) => (
                                        <div key={n} className="text-xs text-slate-700">
                                          • {n}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>

                                <div className="text-xs text-slate-500">
                                  Anchor:{" "}
                                  <Link className="font-mono underline" href={docsHref(it.key)}>
                                    {docsHref(it.key)}
                                  </Link>
                                </div>
                              </div>
                            </details>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
