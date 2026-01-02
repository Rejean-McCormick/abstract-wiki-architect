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
  Ban,
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

// Visualizer
import ASTViewer from "@/components/tools/ASTViewer";

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------
type HealthReady = {
  broker?: string;
  storage?: string;
  engine?: string;
};

type ToolRunEvent = {
  ts: string;
  level: string;
  step: string;
  message: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: Record<string, any>;
};

type ToolRunTruncation = {
  stdout: boolean;
  stderr: boolean;
  limit_chars: number;
};

type ToolRunArgsRejected = {
  arg: string;
  reason: string;
};

type ToolSummary = {
  id: string;
  label: string;
  description: string;
  timeout_sec: number;
};

type ToolRunResponse = {
  trace_id: string;
  success: boolean;
  command: string;
  // legacy compat
  output?: string;
  error?: string;

  stdout: string;
  stderr: string;
  stdout_chars: number;
  stderr_chars: number;

  exit_code: number;
  duration_ms: number;
  started_at: string;
  ended_at: string;

  cwd: string;
  repo_root: string;
  tool: ToolSummary;

  args_received: string[];
  args_accepted: string[];
  args_rejected: ToolRunArgsRejected[];

  truncation: ToolRunTruncation;
  events: ToolRunEvent[];
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
  wiredToolId?: string;
  toolIdGuess: string;
  commandPreview?: string;
  hiddenInNormalMode?: boolean;
};

const TOOL_ID_BY_PATH: Record<string, string> = Object.fromEntries(
  Object.entries(BACKEND_TOOL_REGISTRY).map(([toolId, meta]) => [meta.path, toolId])
);

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
// Local persistence
// ----------------------------------------------------------------------------
const LS_PREFS_KEY = "tools_dashboard_prefs_v2";
const LS_ARGS_KEY = "tools_dashboard_args_v1";

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
  if (n <= 1) return "line-clamp-1";
  if (n === 2) return "line-clamp-2";
  if (n === 3) return "line-clamp-3";
  return "line-clamp-4";
}

function safeJsonParse<T>(s: string): { ok: true; value: T } | { ok: false; error: unknown } {
  try {
    return { ok: true, value: JSON.parse(s) as T };
  } catch (e) {
    return { ok: false, error: e };
  }
}

function normalizeToolRunResponse(
  toolId: string,
  rawText: string,
  parsed: ToolRunResponse | null,
  httpMeta?: { ok: boolean; status: number; statusText: string }
): ToolRunResponse {
  // If we got a parsed object, ensure required fields exist.
  if (parsed) {
    return {
      trace_id: parsed.trace_id ?? "",
      success: Boolean(parsed.success),
      command: parsed.command ?? "",
      output: parsed.output,
      error: parsed.error,

      stdout: parsed.stdout ?? "",
      stderr: parsed.stderr ?? "",
      stdout_chars: Number.isFinite(parsed.stdout_chars) ? parsed.stdout_chars : (parsed.stdout?.length ?? 0),
      stderr_chars: Number.isFinite(parsed.stderr_chars) ? parsed.stderr_chars : (parsed.stderr?.length ?? 0),

      exit_code: Number.isFinite(parsed.exit_code) ? parsed.exit_code : (parsed.success ? 0 : -1),
      duration_ms: Number.isFinite(parsed.duration_ms) ? parsed.duration_ms : 0,
      started_at: parsed.started_at ?? "",
      ended_at: parsed.ended_at ?? "",

      cwd: parsed.cwd ?? "",
      repo_root: parsed.repo_root ?? "",
      tool: parsed.tool ?? { id: toolId, label: "", description: "", timeout_sec: 0 },

      args_received: parsed.args_received ?? [],
      args_accepted: parsed.args_accepted ?? [],
      args_rejected: parsed.args_rejected ?? [],

      truncation: parsed.truncation ?? { stdout: false, stderr: false, limit_chars: 0 },
      events: parsed.events ?? [],
    };
  }

  // If parsing failed, present a structured error.
  const httpLine = httpMeta
    ? `HTTP ${httpMeta.status} ${httpMeta.statusText}${httpMeta.ok ? "" : " (non-2xx)"}`
    : "HTTP (unknown)";

  return {
    trace_id: "",
    success: false,
    command: "",
    output: "",
    error: `${httpLine}\n\n${rawText || "(empty response)"}`,

    stdout: "",
    stderr: rawText || "",
    stdout_chars: 0,
    stderr_chars: rawText?.length ?? 0,

    exit_code: -1,
    duration_ms: 0,
    started_at: "",
    ended_at: "",

    cwd: "",
    repo_root: "",
    tool: { id: toolId, label: "", description: "", timeout_sec: 0 },

    args_received: [],
    args_accepted: [],
    args_rejected: [],

    truncation: { stdout: false, stderr: false, limit_chars: 0 },
    events: [],
  };
}

function formatEventTime(ts: string) {
  // keep lightweight and stable
  const t = ts.split("T")[1] || ts;
  return t.replace("Z", "");
}

function appendConsoleBlock(
  prev: string,
  block: string | string[],
  opts?: { leadingBlank?: boolean }
) {
  const lines = Array.isArray(block) ? block : [block];
  const prefix = opts?.leadingBlank ? "\n" : "";
  return prev + prefix + lines.join("\n");
}

// ----------------------------------------------------------------------------
// Page
// ----------------------------------------------------------------------------
export default function ToolsDashboard() {
  const [activeToolId, setActiveToolId] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const [consoleOutput, setConsoleOutput] = useState<string>(() => {
    return (
      `// Tools Command Center\n` +
      `// Inventory v${INVENTORY.version} (generated ${INVENTORY.generated_on})\n` +
      `// API: ${API_V1}\n` +
      `// Normal mode shows only backend-wired runnable tools.\n` +
      `// Enable Power user (debug) to reveal the full inventory.\n`
    );
  });

  const [lastStatus, setLastStatus] = useState<"success" | "error" | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  // Visualizer State
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [visualData, setVisualData] = useState<any>(null);

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

  // Capture the last full response object for "Copy JSON Bundle"
  const [lastResponseJson, setLastResponseJson] = useState<string | null>(null);

  // Abort running tool
  const runAbortRef = useRef<AbortController | null>(null);

  // ----------------------------------------------------------------------------
  // Load persisted prefs
  // ----------------------------------------------------------------------------
  useEffect(() => {
    try {
      const prefsRaw = localStorage.getItem(LS_PREFS_KEY);
      if (prefsRaw) {
        const parsed = safeJsonParse<{
          powerUser?: boolean;
          showLegacy?: boolean;
          showTests?: boolean;
          showInternal?: boolean;
          wiredOnly?: boolean;
          showHeavy?: boolean;
          leftCollapsed?: boolean;
          autoScrollConsole?: boolean;
        }>(prefsRaw);
        if (parsed.ok && parsed.value) {
          setPowerUser(Boolean(parsed.value.powerUser));
          if (typeof parsed.value.showLegacy === "boolean") setShowLegacy(parsed.value.showLegacy);
          if (typeof parsed.value.showTests === "boolean") setShowTests(parsed.value.showTests);
          if (typeof parsed.value.showInternal === "boolean") setShowInternal(parsed.value.showInternal);
          if (typeof parsed.value.wiredOnly === "boolean") setWiredOnly(parsed.value.wiredOnly);
          if (typeof parsed.value.showHeavy === "boolean") setShowHeavy(parsed.value.showHeavy);
          if (typeof parsed.value.leftCollapsed === "boolean") setLeftCollapsed(parsed.value.leftCollapsed);
          if (typeof parsed.value.autoScrollConsole === "boolean")
            setAutoScrollConsole(parsed.value.autoScrollConsole);
        }
      }

      const argsRaw = localStorage.getItem(LS_ARGS_KEY);
      if (argsRaw) {
        const parsedArgs = safeJsonParse<Record<string, string>>(argsRaw);
        if (parsedArgs.ok && parsedArgs.value) {
          setArgsByToolId(parsedArgs.value);
        }
      }
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist prefs
  useEffect(() => {
    try {
      localStorage.setItem(
        LS_PREFS_KEY,
        JSON.stringify(
          {
            powerUser,
            showLegacy,
            showTests,
            showInternal,
            wiredOnly,
            showHeavy,
            leftCollapsed,
            autoScrollConsole,
          },
          null,
          0
        )
      );
    } catch {
      // ignore
    }
  }, [powerUser, showLegacy, showTests, showInternal, wiredOnly, showHeavy, leftCollapsed, autoScrollConsole]);

  // Persist args
  useEffect(() => {
    try {
      localStorage.setItem(LS_ARGS_KEY, JSON.stringify(argsByToolId, null, 0));
    } catch {
      // ignore
    }
  }, [argsByToolId]);

  // ----------------------------------------------------------------------------
  // Health
  // ----------------------------------------------------------------------------
  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    const controller = new AbortController();
    try {
      const res = await fetch(`${API_V1}/health/ready`, {
        cache: "no-store",
        signal: controller.signal,
      });
      const data = (await res.json()) as HealthReady;
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  // Auto-scroll console to bottom on output changes (opt-out)
  useEffect(() => {
    if (!autoScrollConsole) return;
    const el = consoleRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [consoleOutput, autoScrollConsole]);

  // ----------------------------------------------------------------------------
  // Inventory -> items (deduped paths)
  // ----------------------------------------------------------------------------
  const items: ToolItem[] = useMemo(() => {
    const allPaths: string[] = [];
    const seen = new Set<string>();

    const addMany = (arr?: readonly string[] | string[]) => {
      if (!arr) return;
      for (const p of arr) {
        if (!p) continue;
        if (seen.has(p)) continue;
        seen.add(p);
        allPaths.push(p);
      }
    };

    addMany(INVENTORY.root_entrypoints as readonly string[]);
    addMany(INVENTORY.gf as readonly string[]);
    addMany(INVENTORY.tools.root || []);
    addMany(INVENTORY.tools.everything_matrix || []);
    addMany(INVENTORY.tools.qa || []);
    addMany(INVENTORY.tools.debug || []);
    addMany(INVENTORY.tools.health || []);
    addMany(INVENTORY.tools.lexicon || []);

    addMany(INVENTORY.scripts.root || []);
    addMany(INVENTORY.scripts.lexicon || []);
    addMany(INVENTORY.utils as readonly string[]);
    addMany(INVENTORY.ai_services as readonly string[]);
    addMany(INVENTORY.nlg as readonly string[]);
    addMany(INVENTORY.prototypes as readonly string[]);
    addMany(INVENTORY.tests.root || []);
    addMany(INVENTORY.tests.http_api_legacy || []);
    addMany(INVENTORY.tests.adapters_core_integration || []);

    const out: ToolItem[] = [];

    // 1) Build items from inventory (repo browsing)
    for (const path of allPaths) {
      const cls = classify(INVENTORY.root_entrypoints as readonly string[], path);
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
          : path === "builder/orchestrator.py"
          ? ["python builder/orchestrator.py", "python manage.py build"]
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
        status, // ✅ fixed (previously duplicated)
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

  // ----------------------------------------------------------------------------
  // Filtering (deferred search)
  // ----------------------------------------------------------------------------
  const filteredItems = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();

    const effectiveWiredOnly = powerUser ? wiredOnly : true;
    const effectiveShowLegacy = powerUser ? showLegacy : false;
    const effectiveShowTests = powerUser ? showTests : false;
    const effectiveShowInternal = powerUser ? showInternal : false;

    // ✅ Important: in normal mode, DO NOT silently hide heavy tools
    const effectiveShowHeavy = powerUser ? showHeavy : true;

    return items.filter((it) => {
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
        (it.wiredToolId ? it.wiredToolId.toLowerCase().includes(q) : false)
      );
    });
  }, [items, deferredQuery, powerUser, showLegacy, showTests, showInternal, wiredOnly, showHeavy]);

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

  useEffect(() => {
    if (!selectedKey) return;
    const stillVisible = filteredItems.some((x) => x.key === selectedKey);
    if (!stillVisible) setSelectedKey(null);
  }, [filteredItems, selectedKey]);

  const wiredCount = useMemo(() => items.filter((x) => Boolean(x.wiredToolId)).length, [items]);
  const visibleCount = filteredItems.length;

  // ----------------------------------------------------------------------------
  // Run tooling
  // ----------------------------------------------------------------------------
  const cancelRun = useCallback(() => {
    if (runAbortRef.current) {
      runAbortRef.current.abort();
      runAbortRef.current = null;
      setConsoleOutput((prev) =>
        appendConsoleBlock(prev, ["", "[CANCEL] Abort requested by user."], { leadingBlank: true })
      );
    }
  }, []);

  const runTool = useCallback(
    async (it: ToolItem) => {
      const toolId = it.wiredToolId;
      if (!toolId) return;

      // Reset Visualizer
      setVisualData(null);

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

      // Abort any previous run (shouldn’t happen, but keeps state sane)
      if (runAbortRef.current) runAbortRef.current.abort();
      const controller = new AbortController();
      runAbortRef.current = controller;

      setActiveToolId(toolId);
      setLastStatus(null);
      setLastResponseJson(null);

      setConsoleOutput((prev) =>
        appendConsoleBlock(
          prev,
          [
            "",
            `> Executing: ${it.title}`,
            `  tool_id=${toolId}`,
            `  args=${args.join(" ")}`,
            `----------------------------------------`,
          ],
          { leadingBlank: true }
        )
      );

      const startedAt = performance.now();

      try {
        const res = await fetch(`${API_V1}/tools/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool_id: toolId, args }),
          cache: "no-store",
          signal: controller.signal,
        });

        const httpMeta = { ok: res.ok, status: res.status, statusText: res.statusText };
        const rawText = await res.text();

        const parsedTry = safeJsonParse<ToolRunResponse>(rawText);
        const normalized = normalizeToolRunResponse(
          toolId,
          rawText,
          parsedTry.ok ? parsedTry.value : null,
          httpMeta
        );

        setLastResponseJson(JSON.stringify(normalized, null, 2));

        const durationMs = Math.max(0, Math.round(performance.now() - startedAt));

        if (normalized.success) {
          setLastStatus("success");
          setConsoleOutput((prev) => {
            const lines: string[] = [];
            lines.push(`[TRACE] ${normalized.trace_id}`);
            lines.push(
              `[TIME]  Started: ${normalized.started_at || "(server)"} | Client duration: ${durationMs}ms | Server: ${
                normalized.duration_ms
              }ms`
            );

            if (normalized.events && normalized.events.length > 0) {
              lines.push(`\n[LIFECYCLE]`);
              normalized.events.forEach((e) => {
                lines.push(`  ${formatEventTime(e.ts)} [${e.level}] ${e.step}: ${e.message}`);
              });
            }

            if (normalized.args_rejected && normalized.args_rejected.length > 0) {
              lines.push(`\n[WARN] Rejected Arguments:`);
              normalized.args_rejected.forEach((r) => lines.push(`  - ${r.arg}: ${r.reason}`));
            }

            if (normalized.stdout) {
              lines.push(`\n[STDOUT] (${normalized.stdout_chars} chars)`);
              lines.push(normalized.stdout);
              if (normalized.truncation?.stdout) lines.push("... [TRUNCATED]");
            }

            if (normalized.stderr) {
              lines.push(`\n[STDERR] (${normalized.stderr_chars} chars)`);
              lines.push(normalized.stderr);
              if (normalized.truncation?.stderr) lines.push("... [TRUNCATED]");
            }

            lines.push(`\n[SUCCESS] exit_code=${normalized.exit_code}`);
            return appendConsoleBlock(prev, lines, { leadingBlank: true });
          });

          // Visualizer Logic (prefer stdout; fallback to output)
          const outputJson = normalized.stdout || normalized.output;
          if (toolId === "visualize_ast" && outputJson) {
            const visTry = safeJsonParse<any>(outputJson);
            if (visTry.ok && visTry.value) {
              const tree = visTry.value.tree ?? visTry.value.ast ?? null;
              if (tree) setVisualData(tree);
            } else {
              // don’t fail the run; just log
              setConsoleOutput((prev) =>
                appendConsoleBlock(prev, ["", "[AST] Could not parse visualizer JSON output."], {
                  leadingBlank: true,
                })
              );
            }
          }
        } else {
          setLastStatus("error");
          setConsoleOutput((prev) => {
            const lines: string[] = [];
            lines.push(`[TRACE] ${normalized.trace_id || "(none)"}`);
            lines.push(`[FAILED] exit_code=${normalized.exit_code}`);

            if (normalized.events && normalized.events.length > 0) {
              lines.push(`\n[LIFECYCLE]`);
              normalized.events.forEach((e) => {
                lines.push(`  ${formatEventTime(e.ts)} [${e.level}] ${e.step}: ${e.message}`);
              });
            }

            if (normalized.stdout) {
              lines.push(`\n[STDOUT]`);
              lines.push(normalized.stdout);
            }

            const errText = normalized.stderr || normalized.error || "Unknown Error";
            lines.push(`\n[STDERR]`);
            lines.push(errText);

            return appendConsoleBlock(prev, lines, { leadingBlank: true });
          });
        }
      } catch (e: any) {
        if (e?.name === "AbortError") {
          setLastStatus("error");
          setConsoleOutput((prev) =>
            appendConsoleBlock(prev, ["", "[ABORTED] Request cancelled."], { leadingBlank: true })
          );
        } else {
          setLastStatus("error");
          setConsoleOutput((prev) =>
            appendConsoleBlock(prev, [``, `[NETWORK ERROR]: ${e?.message || String(e)}`], {
              leadingBlank: true,
            })
          );
        }
      } finally {
        // Only clear if we are still the active controller
        runAbortRef.current = null;
        setActiveToolId(null);
      }
    },
    [argsByToolId]
  );

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
                    <input
                      type="checkbox"
                      checked={wiredOnly}
                      onChange={(e) => setWiredOnly(e.target.checked)}
                    />
                    Wired only
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showLegacy}
                      onChange={(e) => setShowLegacy(e.target.checked)}
                    />
                    Show legacy
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={showTests}
                      onChange={(e) => setShowTests(e.target.checked)}
                    />
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
                    <input
                      type="checkbox"
                      checked={showHeavy}
                      onChange={(e) => setShowHeavy(e.target.checked)}
                    />
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
                                  type="button"
                                  onClick={() => setSelectedKey(it.key)}
                                  className="flex-1 text-left"
                                  disabled={activeToolId !== null}
                                >
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-semibold text-slate-800 text-sm">{it.title}</span>
                                    <WiringBadge
                                      wired={Boolean(it.wiredToolId)}
                                      hidden={!powerUser && Boolean(it.hiddenInNormalMode)}
                                    />
                                    <RiskBadge risk={it.risk} />
                                    <StatusBadge status={it.status} />
                                  </div>
                                  <div className="text-[11px] text-slate-400 font-mono mt-1 truncate">
                                    {it.path}
                                  </div>
                                  {it.desc ? (
                                    <div className={`text-xs text-slate-500 mt-1 ${clampLines(2)}`}>
                                      {it.desc}
                                    </div>
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
                                    title={
                                      it.wiredToolId
                                        ? "Run (backend-wired)"
                                        : "Run disabled (not in backend allowlist)"
                                    }
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
                  type="button"
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
                    <WiringBadge
                      wired={Boolean(selected.wiredToolId)}
                      hidden={!powerUser && Boolean(selected.hiddenInNormalMode)}
                    />
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
                          type="button"
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
                            Command preview:{" "}
                            <span className="font-mono">{selected.commandPreview || "(unknown)"}</span>
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
                              type="button"
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
          <Card className="flex-1 flex flex-col bg-slate-950 border-slate-800 shadow-2xl overflow-hidden min-h-[400px]">
            <CardHeader className="py-3 px-4 border-b border-slate-800 bg-slate-900/50 flex flex-row items-center justify-between shrink-0">
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
                  <span className="text-[10px] text-slate-500 font-mono">
                    active_tool: {activeToolId ?? "—"}
                  </span>
                )}

                <label className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                  <input
                    type="checkbox"
                    checked={autoScrollConsole}
                    onChange={(e) => setAutoScrollConsole(e.target.checked)}
                  />
                  autoscroll
                </label>

                {activeToolId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[10px] text-amber-500 hover:text-amber-300"
                    onClick={cancelRun}
                    title="Cancel the in-flight run request"
                  >
                    <Ban className="w-3 h-3 mr-1" /> Cancel
                  </Button>
                )}

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
                  onClick={() => {
                    setConsoleOutput("// Console cleared.\n");
                    setVisualData(null);
                    setLastResponseJson(null);
                    setLastStatus(null);
                  }}
                >
                  Clear
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-slate-500 hover:text-slate-300"
                  onClick={() => copyToClipboard(consoleOutput)}
                  title="Copy console text"
                >
                  Copy Text
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-sky-500 hover:text-sky-300"
                  onClick={() => lastResponseJson && copyToClipboard(lastResponseJson)}
                  disabled={!lastResponseJson}
                  title="Copy full JSON response object for debugging"
                >
                  Copy JSON Bundle
                </Button>
              </div>
            </CardHeader>

            <CardContent className="flex-1 p-0 relative group flex flex-col min-h-0">
              {/* AST Visualizer Overlay */}
              {visualData && (
                <div className="border-b border-slate-800 bg-white relative shrink-0 h-[500px] overflow-hidden">
                  <div className="absolute top-2 right-2 z-10 flex gap-2">
                    <div className="bg-slate-800 text-white text-[10px] px-2 py-1 rounded opacity-80 pointer-events-none">
                      Interactive Visualizer Active
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs bg-white text-slate-800 border-slate-300 hover:bg-slate-100"
                      onClick={() => setVisualData(null)}
                    >
                      Close Visualizer
                    </Button>
                  </div>
                  <ASTViewer data={visualData} height={500} />
                </div>
              )}

              <textarea
                ref={consoleRef}
                readOnly
                value={consoleOutput}
                className="w-full flex-1 bg-slate-950 text-slate-300 font-mono text-xs p-4 resize-none focus:outline-none scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent min-h-[100px]"
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
                                        type="button"
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
                                            type="button"
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
