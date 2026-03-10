// architect_frontend/src/app/tools/hooks/useToolsPrefs.ts
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export const WORKFLOW_FILTER_VALUES = [
  "recommended",
  "language_integration",
  "lexicon_work",
  "build_matrix",
  "qa_validation",
  "debug_recovery",
  "ai_assist",
  "all",
] as const;

export type WorkflowFilter = (typeof WORKFLOW_FILTER_VALUES)[number];

const LEGACY_WORKFLOW_ALIASES: Readonly<Record<string, WorkflowFilter>> = Object.freeze({
  recommended: "recommended",
  languageIntegration: "language_integration",
  lexiconWork: "lexicon_work",
  buildMatrix: "build_matrix",
  qaValidation: "qa_validation",
  debugRecovery: "debug_recovery",
  aiAssist: "ai_assist",
  all: "all",
});

export type ToolsPrefs = {
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

const DEFAULT_PREFS: ToolsPrefs = {
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
};

// Keep in sync with page.tsx / tools workflow UI
export const TOOLS_PREFS_STORAGE_KEY = "tools_dashboard_prefs_v4";

// Optional older keys you may have used previously
const LEGACY_KEYS = [
  "tools_dashboard_prefs_v3",
  "tools_dashboard_prefs_v2",
  "tools_dashboard_prefs_v1",
  "tools_dashboard_prefs",
] as const;

function safeJsonParse<T>(
  raw: string | null
): { ok: true; value: T } | { ok: false; error: unknown } {
  if (!raw) return { ok: false, error: new Error("empty") };
  try {
    return { ok: true, value: JSON.parse(raw) as T };
  } catch (e) {
    return { ok: false, error: e };
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function normalizeWorkflowFilter(v: unknown): WorkflowFilter | null {
  if (typeof v !== "string") return null;

  if ((WORKFLOW_FILTER_VALUES as readonly string[]).includes(v)) {
    return v as WorkflowFilter;
  }

  return LEGACY_WORKFLOW_ALIASES[v] ?? null;
}

function isWorkflowFilter(v: unknown): v is WorkflowFilter {
  return normalizeWorkflowFilter(v) !== null;
}

function coercePrefs(input: unknown, defaults: ToolsPrefs): ToolsPrefs {
  if (!isRecord(input)) return defaults;

  const out: ToolsPrefs = { ...defaults };

  const normalizedWorkflow = normalizeWorkflowFilter(input.workflowFilter);
  if (normalizedWorkflow) {
    out.workflowFilter = normalizedWorkflow;
  }

  (Object.keys(defaults) as (keyof ToolsPrefs)[]).forEach((k) => {
    if (k === "workflowFilter") return;
    const val = input[k];
    if (typeof val === "boolean") {
      out[k] = val as ToolsPrefs[typeof k];
    }
  });

  return out;
}

function readPrefsFromStorage(storageKey: string, defaults: ToolsPrefs): ToolsPrefs {
  if (typeof window === "undefined") return defaults;

  const keysToTry = [storageKey, ...LEGACY_KEYS.filter((k) => k !== storageKey)];

  for (const key of keysToTry) {
    const parsed = safeJsonParse<unknown>(window.localStorage.getItem(key));
    if (!parsed.ok) continue;

    const merged = coercePrefs(parsed.value, defaults);

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(merged));
    } catch {
      // ignore
    }

    return merged;
  }

  return defaults;
}

type UseToolsPrefsOptions = {
  storageKey?: string;
  defaults?: Partial<ToolsPrefs>;
};

type BooleanPrefKey = {
  [K in keyof ToolsPrefs]: ToolsPrefs[K] extends boolean ? K : never;
}[keyof ToolsPrefs];

export function useToolsPrefs(options?: UseToolsPrefsOptions) {
  const storageKey = options?.storageKey ?? TOOLS_PREFS_STORAGE_KEY;
  const defaultsOverride = options?.defaults;

  const defaults = useMemo<ToolsPrefs>(() => {
    const merged = { ...DEFAULT_PREFS, ...(defaultsOverride ?? {}) };

    return {
      ...merged,
      workflowFilter: isWorkflowFilter(merged.workflowFilter)
        ? merged.workflowFilter
        : DEFAULT_PREFS.workflowFilter,
    };
  }, [storageKey, defaultsOverride]);

  const [isLoaded, setIsLoaded] = useState(false);
  const [prefs, setPrefs] = useState<ToolsPrefs>(() => defaults);

  // Load on mount (and when storageKey/defaults change)
  useEffect(() => {
    const loaded = readPrefsFromStorage(storageKey, defaults);
    setPrefs(loaded);
    setIsLoaded(true);
  }, [storageKey, defaults]);

  // Persist (throttled + avoids identical writes)
  const lastSerializedRef = useRef<string>("");

  useEffect(() => {
    if (!isLoaded) return;
    if (typeof window === "undefined") return;

    const serialized = JSON.stringify(prefs);
    if (serialized === lastSerializedRef.current) return;

    let cancelled = false;

    const write = () => {
      if (cancelled) return;
      try {
        window.localStorage.setItem(storageKey, serialized);
        lastSerializedRef.current = serialized;
      } catch {
        // ignore (private mode/quota)
      }
    };

    const ric = (window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
      cancelIdleCallback?: (handle: number) => void;
    }).requestIdleCallback;

    let handle: number | null = null;

    if (typeof ric === "function") {
      handle = ric(write, { timeout: 500 });
      return () => {
        cancelled = true;
        try {
          (window as Window & {
            cancelIdleCallback?: (id: number) => void;
          }).cancelIdleCallback?.(handle!);
        } catch {
          // ignore
        }
      };
    }

    handle = window.setTimeout(write, 0);
    return () => {
      cancelled = true;
      if (handle !== null) window.clearTimeout(handle);
    };
  }, [prefs, storageKey, isLoaded]);

  const setPref = useCallback(<K extends keyof ToolsPrefs>(key: K, value: ToolsPrefs[K]) => {
    setPrefs((prev) => (prev[key] === value ? prev : { ...prev, [key]: value }));
  }, []);

  const togglePref = useCallback(<K extends BooleanPrefKey>(key: K) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const resetPrefs = useCallback(() => {
    setPrefs(defaults);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(storageKey);
      } catch {
        // ignore
      }
    }
  }, [defaults, storageKey]);

  return {
    prefs,
    setPrefs,
    setPref,
    togglePref,
    resetPrefs,
    isLoaded,
  } as const;
}