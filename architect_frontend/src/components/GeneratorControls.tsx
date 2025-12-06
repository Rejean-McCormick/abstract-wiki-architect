// architect_frontend/src/components/GeneratorControls.tsx
"use client";

import React from "react";

// Local definition matching the NLG options we use here
export interface GenerationOptions {
  register?: string | null;
  max_sentences?: number | null;
  discourse_mode?: string | null;
  seed?: number | null;
}

interface GeneratorControlsProps {
  options: GenerationOptions;
  onChange: (newOptions: GenerationOptions) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Reusable controls for NLG parameters (Register, Length, etc.).
 * Maps conceptually to `nlg.api.GenerationOptions` in the backend.
 */
export default function GeneratorControls({
  options,
  onChange,
  disabled = false,
  className = "",
}: GeneratorControlsProps) {
  const handleChange = (field: keyof GenerationOptions, value: unknown) => {
    onChange({
      ...options,
      [field]: value,
    });
  };

  return (
    <div
      className={`space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4 ${className}`}
    >
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Generation Settings
      </h3>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Register (Style) */}
        <div>
          <label
            htmlFor="register"
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            Register
          </label>
          <select
            id="register"
            value={options.register ?? ""}
            disabled={disabled}
            onChange={(e) => handleChange("register", e.target.value || null)}
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-60"
          >
            <option value="">Default (Neutral)</option>
            <option value="formal">Formal</option>
            <option value="informal">Informal</option>
            <option value="simple">Simple / Plain</option>
          </select>
        </div>

        {/* Max Sentences */}
        <div>
          <label
            htmlFor="max_sentences"
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            Max Sentences
          </label>
          <input
            id="max_sentences"
            type="number"
            min={1}
            max={20}
            disabled={disabled}
            value={options.max_sentences ?? ""}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              handleChange("max_sentences", isNaN(val) ? null : val);
            }}
            placeholder="Auto"
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-60"
          />
        </div>

        {/* Discourse Mode */}
        <div>
          <label
            htmlFor="discourse_mode"
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            Discourse Mode
          </label>
          <select
            id="discourse_mode"
            value={options.discourse_mode ?? ""}
            disabled={disabled}
            onChange={(e) =>
              handleChange("discourse_mode", e.target.value || null)
            }
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-60"
          >
            <option value="">Standard</option>
            <option value="intro">Intro / Lead</option>
            <option value="summary">Summary</option>
            <option value="timeline">Timeline Entry</option>
          </select>
        </div>

        {/* Seed (Advanced) */}
        <div>
          <label
            htmlFor="seed"
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            Seed (Deterministic)
          </label>
          <input
            id="seed"
            type="number"
            disabled={disabled}
            value={options.seed ?? ""}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              handleChange("seed", isNaN(val) ? null : val);
            }}
            placeholder="Random"
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:opacity-60"
          />
        </div>
      </div>
    </div>
  );
}
