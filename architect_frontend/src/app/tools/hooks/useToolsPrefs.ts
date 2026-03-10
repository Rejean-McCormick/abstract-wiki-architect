// architect_frontend/src/app/tools/hooks/useToolsPrefs.ts
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export const WORKFLOW_FILTER_VALUES = [
  "recommended",
  "languageIntegration",
  "lexiconWork",
  "buildMatrix",
  "qaValidation",
  "debugRecovery",
  "aiAssist",
  "all",
] as const;

export type WorkflowFilter = (typeof WORKFLOW_FILTER_VALUES)[number];

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
};

// Keep in sync with page.tsx / tools workflow UI
export const TOOLS_PREFS_STORAGE_KEY = "tools_dashboard_prefs_v3";

// Optional older keys you may have used previously
const LEGACY_KEYS = [
  "tools_dashboard_prefs_v2",
  "tools_dashboard_prefs_v1",
  "tools_dashboard_prefs",
] as const;

function safeJsonParse<T>(raw: string | null): { ok: true; value: T } | { ok: false; error: unknown } {
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

function isWorkflowFilter(v: unknown): v is WorkflowFilter {
  return typeof v === "string" && (WORKFLOW_FILTER_VALUES as readonly string[]).includes(v);
}

function coercePrefs(input: unknown, defaults: ToolsPrefs): ToolsPrefs {
  if (!isRecord(input)) return defaults;

  const out: ToolsPrefs = { ...defaults };

  if (isWorkflowFilter(input.workflowFilter)) {
    out.workflowFilter = input.workflowFilter;
  }

  (Object.keys(defaults) as (keyof ToolsPrefs)[]).forEach((k) => {
    if (k === "workflowFilter") return;
    const val = input[k];
    if (typeof val === "boolean") out[k] = val as ToolsPrefs[typeof k];
  });

  return out;
}

function readPrefsFromStorage(storageKey: string, defaults: ToolsPrefs): ToolsPrefs {
  if (typeof window === "undefined") return defaults;

  // 1) Current key
  const current = safeJsonParse<unknown>(window.localStorage.getItem(storageKey));
  if (current.ok) return coercePrefs(current.value, defaults);

  // 2) Migrate from legacy keys if present
  for (const k of LEGACY_KEYS) {
    const legacy = safeJsonParse<unknown>(window.localStorage.getItem(k));
    if (legacy.ok) {
      const merged = coercePrefs(legacy.value, defaults);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(merged));
      } catch {
        // ignore
      }
      return merged;
    }
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

  const defaults = useMemo<ToolsPrefs>(() => {
    const merged = { ...DEFAULT_PREFS, ...(options?.defaults ?? {}) };
    return {
      ...merged,
      workflowFilter: isWorkflowFilter(merged.workflowFilter)
        ? merged.workflowFilter
        : DEFAULT_PREFS.workflowFilter,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]); // treat key change like a “profile” change

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

    const ric = (window as any).requestIdleCallback as
      | ((cb: () => void, opts?: { timeout: number }) => number)
      | undefined;

    let handle: number | null = null;

    if (typeof ric === "function") {
      handle = ric(write, { timeout: 500 });
      return () => {
        cancelled = true;
        try {
          (window as any).cancelIdleCallback?.(handle);
        } catch {
          /* ignore */
        }
      };
    } else {
      handle = window.setTimeout(write, 0);
      return () => {
        cancelled = true;
        if (handle) window.clearTimeout(handle);
      };
    }
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