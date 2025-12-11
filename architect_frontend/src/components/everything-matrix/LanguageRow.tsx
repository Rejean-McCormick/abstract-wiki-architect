import { LanguageEntry } from '@/types/EverythingMatrix';
import ScoreCell from './ScoreCell';

interface LanguageRowProps {
  entry: LanguageEntry;
}

export default function LanguageRow({ entry }: LanguageRowProps) {
  const { meta, blocks, status } = entry;

  // Helper to determine badge color for strategy
  const strategyColor = 
    status.build_strategy === 'HIGH_ROAD' ? 'bg-green-100 text-green-700' :
    status.build_strategy === 'SAFE_MODE' ? 'bg-amber-100 text-amber-700' :
    'bg-red-100 text-red-700';

  return (
    <tr className="hover:bg-slate-50 transition-colors">
      {/* Sticky Left Column: Metadata */}
      <td className="sticky left-0 z-10 border-b border-r border-slate-200 bg-white px-4 py-3 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">{meta.name}</span>
            <span className="text-xs text-slate-400">({meta.wiki_code})</span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs">
            <span className={`rounded-full px-2 py-0.5 font-medium ${strategyColor}`}>
              {status.build_strategy}
            </span>
            <span className="text-slate-500">
              {status.overall_maturity}/10
            </span>
          </div>
        </div>
      </td>

      {/* ZONE A: RGL FOUNDATION */}
      <ScoreCell score={blocks.rgl_cat} />
      <ScoreCell score={blocks.rgl_noun} />
      <ScoreCell score={blocks.rgl_paradigms} />
      <ScoreCell score={blocks.rgl_grammar} />
      <ScoreCell score={blocks.rgl_syntax} isZoneEnd />

      {/* ZONE B: LEXICON */}
      <ScoreCell score={blocks.lex_seed} />
      <ScoreCell score={blocks.lex_concrete} />
      <ScoreCell score={blocks.lex_wide} />
      <ScoreCell score={blocks.sem_mappings} isZoneEnd />

      {/* ZONE C: APPLICATION */}
      <ScoreCell score={blocks.app_profile} />
      <ScoreCell score={blocks.app_assets} />
      <ScoreCell score={blocks.app_routes} isZoneEnd />

      {/* ZONE D: QUALITY */}
      <ScoreCell score={blocks.meta_compile} />
      <ScoreCell score={blocks.meta_test} />
    </tr>
  );
}