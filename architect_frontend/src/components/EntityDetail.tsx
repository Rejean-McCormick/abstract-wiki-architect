// architect_frontend/src/components/EntityDetail.tsx
"use client";

import React, { useEffect, useState, useCallback } from "react";
import { architectApi, type Entity, type GenerationResult as GenerationResultData } from "../lib/api";
import AIPanel from "./AIPanel";
import GenerationResult from "./GenerationResult";

interface EntityDetailProps {
  id: string; // Passed from the Next.js page params
}

export default function EntityDetail({ id }: EntityDetailProps) {
  // --- Data State ---
  const [entity, setEntity] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Editor State ---
  const [localPayload, setLocalPayload] = useState<Record<string, unknown>>({});
  const [payloadString, setPayloadString] = useState("{}");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // --- Generation State ---
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<GenerationResultData | null>(null);

  // --- Fetch Data ---
  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await architectApi.getEntity(id);
        setEntity(data);

        // Initialize editor with current payload
        const initialPayload = data.frame_payload || {};
        setLocalPayload(initialPayload);
        setPayloadString(JSON.stringify(initialPayload, null, 2));
      } catch (e) {
        console.error("Failed to load entity", e);
        setError("Could not load entity. It may not exist or the backend is down.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  // --- Handlers ---
   
  // 1. Handle manual text edits in the JSON box
  const handleJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newVal = e.target.value;
    setPayloadString(newVal);
    try {
      const parsed = JSON.parse(newVal);
      setLocalPayload(parsed);
      setJsonError(null);
    } catch (err) {
      setJsonError("Invalid JSON");
    }
  };

  // 2. Save changes to backend
  const handleSave = async () => {
    if (!entity) return;
    if (jsonError) {
      alert("Please fix JSON errors before saving.");
      return;
    }

    setSaving(true);
    try {
      const updated = await architectApi.updateEntity(id, {
        frame_payload: localPayload,
        // We could also update name/description here if we added fields for them
      });
      setEntity(updated);
      alert("Saved successfully!");
    } catch (e) {
      console.error(e);
      alert("Failed to save changes.");
    } finally {
      setSaving(false);
    }
  };

  // 3. Handle AI Suggestions (Apply Patch)
  const handleAISuggestion = useCallback((newPayload: Record<string, unknown>) => {
    setLocalPayload((prev) => {
      const merged = { ...prev, ...newPayload };
      setPayloadString(JSON.stringify(merged, null, 2));
      return merged;
    });
    setJsonError(null);
  }, []);

  // 4. Handle Generate Preview
  const handleGenerate = async () => {
    if (!entity) return;
    if (jsonError) {
      alert("Please fix JSON errors before generating.");
      return;
    }

    setGenerating(true);
    setGenResult(null);

    try {
      // Calls the /generate endpoint with the current *unsaved* payload
      // allowing the user to test edits immediately.
      const result = await architectApi.generate({
        lang: entity.lang,
        frame_type: entity.frame_type || "generic",
        frame_payload: localPayload,
      });
      setGenResult(result);
    } catch (e) {
      console.error("Generation failed", e);
      alert("Generation failed. See console for details.");
    } finally {
      setGenerating(false);
    }
  };

  // --- Render ---

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        Loading entity editor...
      </div>
    );
  }

  if (error || !entity) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        {error || "Entity not found."}
      </div>
    );
  }

  const created = entity.created_at
    ? new Date(entity.created_at).toLocaleString()
    : "—";
  const updated = entity.updated_at
    ? new Date(entity.updated_at).toLocaleString()
    : "—";

  return (
    <div className="flex flex-col gap-6">
      {/* ------------------------------------------------------------------ */}
      {/* 1. Header & Metadata                                               */}
      {/* ------------------------------------------------------------------ */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">{entity.name}</h1>
            
            {/* Metadata Badges */}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              {entity.frame_type && (
                <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 font-medium text-slate-700">
                  Type: {entity.frame_type}
                </span>
              )}
              {entity.lang && (
                <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 font-medium text-slate-700">
                  Lang: {entity.lang}
                </span>
              )}
              {entity.tags && entity.tags.length > 0 && (
                 <>
                   <span className="text-slate-300">|</span>
                   {entity.tags.map(tag => (
                     <span key={tag} className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                       #{tag}
                     </span>
                   ))}
                 </>
              )}
            </div>
          </div>

          {/* Timestamps & Actions */}
          <div className="flex flex-col items-end gap-3">
             <div className="text-right text-xs text-slate-500">
              <div><span className="font-medium">Created:</span> {created}</div>
              <div><span className="font-medium">Updated:</span> {updated}</div>
              <div className="mt-1 font-mono text-[10px] text-slate-400">ID: {entity.id}</div>
            </div>
            <button
              onClick={handleSave}
              disabled={saving || !!jsonError}
              className="rounded bg-sky-600 px-4 py-1.5 text-sm font-semibold text-white shadow hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>

        {entity.short_description && (
          <p className="mt-4 text-sm text-slate-700 border-t border-slate-100 pt-3">
            {entity.short_description}
          </p>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* 2. Main Editor Area (JSON + AI)                                    */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex h-[600px] gap-4">
        
        {/* Left: JSON Editor */}
        <div className="flex flex-1 flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <label className="text-xs font-semibold uppercase text-slate-500">
              Frame Payload
            </label>
            {jsonError && (
              <span className="text-xs font-bold text-red-600">{jsonError}</span>
            )}
          </div>
          <textarea
            className={`w-full flex-1 resize-none rounded border p-3 font-mono text-sm leading-relaxed focus:outline-none ${
              jsonError 
                ? "border-red-300 bg-red-50 focus:border-red-500" 
                : "border-slate-300 focus:border-sky-500"
            }`}
            value={payloadString}
            onChange={handleJsonChange}
            spellCheck={false}
          />
          <p className="mt-2 text-xs text-slate-400">
            * Direct edit mode. Use the Architect AI to generate structure.
          </p>
        </div>

        {/* Right: AI Panel */}
        <div className="w-80 shrink-0 sm:w-96">
          <AIPanel
            entityId={String(entity.id)}
            entityType={entity.frame_type || "generic"}
            currentValues={localPayload}
            language={entity.lang}
            onApplySuggestion={handleAISuggestion}
            className="h-full"
          />
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* 3. Test Generation (Replaces History Placeholder)                  */}
      {/* ------------------------------------------------------------------ */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            Test Generation
          </h2>
          <button
            onClick={handleGenerate}
            disabled={generating || !!jsonError}
            className="rounded bg-indigo-600 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:bg-slate-300 disabled:cursor-not-allowed"
          >
            {generating ? "Generating..." : "Generate Preview"}
          </button>
        </div>

        {genResult ? (
          <GenerationResult result={genResult} className="!mt-0 !shadow-none !border !border-slate-100" />
        ) : (
          <div className="py-8 text-center text-xs text-slate-500 bg-slate-50 rounded border border-dashed border-slate-200">
            Click "Generate Preview" to test the current frame payload against the NLG engine.
          </div>
        )}
      </section>
    </div>
  );
}