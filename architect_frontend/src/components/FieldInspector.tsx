// architect_frontend/src/components/FieldInspector.tsx
"use client";

import React from "react";

// We define a flexible interface that matches the backend's FrameFieldMetadata
// (from architect_http_api/schemas/frames_metadata.py)
// but can also tolerate simple string values if passed from legacy code.
export interface FieldMeta {
  name: string;
  // Backend returns LocalizedLabel { text: string }, but we tolerate string
  label?: { text: string } | string;
  description?: { text: string } | string | null;
  // Backend uses 'kind', legacy used 'type'
  kind?: string;
  type?: string; 
  required?: boolean;
  // Backend might pass examples as any JSON
  example?: unknown;
  group?: string;
}

interface FieldInspectorProps {
  /**
   * The field config for the currently focused/hovered field.
   * Pass `null` when no field is active.
   */
  activeField: FieldMeta | null;

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

// Helper to extract text from string or LocalizedLabel object
function getLocalizedText(val: { text: string } | string | null | undefined): string {
  if (!val) return "";
  if (typeof val === "string") return val;
  return val.text || "";
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
      <aside className="hidden xl:block w-80 shrink-0 border-l border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
        <p className="text-xs text-slate-500">
          Focus a field in the form to see structured guidance here.
        </p>
      </aside>
    );
  }

  // Normalize data from the potentially diverse activeField shape
  const rawLabel = activeField?.label;
  const label = rawLabel ? getLocalizedText(rawLabel) : (fieldKey ?? "");
  
  const description = getLocalizedText(activeField?.description);
  
  // Support both new 'kind' and old 'type' properties
  const fieldType = activeField?.kind || activeField?.type;
  
  const required = activeField?.required;
  const group = activeField?.group;

  // Example might be a string or a complex object in the new backend
  const rawExample = activeField?.example;
  const example =
    typeof rawExample === "string"
      ? rawExample
      : rawExample
      ? JSON.stringify(rawExample, null, 2)
      : undefined;

  const hasMeta =
    !!description ||
    !!example ||
    !!group ||
    typeof value !== "undefined" ||
    !!error ||
    !!extraHelp;

  return (
    <aside className="hidden xl:flex flex-col w-80 shrink-0 border-l border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 overflow-y-auto h-full">
      {/* Header */}
      <div className="mb-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-slate-900 text-sm truncate" title={label}>
            {label}
          </h2>
          <div className="flex items-center gap-1 shrink-0">
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
          {fieldType && (
            <span className="text-[11px] uppercase tracking-wide text-slate-400">
              {fieldType}
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
          <p className="text-xs text-slate-800 whitespace-pre-wrap font-mono">
            {example}
          </p>
        </section>
      )}

      {/* Current value */}
      {typeof value !== "undefined" && value !== null && value !== "" && (
        <section className="mb-3 rounded-md bg-white border border-slate-200 px-3 py-2">
          <h3 className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Current value
          </h3>
          <p className="text-xs text-slate-800 break-words whitespace-pre-wrap max-h-32 overflow-auto font-mono">
            {typeof value === "string"
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