// architect_frontend/src/app/tools/components/ToolConsolePanel.tsx
"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Terminal,
  Clock,
  AlertTriangle,
  FileText,
  AlertOctagon,
  Copy,
  AlignLeft,
  List,
  Hash,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { ToolRunResponse, ToolRunEvent } from "../types";
import { formatBytes, formatDuration, formatTime, copyToClipboard } from "../utils";

interface ToolConsolePanelProps {
  /** The final structured response (null while running) */
  response: ToolRunResponse | null;

  /** Real-time text log accumulation (for legacy tools or active running state) */
  realtimeLog: string;

  isRunning: boolean;
  toolId?: string;
  onClear?: () => void;
}

function downloadText(filename: string, content: string) {
  try {
    const blob = new Blob([content ?? ""], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch {
    // If the browser blocks this, user can still copy.
  }
}

export default function ToolConsolePanel({
  response,
  realtimeLog,
  isRunning,
  toolId,
  onClear,
}: ToolConsolePanelProps) {
  const [activeTab, setActiveTab] = useState("console");
  const scrollRef = useRef<HTMLDivElement>(null);

  const safeEvents = useMemo<ToolRunEvent[]>(() => response?.events ?? [], [response]);
  const stdout = response?.stdout ?? response?.output ?? "";
  const stderr = response?.stderr ?? response?.error ?? "";
  const stdoutChars =
    typeof response?.stdout_chars === "number" ? response.stdout_chars : (stdout?.length ?? 0);
  const stderrChars =
    typeof response?.stderr_chars === "number" ? response.stderr_chars : (stderr?.length ?? 0);
  const truncStdout = Boolean(response?.truncation?.stdout);
  const truncStderr = Boolean(response?.truncation?.stderr);

  // Auto-switch tabs based on state
  useEffect(() => {
    if (isRunning) {
      setActiveTab("console");
      return;
    }
    if (!response) return;

    // Prefer stderr if failed or stderr non-empty; else stdout if non-empty; else events if present; else meta.
    if (!response.success || stderrChars > 0) {
      setActiveTab("stderr");
    } else if (stdoutChars > 0) {
      setActiveTab("stdout");
    } else if ((response.events?.length ?? 0) > 0) {
      setActiveTab("events");
    } else {
      setActiveTab("meta");
    }
  }, [isRunning, response, stdoutChars, stderrChars]);

  // Auto-scroll the raw console
  useEffect(() => {
    if (activeTab === "console" && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [realtimeLog, activeTab]);

  const handleCopyBundle = () => {
    // Copy a richer bundle than just the response (helps debug the UI too).
    const bundle = {
      tool_id: toolId ?? null,
      is_running: isRunning,
      active_tab: activeTab,
      realtime_log: realtimeLog,
      response,
    };
    copyToClipboard(JSON.stringify(bundle, null, 2));
  };

  // --- RENDERERS ---

  const renderTimeline = (events: ToolRunEvent[]) => (
    <div className="space-y-3 p-4 font-mono text-xs">
      {events.length === 0 && <div className="text-slate-500 italic">No events recorded.</div>}
      {events.map((e, i) => {
        const level = (e.level || "").toUpperCase();
        const isErr = level === "ERROR";
        const isWarn = level === "WARN" || level === "WARNING";
        return (
          <div key={i} className="flex gap-3 group">
            <div className="w-20 text-slate-500 shrink-0 text-right select-none">
              {e.ts ? formatTime(e.ts) : "—"}
            </div>
            <div
              className={`
                shrink-0 w-16 text-center font-bold rounded-sm px-1 py-0.5 h-fit
                ${
                  isErr
                    ? "bg-red-900/30 text-red-400"
                    : isWarn
                    ? "bg-amber-900/30 text-amber-400"
                    : "bg-slate-800 text-slate-400"
                }
              `}
            >
              {level || "INFO"}
            </div>
            <div className="flex-1 space-y-1">
              <div className="font-semibold text-slate-300">{e.step || "step"}</div>
              <div className="text-slate-400 leading-relaxed">{e.message || ""}</div>
              {e.data && Object.keys(e.data).length > 0 && (
                <pre className="mt-1 bg-slate-900 p-2 rounded border border-slate-800 text-[10px] text-slate-500 overflow-x-auto">
                  {JSON.stringify(e.data, null, 2)}
                </pre>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  const renderStream = (content: string, size: number, truncated: boolean, streamName: string) => (
    <div className="flex flex-col h-full relative">
      <div className="absolute top-2 right-4 flex items-center gap-2 z-10">
        <span className="text-[10px] text-slate-500 font-mono">{formatBytes(size)}</span>

        <Button
          variant="outline"
          size="sm"
          className="h-6 text-[10px]"
          onClick={() => downloadText(`${toolId || "tool"}_${streamName.toLowerCase()}.txt`, content)}
          title={`Download ${streamName}`}
        >
          <Download className="w-3 h-3 mr-1" /> Download
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="h-6 text-[10px]"
          onClick={() => copyToClipboard(content)}
          title={`Copy ${streamName}`}
        >
          <Copy className="w-3 h-3 mr-1" /> Copy
        </Button>
      </div>

      {truncated && (
        <div className="bg-amber-950/30 border-b border-amber-900/50 p-2 text-center text-amber-500 text-xs font-medium">
          ⚠️ Output truncated. {streamName} exceeded limit.
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs whitespace-pre-wrap break-all text-slate-300 selection:bg-blue-500/30">
        {content || <span className="text-slate-600 italic">top of stream (empty)</span>}
      </div>
    </div>
  );

  const renderMeta = (res: ToolRunResponse) => (
    <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
      <div className="space-y-4">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            Context
          </h4>
          <div className="bg-slate-900 rounded p-3 space-y-2 border border-slate-800 font-mono text-xs">
            <div className="flex justify-between gap-3">
              <span className="text-slate-500 shrink-0">Trace ID:</span>
              <span className="text-slate-300 select-all break-all">{res.trace_id || "—"}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500 shrink-0">Exit Code:</span>
              <span className={res.exit_code === 0 ? "text-green-400" : "text-red-400"}>
                {typeof res.exit_code === "number" ? res.exit_code : "—"}
              </span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-slate-500 shrink-0">Duration:</span>
              <span className="text-slate-300">
                {typeof res.duration_ms === "number" ? formatDuration(res.duration_ms) : "—"}
              </span>
            </div>
            <div className="pt-2 border-t border-slate-800">
              <span className="text-slate-500 block mb-1">CWD:</span>
              <div className="text-slate-300 break-all">{res.cwd || "—"}</div>
            </div>
          </div>
        </div>

        {res.args_rejected && res.args_rejected.length > 0 && (
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-red-400 mb-2 flex items-center gap-2">
              <AlertTriangle className="w-3 h-3" /> Arguments Rejected
            </h4>
            <div className="bg-red-950/20 rounded border border-red-900/50 overflow-hidden">
              {res.args_rejected.map((r, i) => (
                <div key={i} className="p-2 border-b border-red-900/30 last:border-0 text-xs">
                  <span className="font-mono text-red-300 bg-red-900/40 px-1 rounded">
                    {r.arg}
                  </span>
                  <span className="text-red-400 ml-2">{r.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            Command
          </h4>
          <pre className="bg-slate-950 p-3 rounded border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap break-all">
            {res.command || "—"}
          </pre>
        </div>

        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
            Arguments Received
          </h4>
          <div className="flex flex-wrap gap-1">
            {(res.args_received || []).map((a, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400"
              >
                {a}
              </span>
            ))}
            {(res.args_received || []).length === 0 && (
              <span className="text-xs text-slate-600 italic">None</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col rounded-lg border border-slate-800 bg-slate-950 text-slate-200 shadow-2xl overflow-hidden h-[600px]">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-900/50 px-4 py-3 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Terminal className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            {toolId || "Console"}
          </span>

          {response && (
            <Badge
              variant={response.success ? "default" : "destructive"}
              className={`text-[10px] h-5 ${
                response.success ? "bg-green-900 text-green-300 hover:bg-green-800" : ""
              }`}
            >
              {response.success ? "SUCCESS" : "FAILED"}
            </Badge>
          )}

          {isRunning && (
            <span className="flex items-center gap-2 px-2 py-0.5 rounded bg-blue-900/30 text-blue-400 text-[10px] animate-pulse font-medium">
              <Clock className="w-3 h-3" /> Executing
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {(response || realtimeLog) && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-slate-500 hover:text-slate-300 gap-1.5"
              onClick={handleCopyBundle}
              title="Copy a JSON bundle (response + realtime log + UI state)"
            >
              <Hash className="w-3 h-3" /> Copy Debug Bundle
            </Button>
          )}
          {onClear && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-slate-500 hover:text-slate-300"
              onClick={onClear}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Content Area */}
      {response ? (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
          <div className="px-4 border-b border-slate-800 bg-slate-900/20">
            <TabsList className="bg-transparent h-9 p-0 gap-4">
              <TabsTrigger
                value="events"
                className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-blue-500 data-[state=active]:text-blue-400 rounded-none px-0 pb-2 text-slate-500 text-xs font-medium uppercase tracking-wide gap-2"
              >
                <List className="w-3.5 h-3.5" /> Timeline
                <span className="bg-slate-800 text-slate-400 rounded-full px-1.5 py-0.5 text-[9px]">
                  {safeEvents.length}
                </span>
              </TabsTrigger>

              <TabsTrigger
                value="stdout"
                className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-emerald-500 data-[state=active]:text-emerald-400 rounded-none px-0 pb-2 text-slate-500 text-xs font-medium uppercase tracking-wide gap-2"
              >
                <AlignLeft className="w-3.5 h-3.5" /> Stdout
                {stdoutChars > 0 && (
                  <span className="bg-slate-800 text-slate-400 rounded-full px-1.5 py-0.5 text-[9px]">
                    {formatBytes(stdoutChars, 0)}
                  </span>
                )}
              </TabsTrigger>

              <TabsTrigger
                value="stderr"
                className={`data-[state=active]:bg-transparent data-[state=active]:border-b-2 rounded-none px-0 pb-2 text-xs font-medium uppercase tracking-wide gap-2 ${
                  stderrChars > 0 || !response.success
                    ? "text-amber-500 data-[state=active]:border-amber-500 data-[state=active]:text-amber-400"
                    : "text-slate-500 data-[state=active]:border-slate-500 data-[state=active]:text-slate-300"
                }`}
              >
                <AlertOctagon className="w-3.5 h-3.5" /> Stderr
                {stderrChars > 0 && (
                  <span className="bg-amber-900/40 text-amber-500 rounded-full px-1.5 py-0.5 text-[9px]">
                    {formatBytes(stderrChars, 0)}
                  </span>
                )}
              </TabsTrigger>

              <TabsTrigger
                value="meta"
                className="data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-purple-500 data-[state=active]:text-purple-400 rounded-none px-0 pb-2 text-slate-500 text-xs font-medium uppercase tracking-wide gap-2"
              >
                <FileText className="w-3.5 h-3.5" /> Meta
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="flex-1 min-h-0 bg-slate-950">
            <TabsContent value="events" className="h-full overflow-y-auto m-0">
              {renderTimeline(safeEvents)}
            </TabsContent>
            <TabsContent value="stdout" className="h-full m-0">
              {renderStream(stdout, stdoutChars, truncStdout, "STDOUT")}
            </TabsContent>
            <TabsContent value="stderr" className="h-full m-0">
              {renderStream(stderr, stderrChars, truncStderr, "STDERR")}
            </TabsContent>
            <TabsContent value="meta" className="h-full overflow-y-auto m-0">
              {renderMeta(response)}
            </TabsContent>
          </div>
        </Tabs>
      ) : (
        // Fallback / Active State (Simple Log View)
        <div className="flex-1 flex flex-col min-h-0">
          <div className="bg-slate-900/20 border-b border-slate-800 px-4 py-2 flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-slate-600">Raw Stream</span>
            {isRunning && <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>}
          </div>
          <div
            ref={scrollRef}
            className="flex-1 p-4 font-mono text-xs whitespace-pre-wrap text-slate-300 overflow-y-auto"
          >
            {realtimeLog || <span className="text-slate-600 italic">// Waiting for output...</span>}
          </div>
        </div>
      )}
    </div>
  );
}
