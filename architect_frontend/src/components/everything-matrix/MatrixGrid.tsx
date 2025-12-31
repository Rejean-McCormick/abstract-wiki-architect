// architect_frontend/src/components/everything-matrix/MatrixGrid.tsx
"use client";

import { useMemo, useState } from "react";
import type { EverythingMatrix } from "@/types/EverythingMatrix";
import LanguageRow from "./LanguageRow";

interface MatrixGridProps {
  matrix: EverythingMatrix;
}

type SortField = "iso" | "maturity" | "strategy";
type SortOrder = "asc" | "desc";

const ZONE_GROUPS: Array<{
  label: string;
  colSpan: number;
  className: string;
}> = [
  {
    label: "Zone A: Logic (RGL)",
    colSpan: 5,
    className:
      "border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-blue-700 bg-blue-50/50",
  },
  {
    label: "Zone B: Data (Lexicon)",
    colSpan: 4,
    className:
      "border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-amber-700 bg-amber-50/50",
  },
  {
    label: "Zone C: Apps",
    colSpan: 3,
    className:
      "border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-purple-700 bg-purple-50/50",
  },
  {
    label: "Zone D: QA",
    colSpan: 2,
    className:
      "border-b border-slate-200 px-2 py-1 text-center font-bold text-emerald-700 bg-emerald-50/50",
  },
];

const ZONE_COLUMNS: Array<{
  key: string;
  label: string;
  title: string;
  className?: string;
}> = [
  // Zone A
  {
    key: "cat",
    label: "Cat",
    title: "Category Definitions",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "noun",
    label: "Noun",
    title: "Noun Morphology",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "para",
    label: "Para",
    title: "Paradigms",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "gram",
    label: "Gram",
    title: "Grammar Core",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "syn",
    label: "Syn",
    title: "Syntax API",
    className: "border-b border-r border-slate-200 px-2 py-2 text-center font-bold",
  },

  // Zone B
  {
    key: "seed",
    label: "Seed",
    title: "Core Seed (>150 words)",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "conc",
    label: "Conc",
    title: "Domain Concepts (>500)",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "wide",
    label: "Wide",
    title: "Wide Import (CSV)",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "sem",
    label: "Sem",
    title: "Semantic Alignment (QIDs)",
    className: "border-b border-r border-slate-200 px-2 py-2 text-center",
  },

  // Zone C
  {
    key: "prof",
    label: "Prof",
    title: "Bio-Ready",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "asst",
    label: "Asst",
    title: "Assistant-Ready",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "rout",
    label: "Rout",
    title: "Topology Routing",
    className: "border-b border-r border-slate-200 px-2 py-2 text-center",
  },

  // Zone D
  {
    key: "bin",
    label: "Bin",
    title: "Binary Compilation",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
  {
    key: "test",
    label: "Test",
    title: "Unit Tests",
    className: "border-b border-slate-200 px-2 py-2 text-center",
  },
];

function sortIndicator(active: boolean, order: SortOrder) {
  if (!active) return "";
  return order === "asc" ? " ↑" : " ↓";
}

function normalizeForSearch(s: string) {
  // Lowercase + remove diacritics for friendlier search
  return s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "");
}

function safeNum(n: unknown, fallback = 0) {
  const x = typeof n === "number" ? n : Number(n);
  return Number.isFinite(x) ? x : fallback;
}

export default function MatrixGrid({ matrix }: MatrixGridProps) {
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("maturity");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const languages = useMemo(() => Object.values(matrix.languages || {}), [matrix.languages]);

  const filteredLanguages = useMemo(() => {
    const q = normalizeForSearch(search.trim());
    let langs = languages;

    if (q) {
      langs = langs.filter((l) => {
        const name = normalizeForSearch(l.meta?.name || "");
        const iso = normalizeForSearch(l.meta?.iso || "");
        return name.includes(q) || iso.includes(q);
      });
    }

    // stable sort (copy first), with deterministic tie-breakers
    const sorted = [...langs].sort((a, b) => {
      let valA: string | number = "";
      let valB: string | number = "";

      if (sortField === "iso") {
        valA = (a.meta?.iso || "").toLowerCase();
        valB = (b.meta?.iso || "").toLowerCase();
      } else if (sortField === "strategy") {
        valA = (a.verdict?.build_strategy || "").toLowerCase();
        valB = (b.verdict?.build_strategy || "").toLowerCase();
      } else {
        valA = safeNum(a.verdict?.maturity_score, 0);
        valB = safeNum(b.verdict?.maturity_score, 0);
      }

      if (valA < valB) return sortOrder === "asc" ? -1 : 1;
      if (valA > valB) return sortOrder === "asc" ? 1 : -1;

      // tie-breakers: iso then name (always ascending)
      const isoA = (a.meta?.iso || "").toLowerCase();
      const isoB = (b.meta?.iso || "").toLowerCase();
      if (isoA < isoB) return -1;
      if (isoA > isoB) return 1;

      const nameA = (a.meta?.name || "").toLowerCase();
      const nameB = (b.meta?.name || "").toLowerCase();
      if (nameA < nameB) return -1;
      if (nameA > nameB) return 1;

      return 0;
    });

    return sorted;
  }, [languages, search, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const activeCount = filteredLanguages.length;
  const totalCount = languages.length;

  return (
    <div className="flex flex-col">
      {/* Controls Toolbar */}
      <div className="flex flex-col gap-4 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <input
            type="text"
            placeholder="Search ISO or name (e.g. 'fra', 'Zulu')..."
            className="w-full rounded-md border border-slate-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none sm:w-96"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="text-xs text-slate-500">
            Showing <span className="font-mono">{activeCount}</span> /{" "}
            <span className="font-mono">{totalCount}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <span>Sort by:</span>

          <button
            onClick={() => handleSort("maturity")}
            className={`font-medium hover:text-blue-600 ${
              sortField === "maturity" ? "text-blue-700 underline" : ""
            }`}
            title="Sort by maturity score"
          >
            Maturity{sortIndicator(sortField === "maturity", sortOrder)}
          </button>

          <button
            onClick={() => handleSort("iso")}
            className={`font-medium hover:text-blue-600 ${
              sortField === "iso" ? "text-blue-700 underline" : ""
            }`}
            title="Sort by ISO code"
          >
            ISO Code{sortIndicator(sortField === "iso", sortOrder)}
          </button>

          <button
            onClick={() => handleSort("strategy")}
            className={`font-medium hover:text-blue-600 ${
              sortField === "strategy" ? "text-blue-700 underline" : ""
            }`}
            title="Sort by build strategy"
          >
            Strategy{sortIndicator(sortField === "strategy", sortOrder)}
          </button>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-sm">
          {/* Table Header */}
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            {/* Top Row: Zone Groupings */}
            <tr>
              <th
                className="sticky left-0 z-10 border-b border-r border-slate-200 bg-slate-50 px-4 py-2"
                rowSpan={2}
              >
                <button
                  onClick={() => handleSort("iso")}
                  className="text-left hover:text-blue-600"
                  title="Sort by ISO"
                >
                  Language{sortIndicator(sortField === "iso", sortOrder)}
                </button>
              </th>

              {ZONE_GROUPS.map((z) => (
                <th key={z.label} colSpan={z.colSpan} className={z.className}>
                  {z.label}
                </th>
              ))}
            </tr>

            {/* Bottom Row: Specific Columns */}
            <tr>
              {ZONE_COLUMNS.map((col) => (
                <th key={col.key} title={col.title} className={col.className}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-slate-100 bg-white">
            {filteredLanguages.length > 0 ? (
              filteredLanguages.map((lang) => (
                <LanguageRow key={lang.meta?.iso || lang.meta?.name || Math.random()} entry={lang} />
              ))
            ) : (
              <tr>
                <td colSpan={1 + ZONE_COLUMNS.length} className="py-8 text-center text-slate-400">
                  No languages found matching "{search}"
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
