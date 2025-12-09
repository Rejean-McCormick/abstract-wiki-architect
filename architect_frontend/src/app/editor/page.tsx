'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

interface Language {
  code: string;
  name: string;
}

export default function EditorPage() {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [lang, setLang] = useState('zul');
  const [frameType, setFrameType] = useState('entity.person');
  const [name, setName] = useState('Shaka');
  const [profession, setProfession] = useState('Warrior');
  const [nationality, setNationality] = useState('Zulu');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  // Load languages on mount
  useEffect(() => {
    const fetchLangs = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const res = await axios.get(`${apiUrl}/languages`);
        setLanguages(res.data);
      } catch (e) { console.error("Failed to load languages"); }
    };
    fetchLangs();
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    setResult('');
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const payload = {
        lang: lang,
        frame: {
          frame_type: frameType,
          name: name,
          profession: profession,
          nationality: nationality
        }
      };
      const res = await axios.post(`${apiUrl}/generate`, payload);
      setResult(res.data.text);
    } catch (err: any) {
      setResult('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[calc(100vh-140px)]">
      {/* Input Column */}
      <div className="bg-slate-900 border border-slate-800 p-6 rounded-lg flex flex-col gap-5 shadow-xl">
        <h2 className="text-xl font-bold text-blue-400">📝 Frame Input</h2>
        
        <div className="space-y-4">
          <div>
            <label className="text-xs uppercase font-bold text-slate-500">Language</label>
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="w-full mt-1 bg-slate-950 border border-slate-700 rounded p-2 text-slate-200">
              {languages.map(l => <option key={l.code} value={l.code}>{l.name} ({l.code})</option>)}
            </select>
          </div>

          <div>
             <label className="text-xs uppercase font-bold text-slate-500">Name</label>
             <input value={name} onChange={e => setName(e.target.value)} className="w-full mt-1 bg-slate-950 border border-slate-700 rounded p-2 text-slate-200" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
               <label className="text-xs uppercase font-bold text-slate-500">Profession</label>
               <input value={profession} onChange={e => setProfession(e.target.value)} className="w-full mt-1 bg-slate-950 border border-slate-700 rounded p-2 text-slate-200" />
            </div>
            <div>
               <label className="text-xs uppercase font-bold text-slate-500">Nationality</label>
               <input value={nationality} onChange={e => setNationality(e.target.value)} className="w-full mt-1 bg-slate-950 border border-slate-700 rounded p-2 text-slate-200" />
            </div>
          </div>
          
          <div className="flex-1"></div>

          <button onClick={handleGenerate} disabled={loading} className="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold shadow-lg transition-all disabled:opacity-50">
            {loading ? 'Thinking...' : 'Realize Text ⚡'}
          </button>
        </div>
      </div>

      {/* Output Column */}
      <div className="bg-slate-900 border border-slate-800 p-6 rounded-lg shadow-xl flex flex-col">
        <h2 className="text-xl font-bold text-green-400 mb-4">💬 Output</h2>
        <div className={`flex-1 rounded border-2 border-dashed flex items-center justify-center p-8 text-center ${result ? 'border-green-500/30 bg-green-950/10' : 'border-slate-800 bg-slate-950/30'}`}>
          {result ? <p className="text-3xl font-serif text-slate-100">{result}</p> : <p className="text-slate-600">Waiting for generation...</p>}
        </div>
      </div>
    </div>
  );
}