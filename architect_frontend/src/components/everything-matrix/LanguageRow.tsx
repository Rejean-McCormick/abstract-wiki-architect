// architect_frontend/src/components/everything-matrix/LanguageRow.tsx
import { LanguageEntry } from "@/types/EverythingMatrix";
import ScoreCell from "./ScoreCell";

interface LanguageRowProps {
  entry: LanguageEntry;
}

/**
 * Canonical backend contract (v2+):
 * - All zone scores are 0..10 floats.
 * - Keys are iso2 and Zone C/D do NOT use 0..1 anymore.
 *
 * We still keep a very small “legacy 0..1” back-compat shim so older artifacts
 * don’t render as all-dark cells.
 */
function normScore(value: unknown, opts?: { scale01to10?: boolean }): number {
  const { scale01to10 = false } = opts ?? {};
  let n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return 0;

  // Back-compat: some older scanners emitted 0..1 floats for Zone C/D
  if (scale01to10 && n >= 0 && n <= 1) n = n * 10;

  return Math.max(0, Math.min(10, n));
}

/**
 * Detect “legacy 0–1 scale” zones.
 * Enable if:
 * - zone has a max in (0..1], AND
 * - at least one of A/B has signal in normal 0..10 (so we don't scale fully-empty rows)
 */
function zoneLooksLegacy01(zone: unknown, keys: readonly string[], refABMax: number): boolean {
  const z = (zone ?? {}) as Record<string, unknown>;

  const nums = keys.map((k) => {
    const v = z[k];
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? n : 0;
  });

  const max = Math.max(...nums);
  return max > 0 && max <= 1.0 && refABMax > 1.0;
}

/** Formats a score for display without breaking when backend returns strings/nulls. */
function fmtScore(value: unknown, digits = 1): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "0";
  return n.toFixed(digits);
}

function numOrNull(value: unknown): number | null {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function legacyDetail(value: unknown, isLegacy01: boolean): number | undefined {
  if (!isLegacy01) return undefined;
  const n = numOrNull(value);
  if (n === null) return undefined;
  return n;
}

export default function LanguageRow({ entry }: LanguageRowProps) {
  const { meta, zones, verdict } = entry;

  // v2+: meta.iso is iso2; keep fallback just in case.
  const displayName = (meta.name?.trim() || meta.iso?.toUpperCase() || "UNKNOWN").trim();
  const isoLabel = (meta.iso || "").toUpperCase();

  const buildStrategy = verdict?.build_strategy || "UNKNOWN";
  const maturityScore = verdict?.maturity_score;

  const strategyColor =
    buildStrategy === "HIGH_ROAD"
      ? "bg-green-100 text-green-700 ring-green-200"
      : buildStrategy === "SAFE_MODE"
      ? "bg-amber-100 text-amber-700 ring-amber-200"
      : buildStrategy === "SKIP"
      ? "bg-red-100 text-red-700 ring-red-200"
      : "bg-slate-100 text-slate-700 ring-slate-200";

  // Keep heatmap visible even when unrunnable.
  const rowOpacityClass = verdict?.runnable ? "opacity-100" : "opacity-85";
  const runnableDot = verdict?.runnable ? "bg-emerald-500" : "bg-slate-400";

  // Defensive zone reads (raw)
  const A = zones?.A_RGL ?? { CAT: 0, NOUN: 0, PARA: 0, GRAM: 0, SYN: 0 };
  const B = zones?.B_LEX ?? { SEED: 0, CONC: 0, WIDE: 0, SEM: 0 };
  const C = zones?.C_APP ?? { PROF: 0, ASST: 0, ROUT: 0 };
  const D = zones?.D_QA ?? { BIN: 0, TEST: 0 };

  // Compute A/B reference max to decide whether to apply legacy scaling.
  // (Used only for back-compat; canonical scanners are 0..10 everywhere.)
  const maxA = Math.max(
    normScore(A.CAT),
    normScore(A.NOUN),
    normScore(A.PARA),
    normScore(A.GRAM),
    normScore(A.SYN)
  );
  const maxB = Math.max(normScore(B.SEED), normScore(B.CONC), normScore(B.WIDE), normScore(B.SEM));
  const refABMax = Math.max(maxA, maxB);

  const cLegacy01 = zoneLooksLegacy01(C, ["PROF", "ASST", "ROUT"], refABMax);
  const dLegacy01 = zoneLooksLegacy01(D, ["BIN", "TEST"], refABMax);

  const cProf = normScore(C.PROF, { scale01to10: cLegacy01 });
  const cAsst = normScore(C.ASST, { scale01to10: cLegacy01 });
  const cRout = normScore(C.ROUT, { scale01to10: cLegacy01 });
  const dBin = normScore(D.BIN, { scale01to10: dLegacy01 });
  const dTest = normScore(D.TEST, { scale01to10: dLegacy01 });

  return (
    <tr className={`hover:bg-slate-50 transition-colors ${rowOpacityClass}`}>
      {/* Sticky Left Column */}
      <td className="sticky left-0 z-10 border-b border-r border-slate-200 bg-white px-4 py-3 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${runnableDot}`}
              title={verdict?.runnable ? "Runnable" : "Not runnable"}
            />
            <span className="font-semibold text-slate-900 text-lg whitespace-nowrap">{displayName}</span>
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider whitespace-nowrap">
              {isoLabel}
            </span>

            {!verdict?.runnable && (
              <span
                className="ml-1 rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 px-2 py-0.5 font-semibold text-[10px] uppercase tracking-wide"
                title="This language does not meet runnable thresholds yet. Scores are still shown."
              >
                Not runnable
              </span>
            )}

            {(cLegacy01 || dLegacy01) && (
              <span
                className="ml-1 rounded-full bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200 px-2 py-0.5 font-semibold text-[10px] uppercase tracking-wide"
                title="This row appears to be from an older artifact where some zones used 0..1. UI scaled them by ×10."
              >
                Legacy scale
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className={`rounded-full px-2 py-0.5 font-bold text-[10px] uppercase tracking-wide ring-1 ${strategyColor}`}>
              {buildStrategy}
            </span>

            <span
              className="rounded-full bg-slate-100 text-slate-700 ring-1 ring-slate-200 px-2 py-0.5 font-mono font-bold text-[10px] uppercase tracking-wide"
              title={`maturity_score: ${String(maturityScore)}`}
            >
              {fmtScore(maturityScore, 1)}
            </span>

            <span className="rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 px-2 py-0.5 text-[10px] uppercase tracking-wide">
              {meta.origin}
            </span>

            <span className="rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 px-2 py-0.5 text-[10px] uppercase tracking-wide">
              Tier {meta.tier}
            </span>

            {meta.folder && (
              <span className="rounded-full bg-slate-100 text-slate-500 ring-1 ring-slate-200 px-2 py-0.5 font-mono text-[10px] lowercase tracking-wide">
                {meta.folder}
              </span>
            )}
          </div>
        </div>
      </td>

      {/* ZONE A */}
      <ScoreCell score={normScore(A.CAT)} scale="0-10" />
      <ScoreCell score={normScore(A.NOUN)} scale="0-10" />
      <ScoreCell score={normScore(A.PARA)} scale="0-10" />
      <ScoreCell score={normScore(A.GRAM)} scale="0-10" />
      <ScoreCell score={normScore(A.SYN)} scale="0-10" isZoneEnd />

      {/* ZONE B */}
      <ScoreCell score={normScore(B.SEED)} scale="0-10" />
      <ScoreCell score={normScore(B.CONC)} scale="0-10" />
      <ScoreCell score={normScore(B.WIDE)} scale="0-10" />
      <ScoreCell score={normScore(B.SEM)} scale="0-10" isZoneEnd />

      {/* ZONE C (canonical 0..10; legacy 0..1 scaled if detected) */}
      <ScoreCell
        score={cProf}
        scale="0-10"
        detail={legacyDetail(C.PROF, cLegacy01)}
        detailLabel={cLegacy01 ? "raw 0..1" : undefined}
      />
      <ScoreCell
        score={cAsst}
        scale="0-10"
        detail={legacyDetail(C.ASST, cLegacy01)}
        detailLabel={cLegacy01 ? "raw 0..1" : undefined}
      />
      <ScoreCell
        score={cRout}
        scale="0-10"
        detail={legacyDetail(C.ROUT, cLegacy01)}
        detailLabel={cLegacy01 ? "raw 0..1" : undefined}
        isZoneEnd
      />

      {/* ZONE D (canonical 0..10; legacy 0..1 scaled if detected) */}
      <ScoreCell
        score={dBin}
        scale="0-10"
        detail={legacyDetail(D.BIN, dLegacy01)}
        detailLabel={dLegacy01 ? "raw 0..1" : undefined}
      />
      <ScoreCell
        score={dTest}
        scale="0-10"
        detail={legacyDetail(D.TEST, dLegacy01)}
        detailLabel={dLegacy01 ? "raw 0..1" : undefined}
      />
    </tr>
  );
}