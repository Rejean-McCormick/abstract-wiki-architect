// architect_frontend/src/app/matrix/page.tsx
import path from "path";
import { existsSync } from "fs";
import { readFile } from "fs/promises";
import type { Metadata } from "next";

import MatrixGrid from "@/components/everything-matrix/MatrixGrid";
import type { EverythingMatrix } from "@/types/EverythingMatrix";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Everything Matrix | Abstract Wiki Architect",
  description:
    "Universal Language Maturity Index across RGL, Lexicon, and Application layers.",
};

function formatTimestamp(ts: unknown): string {
  if (!ts) return "Never";

  // Accept ISO strings, epoch ms, or epoch seconds.
  if (typeof ts === "number") {
    const ms = ts < 1e12 ? ts * 1000 : ts;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? "Never" : d.toLocaleString();
  }

  if (typeof ts === "string") {
    const d = new Date(ts);
    return Number.isNaN(d.getTime()) ? "Never" : d.toLocaleString();
  }

  return "Never";
}

/**
 * Server-side data fetch:
 * Prefer reading the generated artifact from disk.
 * We try a couple candidate locations so it works whether Next is run from
 * repo root or from ./architect_frontend.
 */
async function getMatrixData(): Promise<{ matrix: EverythingMatrix | null; source: string }> {
  const candidates = [
    // If Next runs from repo root
    path.resolve(process.cwd(), "data/indices/everything_matrix.json"),
    // If Next runs from ./architect_frontend
    path.resolve(process.cwd(), "..", "data/indices/everything_matrix.json"),
    // Extra safety if cwd is deeper than expected
    path.resolve(process.cwd(), "..", "..", "data/indices/everything_matrix.json"),
  ];

  for (const p of candidates) {
    try {
      if (!existsSync(p)) continue;
      const raw = await readFile(p, "utf-8");
      return { matrix: JSON.parse(raw) as EverythingMatrix, source: p };
    } catch {
      // try next candidate
    }
  }

  return { matrix: null, source: candidates[0] };
}

export default async function EverythingMatrixPage() {
  const { matrix: matrixData, source } = await getMatrixData();

  const timestamp = formatTimestamp((matrixData as any)?.timestamp);
  const languageCount = matrixData?.languages ? Object.keys(matrixData.languages).length : 0;

  return (
    <main className="min-h-screen bg-slate-50 p-6 md:p-12">
      <div className="mx-auto max-w-[1600px] space-y-8">
        {/* Header */}
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              The Everything Matrix
            </h1>
            <p className="mt-2 text-slate-500">
              Centralized orchestration dashboard tracking language maturity from RGL to Production.
            </p>
          </div>

          <div className="flex items-center gap-6 text-sm">
            <div className="text-right">
              <p className="text-slate-500">Languages Tracked</p>
              <p className="font-mono text-lg font-semibold text-slate-900">{languageCount}</p>
            </div>
            <div className="text-right">
              <p className="text-slate-500">Last Audit</p>
              <p className="font-mono font-medium text-slate-700">{timestamp}</p>
            </div>
          </div>
        </header>

        {/* Content */}
        {matrixData ? (
          <MatrixGrid matrix={matrixData} />
        ) : (
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900">Matrix not found</h2>
            <p className="mt-2 text-sm text-slate-600">
              Could not locate <span className="font-mono">data/indices/everything_matrix.json</span>.
            </p>
            <p className="mt-2 text-sm text-slate-600">
              Expected at (first match wins): <span className="font-mono">{source}</span> (and a couple parent-path fallbacks).
            </p>
            <div className="mt-4 text-sm text-slate-700">
              To generate it, run:{" "}
              <span className="font-mono">python tools/everything_matrix/build_index.py</span>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
