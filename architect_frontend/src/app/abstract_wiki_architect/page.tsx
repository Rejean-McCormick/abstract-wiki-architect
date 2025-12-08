// architect_frontend/src/app/abstract_wiki_architect/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { architectApi } from "@/lib/api";
import EntityList from "@/components/EntityList";
import CreateWorkspaceGrid from "./CreateWorkspaceGrid";
import { LanguageSelector } from "@/components/LanguageSelector";
import { Language } from "@/types/language";

export default function AbstractWikiArchitectHomePage() {
  // --- STATE ---
  // We manage the global language selection here.
  // Defaults to "eng" (English) or empty.
  const [selectedLangCode, setSelectedLangCode] = useState<string>("eng");
  
  // Frame types state
  const [frameTypes, setFrameTypes] = useState<any[]>([]);
  const [loadingFrames, setLoadingFrames] = useState(true);

  // --- EFFECTS ---
  useEffect(() => {
    async function loadData() {
      try {
        const frames = await architectApi.listFrameTypes();
        setFrameTypes(frames);
      } catch (e) {
        console.error("Failed to load frame types", e);
      } finally {
        setLoadingFrames(false);
      }
    }
    loadData();
  }, []);

  // --- HANDLERS ---
  const handleLanguageSelect = (lang: Language) => {
    setSelectedLangCode(lang.code);
    // Optional: Persist to localStorage or Context here
    console.log(`Global language set to: ${lang.name} (${lang.code})`);
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        {/* ------------------------------------------------------------------ */}
        {/* 1. Header & Controls                                               */}
        {/* ------------------------------------------------------------------ */}
        <header className="mb-10 flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <p className="text-[11px] font-mono uppercase tracking-[0.25em] text-slate-400">
              Abstract Wiki Architect
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">
              Start a new workspace
            </h1>
            <p className="max-w-xl text-sm text-slate-300">
              Pick a semantic frame to open a generation workspace. The selected 
              language will be applied to your new generation draft.
            </p>
          </div>

          {/* LANGUAGE SELECTOR INTEGRATION */}
          <div className="w-full md:w-64">
            <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-slate-500">
              Target Language
            </label>
            <LanguageSelector
              selectedCode={selectedLangCode}
              onSelect={handleLanguageSelect}
              className="w-full"
            />
          </div>
        </header>

        {/* ------------------------------------------------------------------ */}
        {/* 2. Workspace Grid (Passes Language Context)                        */}
        {/* ------------------------------------------------------------------ */}
        {loadingFrames ? (
          <div className="py-12 text-center text-slate-500 animate-pulse">
            Loading semantic frames...
          </div>
        ) : (
          <CreateWorkspaceGrid 
            frameTypes={frameTypes} 
            defaultLanguage={selectedLangCode} // Pass the selection down
          />
        )}

        {/* ------------------------------------------------------------------ */}
        {/* 3. Recent Work                                                     */}
        {/* ------------------------------------------------------------------ */}
        <section className="mt-12 rounded-xl border border-slate-800 bg-slate-900/20 p-6">
          <div className="mb-6 flex items-baseline justify-between">
            <h2 className="text-xl font-semibold tracking-tight text-slate-200">
              Recent Entities
            </h2>
          </div>

          <div className="bg-slate-50 rounded-lg p-4 text-slate-900">
            <EntityList />
          </div>
        </section>
      </div>
    </main>
  );
}