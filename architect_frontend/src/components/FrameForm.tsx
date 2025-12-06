// architect_frontend/src/components/FrameForm.tsx

'use client';

import React, { useCallback, useMemo, useState } from 'react';
import type { FrameContextConfig, FrameFieldConfig } from '../config/frameConfigs';
import type { GenerationResult } from '../lib/api';
import { generateFrame } from '../lib/api';

type FrameFormProps = {
  frameConfig: FrameContextConfig;
  initialLang?: string;
  initialValues?: Record<string, unknown>;
  onResult?: (result: GenerationResult) => void;
  onError?: (error: Error) => void;
  submitLabel?: string;
};

type FieldValue = string | number | boolean | null | undefined;

function buildInitialValues(
  frameConfig: FrameContextConfig,
  initialValues?: Record<string, unknown>,
): Record<string, FieldValue> {
  const values: Record<string, FieldValue> = {};

  for (const field of frameConfig.fields) {
    if (initialValues && field.name in initialValues) {
      values[field.name] = initialValues[field.name] as FieldValue;
    } else if (field.defaultValue !== undefined) {
      values[field.name] = field.defaultValue as FieldValue;
    } else if (field.inputType === 'checkbox') {
      values[field.name] = false;
    } else {
      values[field.name] = '';
    }
  }

  return values;
}

function isEmptyValue(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === 'string' && v.trim() === '') return true;
  if (Array.isArray(v) && v.length === 0) return true;
  return false;
}

export const FrameForm: React.FC<FrameFormProps> = ({
  frameConfig,
  initialLang,
  initialValues,
  onResult,
  onError,
  submitLabel = 'Generate',
}) => {
  const [lang, setLang] = useState<string>(initialLang ?? frameConfig.defaultLang);
  const [values, setValues] = useState<Record<string, FieldValue>>(() =>
    buildInitialValues(frameConfig, initialValues),
  );

  // Generation options (shared across all frames)
  const [register, setRegister] = useState<string>('');
  const [maxSentences, setMaxSentences] = useState<string>('');
  const [discourseMode, setDiscourseMode] = useState<string>('');
  const [seed, setSeed] = useState<string>('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const hasAdvancedOptions = useMemo(
    () => true, // we always show the block; it is small and generic
    [],
  );

  const handleFieldChange = useCallback(
    (
      event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
    ) => {
      const { name, type } = event.target;
      const value =
        type === 'checkbox'
          ? (event.target as HTMLInputElement).checked
          : event.target.value;

      setValues((prev) => ({
        ...prev,
        [name]: value,
      }));
    },
    [],
  );

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setErrorMessage(null);
      setIsSubmitting(true);

      try {
        // Build frame payload from field configs
        const framePayload: Record<string, unknown> = {};

        for (const field of frameConfig.fields) {
          let raw: unknown = values[field.name];

          // Basic required check
          if (field.required && isEmptyValue(raw)) {
            throw new Error(`Field "${field.label}" is required.`);
          }

          // JSON fields are stored as strings in the form and parsed on submit
          if (field.inputType === 'json') {
            const text = typeof raw === 'string' ? raw.trim() : '';
            if (text) {
              try {
                raw = JSON.parse(text);
              } catch {
                throw new Error(`Field "${field.label}" contains invalid JSON.`);
              }
            } else {
              raw = null;
            }
          }

          // Normalize numbers
          if (field.inputType === 'number' && typeof raw === 'string' && raw.trim() !== '') {
            const n = Number(raw);
            if (!Number.isFinite(n)) {
              throw new Error(`Field "${field.label}" must be a valid number.`);
            }
            raw = n;
          }

          if (!isEmptyValue(raw)) {
            framePayload[field.name] = raw;
          }
        }

        // Build GenerationOptions (all keys are optional)
        const options: Record<string, unknown> = {};
        if (register.trim()) options.register = register.trim();
        if (maxSentences.trim()) options.max_sentences = Number(maxSentences.trim());
        if (discourseMode.trim()) options.discourse_mode = discourseMode.trim();
        if (seed.trim()) options.seed = Number(seed.trim());

        const result = await generateFrame({
          lang,
          frameType: frameConfig.frameType,
          frame: framePayload,
          options: Object.keys(options).length ? options : undefined,
        });

        onResult?.(result);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred while generating.';
        setErrorMessage(message);
        if (err instanceof Error) {
          onError?.(err);
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      frameConfig.frameType,
      frameConfig.fields,
      lang,
      values,
      register,
      maxSentences,
      discourseMode,
      seed,
      onResult,
      onError,
    ],
  );

  const renderFieldControl = (field: FrameFieldConfig) => {
    const commonProps = {
      id: field.name,
      name: field.name,
      value: (values[field.name] ?? '') as string,
      onChange: handleFieldChange,
      placeholder: field.placeholder,
      className:
        'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
    };

    switch (field.inputType) {
      case 'textarea':
        return <textarea {...commonProps} rows={field.rows ?? 4} />;

      case 'select':
        return (
          <select
            {...commonProps}
            value={(values[field.name] ?? '') as string}
            className={commonProps.className}
          >
            <option value="">Select…</option>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );

      case 'checkbox':
        return (
          <input
            id={field.name}
            name={field.name}
            type="checkbox"
            checked={Boolean(values[field.name])}
            onChange={handleFieldChange}
            className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
        );

      case 'number':
        return (
          <input
            {...commonProps}
            type="number"
            value={values[field.name] === undefined ? '' : String(values[field.name])}
          />
        );

      case 'json':
        return (
          <textarea
            {...commonProps}
            rows={field.rows ?? 6}
            spellCheck={false}
          />
        );

      case 'text':
      default:
        return <input {...commonProps} type="text" />;
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Frame header */}
      <div className="border-b border-gray-200 pb-4">
        <h2 className="text-lg font-semibold text-gray-900">{frameConfig.label}</h2>
        {frameConfig.description && (
          <p className="mt-1 text-sm text-gray-600">{frameConfig.description}</p>
        )}
      </div>

      {/* Language + basic options */}
      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <label
            htmlFor="lang"
            className="block text-sm font-medium text-gray-700"
          >
            Language
          </label>
          <select
            id="lang"
            name="lang"
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {frameConfig.languages.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
          {frameConfig.languageHint && (
            <p className="mt-1 text-xs text-gray-500">{frameConfig.languageHint}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="register"
            className="block text-sm font-medium text-gray-700"
          >
            Register (style)
          </label>
          <select
            id="register"
            name="register"
            value={register}
            onChange={(e) => setRegister(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Default</option>
            <option value="neutral">Neutral</option>
            <option value="formal">Formal</option>
            <option value="informal">Informal</option>
          </select>
          <p className="mt-1 text-xs text-gray-500">
            Optional; falls back to language profile defaults if left empty.
          </p>
        </div>

        <div>
          <label
            htmlFor="maxSentences"
            className="block text-sm font-medium text-gray-700"
          >
            Max sentences
          </label>
          <input
            id="maxSentences"
            name="maxSentences"
            type="number"
            min={1}
            value={maxSentences}
            onChange={(e) => setMaxSentences(e.target.value)}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Optional upper bound; exact length is up to the engine.
          </p>
        </div>
      </div>

      {/* Advanced generation options */}
      {hasAdvancedOptions && (
        <details className="rounded-md border border-gray-200 bg-gray-50 p-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            Advanced generation options
          </summary>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <label
                htmlFor="discourseMode"
                className="block text-sm font-medium text-gray-700"
              >
                Discourse mode
              </label>
              <input
                id="discourseMode"
                name="discourseMode"
                type="text"
                value={discourseMode}
                onChange={(e) => setDiscourseMode(e.target.value)}
                placeholder='e.g. "intro", "summary"'
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Optional hint to steer the discourse role of the sentence.
              </p>
            </div>

            <div>
              <label
                htmlFor="seed"
                className="block text-sm font-medium text-gray-700"
              >
                Seed
              </label>
              <input
                id="seed"
                name="seed"
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Optional; reserved for future stochastic behavior / reproducibility.
              </p>
            </div>
          </div>
        </details>
      )}

      {/* Frame-specific fields */}
      <div className="space-y-6">
        {frameConfig.fields.map((field) => (
          <div key={field.name} className="space-y-1">
            <label
              htmlFor={field.name}
              className="block text-sm font-medium text-gray-700"
            >
              {field.label}
              {field.required && <span className="text-red-500"> *</span>}
            </label>
            {field.helpText && (
              <p className="text-xs text-gray-500 mb-1">{field.helpText}</p>
            )}
            {renderFieldControl(field)}
          </div>
        ))}
      </div>

      {/* Error + submit */}
      {errorMessage && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {errorMessage}
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <p className="text-xs text-gray-500">
          Fields marked with <span className="text-red-500">*</span> are required.
        </p>
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Generating…' : submitLabel}
        </button>
      </div>
    </form>
  );
};

export default FrameForm;
