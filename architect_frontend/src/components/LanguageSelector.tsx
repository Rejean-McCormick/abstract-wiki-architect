// architect_frontend/src/components/LanguageSelector.tsx

import React, { useEffect, useState } from 'react';
import { getLanguages } from '../services/api';
import { Language } from '../types/language';

interface LanguageSelectorProps {
  /**
   * The currently selected language code (e.g. "zul").
   */
  selectedCode: string;
  
  /**
   * Callback fired when the user selects a new language.
   */
  onSelect: (lang: Language) => void;
  
  /**
   * Optional custom class name for styling.
   */
  className?: string;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  selectedCode,
  onSelect,
  className = '',
}) => {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadLangs() {
      try {
        const data = await getLanguages();
        if (mounted) {
          setLanguages(data);
          setLoading(false);
        }
      } catch (err: any) {
        if (mounted) {
          console.error("Failed to load languages:", err);
          setError("Failed to load languages.");
          setLoading(false);
        }
      }
    }

    loadLangs();

    return () => {
      mounted = false;
    };
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const code = e.target.value;
    const lang = languages.find((l) => l.code === code);
    if (lang) {
      onSelect(lang);
    }
  };

  if (loading) {
    return <span className="text-gray-500 text-sm">Loading languages...</span>;
  }

  if (error) {
    return <span className="text-red-500 text-sm">Error: {error}</span>;
  }

  return (
    <div className={`inline-block relative ${className}`}>
      <label htmlFor="language-select" className="sr-only">
        Select Language
      </label>
      <select
        id="language-select"
        value={selectedCode}
        onChange={handleChange}
        className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md shadow-sm bg-white text-gray-900 border"
      >
        <option value="" disabled>
          -- Select a Language --
        </option>
        
        {/* Tier 1: Core / Mature Languages First (Optional heuristic) */}
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.name} ({lang.code}) {lang.z_id ? `[${lang.z_id}]` : ''}
          </option>
        ))}
      </select>
    </div>
  );
};