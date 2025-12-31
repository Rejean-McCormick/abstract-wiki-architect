import { LanguageEntry } from '@/types/EverythingMatrix';
import ScoreCell from './ScoreCell';

interface LanguageRowProps {
  entry: LanguageEntry;
}

export default function LanguageRow({ entry }: LanguageRowProps) {
  const { meta, zones, verdict } = entry;

  // Helper to determine badge color for strategy
  const strategyColor = 
    verdict.build_strategy === 'HIGH_ROAD' ? 'bg-green-100 text-green-700' :
    verdict.build_strategy === 'SAFE_MODE' ? 'bg-amber-100 text-amber-700' :
    'bg-red-100 text-red-700';

  // "Zombie Languages" (linked but empty) are displayed with low opacity
  const opacityClass = verdict.runnable ? 'opacity-100' : 'opacity-50 grayscale';

  return (
    <tr className={`hover:bg-slate-50 transition-colors ${opacityClass}`}>
      {/* Sticky Left Column: Metadata */}
      <td className="sticky left-0 z-10 border-b border-r border-slate-200 bg-white px-4 py-3 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]">
        <div className="flex flex-col">
          <div className="flex items-baseline gap-2">
            {/* Display Full Name if available, fallback to ISO code */}
            <span className="font-semibold text-slate-900 text-lg whitespace-nowrap">
              {meta.name || meta.iso.toUpperCase()}
            </span>
            
            {/* Secondary identifier: ISO if name exists, otherwise Origin */}
            {meta.name ? (
                <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                  {meta.iso}
                </span>
            ) : (
                <span className="text-xs text-slate-400 uppercase tracking-wider">
                  ({meta.origin})
                </span>
            )}
          </div>
          
          <div className="mt-1 flex items-center gap-2 text-xs">
            <span className={`rounded-full px-2 py-0.5 font-bold text-[10px] uppercase tracking-wide ${strategyColor}`}>
              {verdict.build_strategy}
            </span>
            <span className="font-mono font-bold text-slate-600">
              {verdict.maturity_score}
            </span>
             {/* If we showed name above, show origin here to be complete */}
             {meta.name && (
                <span className="text-[10px] text-slate-400 uppercase ml-1">
                  {meta.origin}
                </span>
             )}
          </div>
        </div>
      </td>

      {/* ZONE A: RGL FOUNDATION (Logic) */}
      <ScoreCell score={zones.A_RGL.CAT} />
      <ScoreCell score={zones.A_RGL.NOUN} />
      <ScoreCell score={zones.A_RGL.PARA} />
      <ScoreCell score={zones.A_RGL.GRAM} />
      <ScoreCell score={zones.A_RGL.SYN} isZoneEnd />

      {/* ZONE B: LEXICON (Data) */}
      <ScoreCell score={zones.B_LEX.SEED} />
      <ScoreCell score={zones.B_LEX.CONC} />
      <ScoreCell score={zones.B_LEX.WIDE} />
      <ScoreCell score={zones.B_LEX.SEM} isZoneEnd />

      {/* ZONE C: APPLICATION (Use Case) */}
      <ScoreCell score={zones.C_APP.PROF} />
      <ScoreCell score={zones.C_APP.ASST} />
      <ScoreCell score={zones.C_APP.ROUT} isZoneEnd />

      {/* ZONE D: QUALITY (QA) */}
      <ScoreCell score={zones.D_QA.BIN} />
      <ScoreCell score={zones.D_QA.TEST} />
    </tr>
  );
}