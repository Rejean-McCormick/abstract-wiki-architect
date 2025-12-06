// architect_frontend/src/components/EntityDetail.tsx
"use client";

import React from "react";

// If you already have shared types in src/lib/entityApi.ts, prefer importing them:
// import type { EntityDetail, EntityFrameSummary, EntityGenerationSummary } from "@/lib/entityApi";

export interface EntityFrameSummary {
  id: string;
  frameType: string;
  family?: string | null;
  lang?: string | null;
  status?: "draft" | "approved" | "deprecated" | null;
  updatedAt?: string | null;
}

export interface EntityGenerationSummary {
  id: string;
  frameId: string;
  frameType: string;
  lang: string;
  createdAt: string;
  description?: string | null;
}

export interface EntityDetailData {
  id: string;
  label: string;
  description?: string | null;
  entityType?: string | null; // e.g. "person", "organization"
  language?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  // Optional richer metadata
  tags?: string[] | null;
}

interface EntityDetailProps {
  entity: EntityDetailData;
  frames?: EntityFrameSummary[];
  generations?: EntityGenerationSummary[];
  isLoading?: boolean;
  error?: string | null;
  onOpenFrame?: (frame: EntityFrameSummary) => void;
  onOpenGeneration?: (generation: EntityGenerationSummary) => void;
}

/**
 * EntityDetail
 *
 * Presentation component for a single entity:
 * - basic metadata (label, type, language, timestamps),
 * - list of frames attached to this entity,
 * - list of past generations.
 *
 * Data fetching is expected to be handled by the page component
 * (e.g. /abstract_wiki_architect/entities/[id]/page.tsx).
 */
export default function EntityDetail({
  entity,
  frames = [],
  generations = [],
  isLoading = false,
  error = null,
  onOpenFrame,
  onOpenGeneration,
}: EntityDetailProps) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
        Loading entity…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        {error}
      </div>
    );
  }

  const created = entity.createdAt
    ? new Date(entity.createdAt).toLocaleString()
    : null;
  const updated = entity.updatedAt
    ? new Date(entity.updatedAt).toLocaleString()
    : null;

  return (
    <div className="flex flex-col gap-6">
      {/* Header / basic info */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">
              {entity.label}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              {entity.entityType && (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5">
                  {entity.entityType}
                </span>
              )}
              {entity.language && (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5">
                  Lang: {entity.language}
                </span>
              )}
              {entity.tags?.length
                ? entity.tags.map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5"
                    >
                      {t}
                    </span>
                  ))
                : null}
            </div>
          </div>
          <div className="text-right text-xs text-slate-500">
            {created && (
              <div>
                <span className="font-medium">Created:</span> {created}
              </div>
            )}
            {updated && (
              <div>
                <span className="font-medium">Updated:</span> {updated}
              </div>
            )}
            <div className="mt-1 text-[10px] text-slate-400">
              Entity ID: {entity.id}
            </div>
          </div>
        </div>

        {entity.description && (
          <p className="mt-3 text-sm text-slate-700">{entity.description}</p>
        )}
      </section>

      {/* Frames list */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            Frames for this entity
          </h2>
          <span className="text-xs text-slate-500">
            {frames.length} frame{frames.length === 1 ? "" : "s"}
          </span>
        </div>

        {frames.length === 0 ? (
          <p className="text-xs text-slate-500">
            No frames attached yet. Use the Architect workspaces to create one.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {frames.map((frame) => {
              const updatedAt = frame.updatedAt
                ? new Date(frame.updatedAt).toLocaleString()
                : null;
              const badge =
                frame.status === "approved"
                  ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                  : frame.status === "deprecated"
                  ? "bg-slate-100 text-slate-500 border-slate-200"
                  : "bg-blue-100 text-blue-800 border-blue-200";

              const content = (
                <div className="flex items-center justify-between px-2 py-2">
                  <div>
                    <div className="text-slate-900">
                      <span className="font-medium">{frame.frameType}</span>
                      {frame.family && (
                        <span className="ml-2 text-xs text-slate-500">
                          ({frame.family})
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      {frame.lang && <span>Lang: {frame.lang}</span>}
                      {updatedAt && (
                        <span className="ml-2">Updated: {updatedAt}</span>
                      )}
                    </div>
                  </div>
                  {frame.status && (
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[11px] ${badge}`}
                    >
                      {frame.status}
                    </span>
                  )}
                </div>
              );

              return (
                <li
                  key={frame.id}
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => onOpenFrame && onOpenFrame(frame)}
                >
                  {content}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Generations list */}
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">
            Generated texts
          </h2>
          <span className="text-xs text-slate-500">
            {generations.length} generation
            {generations.length === 1 ? "" : "s"}
          </span>
        </div>

        {generations.length === 0 ? (
          <p className="text-xs text-slate-500">
            No generated texts recorded yet for this entity.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {generations.map((gen) => {
              const createdAt = new Date(gen.createdAt).toLocaleString();
              return (
                <li
                  key={gen.id}
                  className="cursor-pointer px-2 py-2 hover:bg-slate-50"
                  onClick={() => onOpenGeneration && onOpenGeneration(gen)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-slate-900">
                        <span className="font-medium">{gen.frameType}</span>
                        <span className="ml-2 text-xs text-slate-500">
                          ({gen.lang})
                        </span>
                      </div>
                      {gen.description && (
                        <div className="mt-0.5 line-clamp-2 text-xs text-slate-600">
                          {gen.description}
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-slate-500">{createdAt}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
