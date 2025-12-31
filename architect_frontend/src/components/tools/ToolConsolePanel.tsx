import React, { useEffect, useRef } from 'react';

interface ToolConsolePanelProps {
  output: string;
  isRunning: boolean;
  toolId?: string;
  onClear?: () => void;
}

export default function ToolConsolePanel({ 
  output, 
  isRunning, 
  toolId,
  onClear 
}: ToolConsolePanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when output updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [output]);

  if (!output && !isRunning) {
    return null;
  }

  return (
    <div className="mt-4 flex flex-col rounded-lg border border-slate-700 bg-slate-950 text-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-900 px-3 py-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Console Output
          </span>
          {toolId && (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium text-slate-400 font-mono">
              {toolId}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {isRunning && (
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </span>
              <span className="text-xs font-medium text-emerald-400">Running...</span>
            </div>
          )}
          
          {onClear && output && (
            <button 
              onClick={onClear}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
              disabled={isRunning}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Output Area */}
      <div 
        ref={scrollRef}
        className="h-64 overflow-y-auto p-3 font-mono text-sm leading-relaxed whitespace-pre-wrap break-all"
      >
        {output ? (
          output
        ) : (
          <span className="text-slate-600 italic">...</span>
        )}
      </div>
    </div>
  );
}