'use client';

import { useState, useMemo } from 'react';
import { EverythingMatrix, LanguageEntry } from '@/types/EverythingMatrix';
import LanguageRow from './LanguageRow';

interface MatrixGridProps {
  matrix: EverythingMatrix;
}

type SortField = 'name' | 'maturity' | 'code';
type SortOrder = 'asc' | 'desc';

export default function MatrixGrid({ matrix }: MatrixGridProps) {
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('maturity');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Convert dictionary to array and process
  const filteredLanguages = useMemo(() => {
    let langs = Object.values(matrix.languages);

    // 1. Filter
    if (search) {
      const q = search.toLowerCase();
      langs = langs.filter(
        (l) =>
          l.meta.name.toLowerCase().includes(q) ||
          l.meta.wiki_code.toLowerCase().includes(q) ||
          l.meta.iso_code.toLowerCase().includes(q)
      );
    }

    // 2. Sort
    return langs.sort((a, b) => {
      let valA: string | number = '';
      let valB: string | number = '';

      if (sortField === 'name') {
        valA = a.meta.name;
        valB = b.meta.name;
      } else if (sortField === 'code') {
        valA = a.meta.wiki_code;
        valB = b.meta.wiki_code;
      } else if (sortField === 'maturity') {
        valA = a.status.overall_maturity;
        valB = b.status.overall_maturity;
      }

      if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
      if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [matrix, search, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc'); // Default to desc for new metrics
    }
  };

  return (
    <div className="flex flex-col">
      {/* Controls Toolbar */}
      <div className="flex flex-col gap-4 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="text"
          placeholder="Search languages (e.g. 'French', 'Fra', 'fr')..."
          className="w-full rounded-md border border-slate-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none sm:w-96"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        
        <div className="flex gap-2 text-sm text-slate-600">
           <span>Sort by:</span>
           <button 
             onClick={() => handleSort('maturity')}
             className={`font-medium hover:text-blue-600 ${sortField === 'maturity' ? 'text-blue-700 underline' : ''}`}
           >
             Maturity
           </button>
           <button 
             onClick={() => handleSort('name')}
             className={`font-medium hover:text-blue-600 ${sortField === 'name' ? 'text-blue-700 underline' : ''}`}
           >
             Name
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
              <th className="sticky left-0 z-10 border-b border-r border-slate-200 bg-slate-50 px-4 py-2" rowSpan={2}>
                Language
              </th>
              
              <th colSpan={5} className="border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-blue-700 bg-blue-50/50">
                Zone A: RGL Engine
              </th>
              <th colSpan={4} className="border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-amber-700 bg-amber-50/50">
                Zone B: Lexicon
              </th>
              <th colSpan={3} className="border-b border-r border-slate-200 px-2 py-1 text-center font-bold text-purple-700 bg-purple-50/50">
                Zone C: Application
              </th>
              <th colSpan={2} className="border-b border-slate-200 px-2 py-1 text-center font-bold text-emerald-700 bg-emerald-50/50">
                Zone D: Quality
              </th>
            </tr>

            {/* Bottom Row: Specific Columns */}
            <tr>
              {/* Zone A */}
              <th title="Category Definitions" className="border-b border-slate-200 px-2 py-2 text-center">Cat</th>
              <th title="Noun Morphology" className="border-b border-slate-200 px-2 py-2 text-center">Noun</th>
              <th title="Constructors (Paradigms)" className="border-b border-slate-200 px-2 py-2 text-center">Para</th>
              <th title="Grammar Structure" className="border-b border-slate-200 px-2 py-2 text-center">Gram</th>
              <th title="High-Level Syntax API" className="border-b border-r border-slate-200 px-2 py-2 text-center font-bold">Syn</th>

              {/* Zone B */}
              <th title="AI Seed Dictionary" className="border-b border-slate-200 px-2 py-2 text-center">Seed</th>
              <th title="Concrete GF Dictionary" className="border-b border-slate-200 px-2 py-2 text-center">Conc</th>
              <th title="Wiktionary/PanLex Import" className="border-b border-slate-200 px-2 py-2 text-center">Wide</th>
              <th title="Semantic Mappings" className="border-b border-r border-slate-200 px-2 py-2 text-center">Sem</th>

              {/* Zone C */}
              <th title="Frontend Profile Config" className="border-b border-slate-200 px-2 py-2 text-center">Prof</th>
              <th title="UI Assets (Flags)" className="border-b border-slate-200 px-2 py-2 text-center">Asst</th>
              <th title="Backend API Routes" className="border-b border-r border-slate-200 px-2 py-2 text-center">Rout</th>

              {/* Zone D */}
              <th title="Binary Compilation" className="border-b border-slate-200 px-2 py-2 text-center">Bin</th>
              <th title="Unit Tests" className="border-b border-slate-200 px-2 py-2 text-center">Test</th>
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-slate-100 bg-white">
            {filteredLanguages.length > 0 ? (
              filteredLanguages.map((lang) => (
                <LanguageRow key={lang.meta.wiki_code} entry={lang} />
              ))
            ) : (
              <tr>
                <td colSpan={15} className="py-8 text-center text-slate-400">
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