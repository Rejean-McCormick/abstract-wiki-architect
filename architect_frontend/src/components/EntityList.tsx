// architect_frontend/src/components/EntityList.tsx
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

// If you already have a shared type in src/lib/entityApi.ts,
// you can import it and delete the local interface below, e.g.:
// import type { EntitySummary } from "../lib/entityApi";

export interface EntitySummary {
  id: string;
  label: string;
  description?: string | null;
  entityType?: string | null; // e.g. "person", "organization"
  language?: string | null;   // e.g. "en", "fr"
  updatedAt?: string | null;  // ISO timestamp
}

interface EntityListProps {
  entities: EntitySummary[];
  isLoading?: boolean;
  error?: string | null;
  /**
   * Optional callback if you want to react to selection
   * in the parent instead of always navigating.
   */
  onSelectEntity?: (entity: EntitySummary) => void;
  /**
   * If true, disables automatic navigation and only calls onSelectEntity.
   */
  disableNavigation?: boolean;
}

/**
 * EntityList
 *
 * Renders a searchable, sortable list of entities.
 * Each entity links to /abstract_wiki_architect/entities/[id] by default.
 */
export default function EntityList(props: EntityListProps) {
  const {
    entities,
    isLoading = false,
    error = null,
    onSelectEntity,
    disableNavigation = false,
  } = props;

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<"label" | "updatedAt">("label");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();

    let result = entities;

    if (q.length > 0) {
      result = result.filter((e) => {
        const label = e.label?.toLowerCase() ?? "";
        const desc = e.description?.toLowerCase() ?? "";
        const type = e.entityType?.toLowerCase() ?? "";
        const lang = e.language?.toLowerCase() ?? "";
        return (
          label.includes(q) ||
          desc.includes(q) ||
          type.includes(q) ||
          lang.includes(q)
        );
      });
    }

    const sorted = [...result].sort((a, b) => {
      if (sortKey === "label") {
        const la = a.label.toLowerCase();
        const lb = b.label.toLowerCase();
        if (la < lb) return sortDir === "asc" ? -1 : 1;
        if (la > lb) return sortDir === "asc" ? 1 : -1;
        return 0;
      }

      // sortKey === "updatedAt"
      const ta = a.updatedAt ? Date.parse(a.updatedAt) : 0;
      const tb = b.updatedAt ? Date.parse(b.updatedAt) : 0;
      if (ta < tb) return sortDir === "asc" ? -1 : 1;
      if (ta > tb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [entities, search, sortKey, sortDir]);

  const handleHeaderClick = (key: "label" | "updatedAt") => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const renderSortIndicator = (key: "label" | "updatedAt") => {
    if (sortKey !== key) return null;
    return sortDir === "asc" ? "▲" : "▼";
  };

  const handleRowClick = (entity: EntitySummary) => {
    if (onSelectEntity) {
      onSelectEntity(entity);
    }
    // Navigation is handled by <Link> when disableNavigation === false.
  };

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
        Loading entities…
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

  if (!entities || entities.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
        No entities yet. Once you register entities in the backend, they will
        appear here.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <input
          type="search"
          placeholder="Search entities by label, type, or language…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
        {/* Hook point for future filters (language, type, etc.) */}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="max-h-[540px] overflow-y-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th
                  scope="col"
                  className="cursor-pointer px-4 py-2"
                  onClick={() => handleHeaderClick("label")}
                >
                  <span className="inline-flex items-center gap-1">
                    Label
                    {renderSortIndicator("label")}
                  </span>
                </th>
                <th scope="col" className="px-4 py-2">
                  Type
                </th>
                <th scope="col" className="px-4 py-2">
                  Language
                </th>
                <th
                  scope="col"
                  className="cursor-pointer px-4 py-2 text-right"
                  onClick={() => handleHeaderClick("updatedAt")}
                >
                  <span className="inline-flex items-center gap-1">
                    Last updated
                    {renderSortIndicator("updatedAt")}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((entity) => {
                const rowContent = (
                  <tr
                    key={entity.id}
                    className="group cursor-pointer hover:bg-slate-50"
                    onClick={() => handleRowClick(entity)}
                  >
                    <td className="max-w-xs truncate px-4 py-2 font-medium text-slate-900">
                      {entity.label}
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {entity.entityType ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-slate-600">
                      {entity.language ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-right text-xs text-slate-500">
                      {entity.updatedAt
                        ? new Date(entity.updatedAt).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                );

                if (disableNavigation) {
                  return rowContent;
                }

                return (
                  <Link
                    key={entity.id}
                    href={`/abstract_wiki_architect/entities/${encodeURIComponent(
                      entity.id,
                    )}`}
                    className="block"
                  >
                    {rowContent}
                  </Link>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary */}
      <div className="text-xs text-slate-500">
        Showing {filtered.length} of {entities.length} entities
      </div>
    </div>
  );
}
