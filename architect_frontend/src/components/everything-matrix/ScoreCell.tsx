import React from 'react';

interface ScoreCellProps {
  score: number;
  isZoneEnd?: boolean;
}

export default function ScoreCell({ score, isZoneEnd = false }: ScoreCellProps) {
  // Logic: Map Maturity Scale (0-10) to Visual Styles
  let bgClass = '';
  let textClass = '';

  if (score === 0) {
    // 0: Absent (Grayed out)
    bgClass = 'bg-slate-50';
    textClass = 'text-slate-300';
  } else if (score <= 2) {
    // 1-2: Blocker (Red)
    bgClass = 'bg-red-50';
    textClass = 'text-red-600 font-medium';
  } else if (score <= 5) {
    // 3-5: Draft / Safe Mode (Amber)
    bgClass = 'bg-amber-50';
    textClass = 'text-amber-700 font-medium';
  } else if (score <= 8) {
    // 6-8: Functional / Beta (Blue)
    bgClass = 'bg-blue-50';
    textClass = 'text-blue-700 font-semibold';
  } else {
    // 9-10: Production / Final (Green)
    bgClass = 'bg-emerald-100';
    textClass = 'text-emerald-800 font-bold';
  }

  return (
    <td
      className={`
        relative border-b border-slate-200 px-2 py-3 text-center text-sm
        transition-all duration-150 hover:brightness-95 cursor-default
        ${isZoneEnd ? 'border-r-2 border-r-slate-200' : 'border-r border-r-slate-100'}
        ${bgClass}
      `}
    >
      <span className={textClass}>
        {score === 0 ? '—' : score}
      </span>
      
      {/* Optional: Tiny visual indicator for perfect scores */}
      {score === 10 && (
        <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-emerald-500 opacity-50" />
      )}
    </td>
  );
}