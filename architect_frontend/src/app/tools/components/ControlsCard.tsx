// architect_frontend/src/app/tools/components/ControlsCard.tsx
"use client";

import React, { memo, useCallback, useMemo } from "react";
import {
  Info,
  Search,
  Filter,
  PlugZap,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  GitBranch,
  ListChecks,
} from "lucide-react";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type HealthReady = {
  broker?: string;
  storage?: string;
  engine?: string;
};

export type ControlsFilters = {
  wiredOnly: boolean;
  showLegacy: boolean;
  showTests: boolean;
  showInternal: boolean;
  showHeavy: boolean;
};

export type WorkflowFilter =
  | "recommended"
  | "language_integration"
  | "lexicon_work"
  | "build_matrix"
  | "qa_validation"
  | "debug_recovery"
  | "ai_assist"
  | "all";

export type WorkflowOption = {
  value: WorkflowFilter;
  label: string;
};

export type WorkflowGuide = {
  title: string;
  summary?: string;
  steps: string[];
};

type ControlsCardProps = {
  apiV1: string;
  repoUrl?: string;

  visibleCount: number;
  totalCount: number;
  wiredCount: number;

  query: string;
  onQueryChange: (value: string) => void;

  workflow: WorkflowFilter;
  workflowOptions: readonly WorkflowOption[];
  onWorkflowChange: (value: WorkflowFilter) => void;
  workflowGuide?: WorkflowGuide | null;

  powerUser: boolean;
  onPowerUserChange: (value: boolean) => void;

  filters: ControlsFilters;
  onFilterChange: <K extends keyof ControlsFilters>(key: K, value: ControlsFilters[K]) => void;

  health: HealthReady | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
};

function classifyHealth(value?: string) {
  const v = (value || "").toLowerCase();
  const ok = v === "ok" || v === "ready" || v === "up" || v === "healthy";
  const bad = v === "down" || v === "unhealthy" || v === "error" || v === "fail";
  return { ok, bad, v: value ?? "unknown" };
}

const HealthPill = memo(function HealthPill({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  const cls = useMemo(() => classifyHealth(value), [value]);

  return (
    <span className="inline-flex items-center gap-1 text-xs">
      {cls.ok ? (
        <CheckCircle2 className="w-3 h-3 text-green-500" />
      ) : cls.bad ? (
        <XCircle className="w-3 h-3 text-red-500" />
      ) : (
        <AlertTriangle className="w-3 h-3 text-amber-500" />
      )}
      <span className="text-slate-600">{label}:</span>
      <span className="font-mono text-slate-700">{cls.v}</span>
    </span>
  );
});

function FilterToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-600">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

const WorkflowGuideCard = memo(function WorkflowGuideCard({
  workflowGuide,
}: {
  workflowGuide?: WorkflowGuide | null;
}) {
  if (!workflowGuide) return null;

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-3">
      <div className="flex items-start gap-2">
        <GitBranch className="mt-0.5 h-4 w-4 text-blue-600" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">{workflowGuide.title}</div>
          {workflowGuide.summary ? (
            <div className="mt-1 text-xs text-slate-600">{workflowGuide.summary}</div>
          ) : null}
        </div>
      </div>

      {workflowGuide.steps.length > 0 ? (
        <div className="mt-3 flex items-start gap-2">
          <ListChecks className="mt-0.5 h-4 w-4 text-slate-500" />
          <ol className="space-y-1 text-sm text-slate-700">
            {workflowGuide.steps.map((step, idx) => (
              <li key={`${idx}-${step}`} className="flex gap-2">
                <span className="w-5 shrink-0 text-slate-400">{idx + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
});

export const ControlsCard = memo(function ControlsCard(props: ControlsCardProps) {
  const {
    apiV1,
    repoUrl,

    visibleCount,
    totalCount,
    wiredCount,

    query,
    onQueryChange,

    workflow,
    workflowOptions,
    onWorkflowChange,
    workflowGuide,

    powerUser,
    onPowerUserChange,

    filters,
    onFilterChange,

    health,
    healthLoading,
    onRefreshHealth,
  } = props;

  const onSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => onQueryChange(e.target.value),
    [onQueryChange]
  );

  const setFilter = useCallback(
    <K extends keyof ControlsFilters>(key: K) =>
      (value: ControlsFilters[K]) =>
        onFilterChange(key, value),
    [onFilterChange]
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Info className="w-4 h-4 text-slate-500" />
          Interface
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
          <div className="xl:col-span-5">
            <div className="text-xs text-slate-500 mb-1 flex items-center gap-2">
              <Search className="w-3 h-3" />
              Search
            </div>
            <input
              value={query}
              onChange={onSearch}
              placeholder="Search by name, path, category, tool_id…"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-200"
            />
          </div>

          <div className="xl:col-span-3">
            <div className="text-xs text-slate-500 mb-1 flex items-center gap-2">
              <GitBranch className="w-3 h-3" />
              Workflow / Tool Set
            </div>
            <Select value={workflow} onValueChange={(value) => onWorkflowChange(value as WorkflowFilter)}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a workflow" />
              </SelectTrigger>
              <SelectContent>
                {workflowOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="xl:col-span-4 flex items-end gap-3 flex-wrap">
            <label className="flex items-center gap-2 text-sm text-slate-700 font-medium">
              <input
                type="checkbox"
                checked={powerUser}
                onChange={(e) => onPowerUserChange(e.target.checked)}
              />
              Power user (debug)
            </label>

            {powerUser ? (
              <div className="flex items-center gap-3 flex-wrap">
                <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                  <Filter className="w-3 h-3" /> Filters:
                </span>

                <FilterToggle
                  label="Wired only"
                  checked={filters.wiredOnly}
                  onChange={setFilter("wiredOnly")}
                />
                <FilterToggle
                  label="Show legacy"
                  checked={filters.showLegacy}
                  onChange={setFilter("showLegacy")}
                />
                <FilterToggle
                  label="Show tests"
                  checked={filters.showTests}
                  onChange={setFilter("showTests")}
                />
                <FilterToggle
                  label="Show internal"
                  checked={filters.showInternal}
                  onChange={setFilter("showInternal")}
                />
                <FilterToggle
                  label="Show heavy"
                  checked={filters.showHeavy}
                  onChange={setFilter("showHeavy")}
                />
              </div>
            ) : (
              <span className="text-xs text-slate-400">(advanced filters hidden)</span>
            )}
          </div>
        </div>

        <WorkflowGuideCard workflowGuide={workflowGuide} />

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs text-slate-500">
            API: <span className="font-mono">{apiV1}</span> • Visible:{" "}
            <span className="font-mono">{visibleCount}</span> /{" "}
            <span className="font-mono">{totalCount}</span> • Wired tools:{" "}
            <span className="font-mono">{wiredCount}</span>
            {repoUrl ? (
              <>
                {" "}
                • Repo: <span className="font-mono">{repoUrl}</span>
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
              <HealthPill label="broker" value={health?.broker} />
              <HealthPill label="storage" value={health?.storage} />
              <HealthPill label="engine" value={health?.engine} />
            </span>

            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={onRefreshHealth}
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
  );
});

export default ControlsCard;