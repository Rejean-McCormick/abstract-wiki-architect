// architect_frontend/src/components/FieldInspector.tsx
'use client';

import React from 'react';
import type { FrameFieldConfig } from '@/config/frameConfigs';

interface FieldInspectorProps {
  /**
   * The field config for the currently focused/hovered field.
   * Pass `null` when no field is active.
   */
  activeField: FrameFieldConfig | null;

  /**
   * Raw key of the field (e.g. "topic", "time_span").
   * Used as a fallback label if config is partial.
   */
  fieldKey?: string | null;

  /**
   * Current value of the field in the form.
   */
  value?: unknown;

  /**
   * Validation error for this field, if any.
   */
  error?: string | null;

  /**
   * Optional extra docs, e.g. from backend or AI explanation endpoint.
   */
  extraHelp?: string | null;
}

const FieldInspector: React.FC<FieldInspectorProps> = ({
  activeField,
  fieldKey,
  value,
  error,
  extraHelp,
}) => {
  const hasActiveField = !!activeField || !!fieldKey;

  if (!hasActiveField) {
    return (
      <aside className="hidden xl:block w-80 border-l border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
        <p className="text-xs text-slate-500">
          Focus a field in the form to see structured guidance here.
        </p>
      </aside>
    );
  }

  const label = activeField?.label ?? fieldKey ?? '';
  const description = activeField?.description;
  const type = activeField?.type;
  const required = activeField?.required;
  const example = (activeField as any)?.example as string | undefined;
  const group = (activeField as any)?.group as string | undefined;

  const hasMeta =
    !!description || !!example || !!group || typeof value !== 'undefined' || !!error || !!extraHelp;

  return (
    <aside className="hidden xl:flex flex-col w-80 border-l border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
      {/* Header */}
      <div className="mb-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-slate-900 text-sm truncate">
            {label}
          </h2>
          <div className="flex items-center gap-1">
            {group && (
              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-500">
                {group}
              </span>
            )}
            {required && (
              <span className="rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-700">
                required
              </span>
            )}
          </div>
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          {type && (
            <span className="text-[11px] uppercase tracking-wide text-slate-400">
              {type}
            </span>
          )}
          {fieldKey && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-mono text-slate-500">
              {fieldKey}
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      {description && (
        <section className="mb-3">
          <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            How this field is used
          </h3>
          <p className="text-xs leading-relaxed text-slate-700 whitespace-pre-wrap">
            {description}
          </p>
        </section>
      )}

      {/* Example */}
      {example && (
        <section className="mb-3 rounded-md bg-white border border-slate-200 px-3 py-2">
          <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Example
          </h3>
          <p className="text-xs text-slate-800 whitespace-pre-wrap">
            {example}
          </p>
        </section>
      )}

      {/* Current value */}
      {typeof value !== 'undefined' && value !== null && value !== '' && (
        <section className="mb-3 rounded-md bg-white border border-slate-200 px-3 py-2">
          <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Current value
          </h3>
          <p className="text-xs text-slate-800 break-words whitespace-pre-wrap max-h-32 overflow-auto">
            {typeof value === 'string'
              ? value
              : JSON.stringify(value, null, 2)}
          </p>
        </section>
      )}

      {/* Extra help (e.g. AI explanation) */}
      {extraHelp && (
        <section className="mb-3 rounded-md bg-indigo-50 border border-indigo-100 px-3 py-2">
          <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-indigo-700">
            Guidance
          </h3>
          <p className="text-xs text-indigo-900 whitespace-pre-wrap">
            {extraHelp}
          </p>
        </section>
      )}

      {/* Error */}
      {error && (
        <section className="mt-auto rounded-md border border-rose-200 bg-rose-50 px-3 py-2">
          <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-rose-700">
            Issues
          </h3>
          <p className="text-xs text-rose-800 whitespace-pre-wrap">
            {error}
          </p>
        </section>
      )}

      {/* Fallback when meta is thin */}
      {!hasMeta && (
        <p className="mt-2 text-xs text-slate-500">
          No additional documentation for this field yet. You can still use it
          as a free-form hint to the NLG engine.
        </p>
      )}
    </aside>
  );
};

export default FieldInspector;
