// architect_frontend/src/app/abstract_wiki_architect/page.tsx

import React from "react";
import { architectApi } from "@/lib/api";
import EntityList from "@/components/EntityList";
import CreateWorkspaceGrid from "./CreateWorkspaceGrid"; // Extracted Client Component

export const dynamic = "force-dynamic"; // Ensure we fetch fresh data on navigation

// Derive the frame types list type from the API helper
type FrameTypeList = Awaited<ReturnType<typeof architectApi.listFrameTypes>>;

export default async function AbstractWikiArchitectHomePage() {
  let frameTypes: FrameTypeList = [];
  try {
    frameTypes = await architectApi.listFrameTypes();
  } catch (e) {
    console.error("Failed to load frame types", e);
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        {/* ------------------------------------------------------------------ */}
        {/* 1. Header & Templates                                              */}
        {/* ------------------------------------------------------------------ */}
        <header className="mb-10 space-y-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.25em] text-slate-400">
            Abstract Wiki Architect
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Start a new workspace
          </h1>
          <p className="max-w-3xl text-sm text-slate-300">
            Pick a semantic frame to open a generation workspace. Each frame
            has its own dedicated form, defaults, and language options.
          </p>
        </header>

        {/* Dynamic Frame Grid (Client Component for Interactivity) */}
        <CreateWorkspaceGrid frameTypes={frameTypes} />

        {/* ------------------------------------------------------------------ */}
        {/* 2. Recent Work (The new EntityList)                                */}
        {/* ------------------------------------------------------------------ */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/20 p-6">
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
