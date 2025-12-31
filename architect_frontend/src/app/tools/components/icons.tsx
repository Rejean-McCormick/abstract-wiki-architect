// architect_frontend/src/app/tools/components/icons.tsx
"use client";

import React from "react";
import {
  Terminal,
  Database,
  Cpu,
  ShieldCheck,
  Wrench,
  Bot,
  Beaker,
  FileText,
  Layers,
  Activity,
  Hammer,
  Sparkles,
  FlaskConical,
} from "lucide-react";

/**
 * Category -> icon mapping.
 * Keep this centralized so category renames don’t require touching page layout.
 */
export const iconForCategory = (category: string) => {
  const c = (category || "").toLowerCase();

  // Diagnostics / maintenance / health
  if (c.includes("diagnostic") || c.includes("maintenance") || c.includes("health") || c.includes("cleanup")) {
    return <Activity className="w-4 h-4 text-blue-600" />;
  }

  // Build system / compilation
  if (c.includes("build") || c.includes("compile") || c.includes("gf")) {
    return <Cpu className="w-4 h-4 text-purple-600" />;
  }

  // Lexicon / data / schema / indexing
  if (c.includes("lexicon") || c.includes("data") || c.includes("schema") || c.includes("index")) {
    return <Database className="w-4 h-4 text-amber-600" />;
  }

  // QA / tests
  if (c.includes("qa") || c.includes("test")) {
    return <ShieldCheck className="w-4 h-4 text-green-600" />;
  }

  // AI tooling
  if (c.includes("ai")) {
    return <Bot className="w-4 h-4 text-pink-600" />;
  }

  // Prototypes / demos / experiments
  if (c.includes("demo") || c.includes("prototype") || c.includes("experiment")) {
    return <Beaker className="w-4 h-4 text-purple-600" />;
  }

  // Libraries / internal utilities
  if (c.includes("libraries") || c.includes("library")) {
    return <Layers className="w-4 h-4 text-slate-700" />;
  }

  // Launch surfaces / entrypoints
  if (c.includes("launch") || c.includes("entry")) {
    return <Terminal className="w-4 h-4 text-slate-600" />;
  }

  // Generic tools bucket
  if (c === "tools" || c.includes("tool")) {
    return <Wrench className="w-4 h-4 text-slate-700" />;
  }

  // Fallback
  return <FileText className="w-4 h-4 text-slate-500" />;
};
