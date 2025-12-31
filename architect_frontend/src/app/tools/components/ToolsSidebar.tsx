// architect_frontend/src/app/tools/components/ToolsSidebar.tsx
"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { ExternalLink, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

import type { ToolItem } from "../types";
import { docsHref } from "../utils";
import { RiskBadge, StatusBadge, WiringBadge } from "./Badges";
import { iconForCategory } from "./icons";

interface ToolsSidebarProps {
  grouped: Map<string, Map<string, ToolItem[]>>;
  selectedKey: string | null;
  setSelectedKey: (k: string) => void;
  activeToolId: string | null;
  runTool: (it: ToolItem) => void;
  disabled?: boolean;
}

export function ToolsSidebar(props: ToolsSidebarProps) {
  const { grouped, selectedKey, setSelectedKey, activeToolId, runTool, disabled } = props;

  const categoryEntries = useMemo(
    () => [...grouped.entries()].sort((a, b) => a[0].localeCompare(b[0])),
    [grouped]
  );

  return (
    <div className="space-y-4 overflow-y-auto pr-2 pb-10 h-full">
      {categoryEntries.map(([cat, byGroup]) => {
        const groupEntries = [...byGroup.entries()].sort((a, b) => a[0].localeCompare(b[0]));
        const catCount = [...byGroup.values()].reduce((n, arr) => n + arr.length, 0);

        return (
          <div key={cat} className="space-y-2">
            {/* Category Header */}
            <div className="flex items-center gap-2 sticky top-0 bg-white/90 backdrop-blur-sm z-10 py-1">
              {iconForCategory(cat)}
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">{cat}</h2>
              <span className="text-xs text-slate-400">({catCount})</span>
            </div>

            {groupEntries.map(([groupName, groupItems]) => (
              <div key={groupName} className="space-y-2">
                <div className="text-xs font-semibold text-slate-400 pl-1">{groupName}</div>

                <div className="grid gap-2">
                  {groupItems.map((it) => {
                    const isSelected = selectedKey === it.key;
                    const isRunning = !!it.wiredToolId && activeToolId === it.wiredToolId;
                    const isGlobalDisabled = Boolean(disabled) || (activeToolId !== null && !isRunning);

                    return (
                      <div
                        key={it.key}
                        className={`group relative rounded-lg border bg-white transition-all ${
                          isSelected ? "border-blue-400 shadow-md ring-1 ring-blue-100" : "border-slate-200 hover:border-slate-300"
                        } ${isGlobalDisabled ? "opacity-60" : ""}`}
                      >
                        <div className="flex items-start justify-between gap-3 p-3">
                          
                          {/* Selection Area: Title & Description */}
                          <div
                            role="button"
                            tabIndex={isGlobalDisabled ? -1 : 0}
                            onClick={() => {
                              if (!isGlobalDisabled) setSelectedKey(it.key);
                            }}
                            onKeyDown={(e) => {
                              if (!isGlobalDisabled && (e.key === 'Enter' || e.key === ' ')) {
                                e.preventDefault();
                                setSelectedKey(it.key);
                              }
                            }}
                            className={`flex-1 text-left cursor-pointer outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-400 rounded-sm ${
                              isGlobalDisabled ? "pointer-events-none" : ""
                            }`}
                          >
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-semibold text-slate-800 text-sm">{it.title}</span>
                              <WiringBadge wired={Boolean(it.wiredToolId)} hidden={Boolean(it.hidden)} />
                              <RiskBadge risk={it.risk} />
                              <StatusBadge status={it.status} />
                            </div>

                            <div className="text-[11px] text-slate-400 font-mono mt-1 truncate max-w-[200px]" title={it.path}>
                              {it.path}
                            </div>

                            {it.desc ? (
                              <div className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                                {it.desc}
                              </div>
                            ) : null}
                          </div>

                          {/* Actions Area: Docs & Run */}
                          <div className="flex flex-col gap-2 shrink-0 z-10" onClick={(e) => e.stopPropagation()}>
                            <Link
                              href={docsHref(it.key)}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => {
                                // Optional: Select on documentation click? Usually better to just open docs.
                                e.stopPropagation(); 
                              }}
                              className="inline-flex items-center justify-center gap-1 text-xs rounded-md border border-slate-200 px-2 py-1 text-slate-600 hover:bg-slate-50 hover:text-blue-600 transition-colors"
                            >
                              Docs <ExternalLink className="w-3 h-3" />
                            </Link>

                            <Button
                              size="sm"
                              className="h-8 px-3 text-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                runTool(it);
                              }}
                              disabled={activeToolId !== null || !it.wiredToolId}
                              variant={it.risk === "heavy" ? "destructive" : "default"}
                              title={it.wiredToolId ? "Run (backend-wired)" : "Run disabled (not in backend allowlist)"}
                            >
                              {isRunning ? (
                                <span className="inline-flex items-center gap-2">
                                  <Loader2 className="w-3 h-3 animate-spin" /> Running
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-2">
                                  <Play className="w-3 h-3" /> Run
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
        );
      })}
    </div>
  );
}

export default ToolsSidebar;