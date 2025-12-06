// architect_frontend/src/components/EntityList.tsx
"use client";

import React, { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { architectApi, Entity, EntityCreatePayload } from "../lib/api";

export default function EntityList() {
  const router = useRouter();

  // --- Data State ---
  const [entities, setEntities] = useState<Entity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- UI State ---
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<"name" | "updated_at">("updated_at"); // Default to newest
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // --- Create Modal State ---
  const [isCreating, setIsCreating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newEntityData, setNewEntityData] = useState<EntityCreatePayload>({
    name: "",
    frame_type: "bio", // default
    lang: "en",
  });

  // 1. Fetch Entities on Mount
  useEffect(() => {
    loadEntities();
  }, []);

  async function loadEntities() {
    try {
      setIsLoading(true);
      const data = await architectApi.listEntities();
      setEntities(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError("Failed to load entities. Ensure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  }

  // 2. Handle Delete
  const handleDelete = async (e: React.MouseEvent, id: number | string) => {
    e.preventDefault(); // Prevent Link navigation
    if (!confirm("Are you sure you want to delete this entity?")) return;

    try {
      await architectApi.deleteEntity(id);
      setEntities((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      alert("Failed to delete entity.");
    }
  };

  // 3. Handle Create
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const created = await architectApi.createEntity({
        ...newEntityData,
        frame_payload: {}, // Start empty
      });
      // Navigate immediately to the new entity editor
      router.push(`/abstract_wiki_architect/entities/${created.id}`);
    } catch (err) {
      alert("Failed to create entity.");
      setIsSubmitting(false);
    }
  };

  // 4. Client-side Search & Sort
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();

    let result = entities;

    // Filter
    if (q.length > 0) {
      result = result.filter((e) => {
        const name = e.name?.toLowerCase() ?? "";
        const type = e.frame_type?.toLowerCase() ?? "";
        const lang = e.lang?.toLowerCase() ?? "";
        const desc = e.short_description?.toLowerCase() ?? "";
        return (
          name.includes(q) ||
          type.includes(q) ||
          lang.includes(q) ||
          desc.includes(q)
        );
      });
    }

    // Sort
    const sorted = [...result].sort((a, b) => {
      if (sortKey === "name") {
        const la = a.name.toLowerCase();
        const lb = b.name.toLowerCase();
        if (la < lb) return sortDir === "asc" ? -1 : 1;
        if (la > lb) return sortDir === "asc" ? 1 : -1;
        return 0;
      }

      // sortKey === "updated_at"
      const ta = a.updated_at ? Date.parse(a.updated_at) : 0;
      const tb = b.updated_at ? Date.parse(b.updated_at) : 0;
      if (ta < tb) return sortDir === "asc" ? -1 : 1;
      if (ta > tb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [entities, search, sortKey, sortDir]);

  // --- Render Helpers ---

  const handleHeaderClick = (key: "name" | "updated_at") => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const renderSortIndicator = (key: "name" | "updated_at") => {
    if (sortKey !== key) return null;
    return sortDir === "asc" ? "▲" : "▼";
  };

  // --- Main Render ---

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        Loading library...
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

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1">
          <input
            type="search"
            placeholder="Search entities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-500"
        >
          + New Entity
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="max-h-[600px] overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              {entities.length === 0
                ? "No entities found. Create one to get started."
                : "No matching entities found."}
            </div>
          ) : (
            <table className="min-w-full text-left text-sm">
              <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th
                    scope="col"
                    className="cursor-pointer px-4 py-3 hover:bg-slate-100"
                    onClick={() => handleHeaderClick("name")}
                  >
                    <span className="inline-flex items-center gap-1">
                      Name {renderSortIndicator("name")}
                    </span>
                  </th>
                  <th scope="col" className="px-4 py-3">Type</th>
                  <th scope="col" className="px-4 py-3">Lang</th>
                  <th
                    scope="col"
                    className="cursor-pointer px-4 py-3 text-right hover:bg-slate-100"
                    onClick={() => handleHeaderClick("updated_at")}
                  >
                    <span className="inline-flex items-center justify-end gap-1">
                      Updated {renderSortIndicator("updated_at")}
                    </span>
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((entity) => (
                  <tr
                    key={entity.id}
                    className="group cursor-pointer hover:bg-slate-50"
                    // Row click navigates, but specific buttons stopPropagation
                    onClick={() => router.push(`/abstract_wiki_architect/entities/${entity.id}`)}
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">
                      <div className="truncate max-w-[200px] sm:max-w-xs">{entity.name}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        {entity.frame_type ?? "Generic"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {entity.lang}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">
                      {entity.updated_at
                        ? new Date(entity.updated_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={(e) => handleDelete(e, entity.id)}
                        className="text-xs font-medium text-red-400 opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="text-xs text-slate-500">
        Showing {filtered.length} of {entities.length} entities
      </div>

      {/* --- Create Modal --- */}
      {isCreating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold text-slate-800">New Entity</h2>
            <form onSubmit={handleCreateSubmit} className="flex flex-col gap-4">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                  Name
                </label>
                <input
                  autoFocus
                  type="text"
                  required
                  placeholder="e.g. Marie Curie"
                  value={newEntityData.name}
                  onChange={(e) =>
                    setNewEntityData({ ...newEntityData, name: e.target.value })
                  }
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    Type
                  </label>
                  <select
                    value={newEntityData.frame_type}
                    onChange={(e) =>
                      setNewEntityData({ ...newEntityData, frame_type: e.target.value })
                    }
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm bg-white focus:border-sky-500 focus:outline-none"
                  >
                    <option value="bio">Bio</option>
                    <option value="entity.person">Person</option>
                    <option value="entity.place">Place</option>
                    <option value="event">Event</option>
                    <option value="construction">Construction</option>
                    <option value="function">Function</option>
                  </select>
                </div>
                <div className="w-24">
                  <label className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    Lang
                  </label>
                  <input
                    type="text"
                    maxLength={5}
                    value={newEntityData.lang}
                    onChange={(e) =>
                      setNewEntityData({ ...newEntityData, lang: e.target.value })
                    }
                    className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="mt-4 flex gap-3">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="flex-1 rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}