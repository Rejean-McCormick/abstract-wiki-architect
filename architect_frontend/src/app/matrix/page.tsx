import path from 'path';
import fs from 'fs';
import { Metadata } from 'next';
import MatrixGrid from '@/components/everything-matrix/MatrixGrid';
import { EverythingMatrix } from '@/types/EverythingMatrix';

export const metadata: Metadata = {
  title: 'Everything Matrix | Abstract Wiki Architect',
  description: 'Universal Language Maturity Index across RGL, Lexicon, and Application layers.',
};

/**
 * Server-Side Data Fetching
 * Reads the generated JSON artifacts from the ../data directory.
 */
async function getMatrixData(): Promise<EverythingMatrix | null> {
  try {
    // Resolve path relative to the Next.js root (architect_frontend)
    // We go up one level (..) to project root, then into data/indices
    const matrixPath = path.resolve(process.cwd(), '../data/indices/everything_matrix.json');

    if (!fs.existsSync(matrixPath)) {
      console.warn(`⚠️ Matrix file missing at: ${matrixPath}`);
      return null;
    }

    const fileContent = fs.readFileSync(matrixPath, 'utf-8');
    return JSON.parse(fileContent) as EverythingMatrix;
  } catch (error) {
    console.error('❌ Failed to read Everything Matrix:', error);
    return null;
  }
}

export default async function EverythingMatrixPage() {
  const matrixData = await getMatrixData();
  const timestamp = matrixData?.timestamp 
    ? new Date(matrixData.timestamp).toLocaleString() 
    : 'Never';

  const languageCount = matrixData?.languages 
    ? Object.keys(matrixData.languages).length 
    : 0;

  return (
    <main className="min-h-screen bg-slate-50 p-6 md:p-12">
      <div className="mx-auto max-w-[1600px] space-y-8">
        
        {/* Header Section */}
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

        {/* Content Section */}
        {matrixData ? (
          <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <MatrixGrid matrix={matrixData} />
          </section>
        ) : (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-800">
            <h3 className="font-semibold">Data Not Found</h3>
            <p className="mt-1 text-sm text-red-600">
              Could not locate <code>data/indices/everything_matrix.json</code>. 
              <br />
              Please run the backend builder tool: <code>python3 tools/everything_matrix/build_index.py</code>
            </p>
          </div>
        )}

        {/* Legend / Key */}
        <footer className="grid grid-cols-2 gap-4 text-xs text-slate-500 md:grid-cols-4">
          <div className="space-y-1">
            <strong className="text-slate-700">Zone A: RGL Foundation</strong>
            <p>Grammar, Syntax, and Core Libraries required for compilation.</p>
          </div>
          <div className="space-y-1">
            <strong className="text-slate-700">Zone B: Lexicon</strong>
            <p>Vocabulary size, AI seeds, and external dictionary imports.</p>
          </div>
          <div className="space-y-1">
            <strong className="text-slate-700">Zone C: Application</strong>
            <p>Frontend profiles, UI assets, and backend API routes.</p>
          </div>
          <div className="space-y-1">
            <strong className="text-slate-700">Zone D: Quality</strong>
            <p>Compilation status and unit test pass rates.</p>
          </div>
        </footer>
      </div>
    </main>
  );
}