// architect_frontend/src/app/tools/components/ToolsToolbar.tsx
"use client";

import React from "react";
import { 
  Search, 
  Filter, 
  Activity, 
  RefreshCw, 
  Server, 
  Database, 
  Cpu, 
  Settings2
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import type { HealthReady } from "../types";

// --- Sub-components ---

function StatusIndicator({ 
  label, 
  value, 
  icon: Icon 
}: { 
  label: string; 
  value?: string; 
  icon: React.ElementType 
}) {
  const v = (value || "").toLowerCase();
  const ok = ["ok", "ready", "up", "healthy"].includes(v);
  const bad = ["down", "unhealthy", "error", "fail"].includes(v);
  
  let colorClass = "bg-slate-200 text-slate-500";
  if (ok) colorClass = "bg-emerald-100 text-emerald-700 border-emerald-200";
  else if (bad) colorClass = "bg-red-100 text-red-700 border-red-200";
  else if (v) colorClass = "bg-amber-100 text-amber-700 border-amber-200";

  return (
    <div 
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md border text-[10px] font-medium uppercase tracking-wide transition-colors ${colorClass}`}
      title={`${label}: ${value ?? "unknown"}`}
    >
      <Icon className="w-3 h-3" />
      <span className="hidden sm:inline">{label}</span>
      {v && <span className="font-bold border-l pl-1.5 ml-0.5 border-current/20">{v}</span>}
    </div>
  );
}

// --- Main Component ---

interface ToolsToolbarProps {
  apiBase: string;
  repoUrl?: string;

  query: string;
  setQuery: (v: string) => void;

  powerUser: boolean;
  setPowerUser: (v: boolean) => void;

  // advanced filters
  wiredOnly: boolean;
  setWiredOnly: (v: boolean) => void;
  showLegacy: boolean;
  setShowLegacy: (v: boolean) => void;
  showTests: boolean;
  setShowTests: (v: boolean) => void;
  showInternal: boolean;
  setShowInternal: (v: boolean) => void;

  visibleCount: number;
  totalCount: number;
  wiredCount: number;

  health: HealthReady | null;
  healthLoading: boolean;
  refreshHealth: () => void;
}

export function ToolsToolbar(props: ToolsToolbarProps) {
  const {
    apiBase,
    repoUrl,
    query,
    setQuery,
    powerUser,
    setPowerUser,
    wiredOnly,
    setWiredOnly,
    showLegacy,
    setShowLegacy,
    showTests,
    setShowTests,
    showInternal,
    setShowInternal,
    visibleCount,
    totalCount,
    wiredCount,
    health,
    healthLoading,
    refreshHealth,
  } = props;

  return (
    <Card className="border-slate-200 shadow-sm bg-white">
      <CardContent className="p-3 space-y-3">
        
        {/* Top Row: Search & Mode Toggle */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tools by name, path, category, or ID..."
              className="w-full h-9 rounded-md border border-slate-200 pl-9 pr-3 text-sm outline-none placeholder:text-slate-400 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-all"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <label 
              className={`
                flex items-center gap-2 text-xs font-medium px-3 py-2 rounded-md border cursor-pointer select-none transition-colors
                ${powerUser 
                  ? "bg-blue-50 border-blue-200 text-blue-700" 
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                }
              `}
            >
              <input 
                type="checkbox" 
                checked={powerUser} 
                onChange={(e) => setPowerUser(e.target.checked)} 
                className="accent-blue-600"
              />
              <Settings2 className="w-3.5 h-3.5" />
              Power User
            </label>
          </div>
        </div>

        {/* Middle Row: Advanced Filters (Conditional) */}
        {powerUser && (
          <div className="flex flex-wrap items-center gap-2 p-2 bg-slate-50/50 rounded-md border border-slate-100 animate-in fade-in slide-in-from-top-1 duration-200">
            <div className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1 pr-2 border-r border-slate-200 mr-1">
              <Filter className="w-3 h-3" /> Filters
            </div>
            
            {[
              { label: "Wired Only", checked: wiredOnly, set: setWiredOnly },
              { label: "Show Legacy", checked: showLegacy, set: setShowLegacy },
              { label: "Show Tests", checked: showTests, set: setShowTests },
              { label: "Show Internal", checked: showInternal, set: setShowInternal },
            ].map((f) => (
              <label 
                key={f.label} 
                className="flex items-center gap-1.5 text-xs text-slate-600 bg-white px-2 py-1 rounded border border-slate-200 hover:border-slate-300 cursor-pointer select-none"
              >
                <input 
                  type="checkbox" 
                  checked={f.checked} 
                  onChange={(e) => f.set(e.target.checked)} 
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-600/20"
                />
                {f.label}
              </label>
            ))}
          </div>
        )}

        {/* Bottom Row: Stats & Health */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pt-1">
          
          {/* Stats */}
          <div className="text-xs text-slate-500 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span title={apiBase}>
              API: <span className="font-mono text-slate-700">{new URL(apiBase).host}</span>
            </span>
            <span className="text-slate-300">|</span>
            <span>
              Visible: <span className="font-mono font-medium text-slate-700">{visibleCount}</span>
              <span className="text-slate-400 mx-0.5">/</span>
              {totalCount}
            </span>
            <span className="text-slate-300">|</span>
            <span title="Tools explicitly wired to backend">
              Wired: <span className="font-mono font-medium text-slate-700">{wiredCount}</span>
            </span>
            
            {!repoUrl && (
              <>
                <span className="text-slate-300">|</span>
                <span className="text-amber-600 flex items-center gap-1">
                   Repo URL missing
                </span>
              </>
            )}
          </div>

          {/* Health */}
          <div className="flex items-center gap-2 w-full md:w-auto justify-end">
            <div className="flex items-center gap-1.5">
              <StatusIndicator label="Broker" value={health?.broker} icon={Server} />
              <StatusIndicator label="DB" value={health?.storage} icon={Database} />
              <StatusIndicator label="Eng" value={health?.engine} icon={Cpu} />
            </div>

            <Button 
              variant="ghost" 
              size="icon" 
              className="h-7 w-7 text-slate-400 hover:text-blue-600" 
              onClick={refreshHealth} 
              disabled={healthLoading}
              title="Refresh System Health"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? "animate-spin text-blue-600" : ""}`} />
            </Button>
          </div>
        </div>

      </CardContent>
    </Card>
  );
}

export default ToolsToolbar;