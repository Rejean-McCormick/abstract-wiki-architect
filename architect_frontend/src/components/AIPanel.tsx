"use client";

import React, { useCallback, useMemo, useState, FormEvent } from "react";
import { sendArchitectRequest } from "../lib/aiApi";

export type AIPanelMode = "guide" | "explain" | "suggest_fields";

export interface AIPanelProps {
  /**
   * Current frame slug (e.g. "bio", "event", "definition").
   * Used to give the AI some semantic context.
   */
  frameSlug: string;

  /**
   * Current form values for the selected frame.
   * This is sent as context so the AI can suggest improvements or missing fields.
   */
  frameValues: Record<string, unknown>;

  /**
   * Target language code (e.g. "en", "fr", "sw").
   */
  language: string;

  /**
   * Optional hook: apply AI-suggested updates back into the form.
   */
  onApplySuggestion?: (updates: Record<string, unknown>) => void;

  /**
   * Optional className to let parents control panel sizing/layout.
   */
  className?: string;
}

interface AIMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ArchitectAIRequestPayload {
  mode: AIPanelMode;
  userMessage: string;
  frameSlug: string;
  frameValues: Record<string, unknown>;
  language: string;
}

export interface ArchitectAIResponsePayload {
  assistantMessage: string;
  /**
   * Optional patch for frame values (e.g. fill missing fields, tweak lemmas).
   */
  suggestedFrameValues?: Record<string, unknown>;
}

/**
 * Right-side “Ask the Architect” helper panel.
 * Orchestrates interaction with the backend AI via `sendArchitectRequest`.
 */
const AIPanel: React.FC<AIPanelProps> = ({
  frameSlug,
  frameValues,
  language,
  onApplySuggestion,
  className,
}) => {
  const [mode, setMode] = useState<AIPanelMode>("guide");
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSuggestion, setLastSuggestion] =
    useState<Record<string, unknown> | null>(null);

  const trimmedInput = input.trim();
  const canSend = trimmedInput.length > 0 && !isLoading;

  const modeLabel = useMemo(() => {
    switch (mode) {
      case "guide":
        return "Guide / open question";
      case "explain":
        return "Explain current setup";
      case "suggest_fields":
        return "Suggest / refine frame fields";
      default:
        return mode;
    }
  }, [mode]);

  const handleSubmit = useCallback(
    async (evt: FormEvent) => {
      evt.preventDefault();
      if (!canSend) return;

      setIsLoading(true);
      setError(null);

      const userMsg: AIMessage = { role: "user", content: trimmedInput };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");

      try {
        const payload: ArchitectAIRequestPayload = {
          mode,
          userMessage: trimmedInput,
          frameSlug,
          frameValues,
          language,
        };

        const response: ArchitectAIResponsePayload = await sendArchitectRequest(
          payload
        );

        const assistantMsg: AIMessage = {
          role: "assistant",
          content: response.assistantMessage,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setLastSuggestion(response.suggestedFrameValues ?? null);
      } catch (e: unknown) {
        console.error("AI panel error", e);
        setError(
          "The Architect assistant could not be reached. Check the backend URL and try again."
        );
      } finally {
        setIsLoading(false);
      }
    },
    [canSend, trimmedInput, mode, frameSlug, frameValues, language]
  );

  const handleApplySuggestion = useCallback(() => {
    if (!lastSuggestion || !onApplySuggestion) return;
    onApplySuggestion(lastSuggestion);
  }, [lastSuggestion, onApplySuggestion]);

  const handleQuickPrompt = useCallback(
    (preset: "explain_frame" | "suggest_missing" | "improve_output") => {
      switch (preset) {
        case "explain_frame":
          setMode("explain");
          setInput(
            "Explain how this current semantic frame will be realized in the target language, and point out any suspicious or underspecified fields."
          );
          break;
        case "suggest_missing":
          setMode("suggest_fields");
          setInput(
            "Look at my current frame values and suggest any missing or low-quality fields, with concrete replacements."
          );
          break;
        case "improve_output":
          setMode("guide");
          setInput(
            "I am not satisfied with the output. Suggest specific tweaks to the frame that would improve fluency and naturalness."
          );
          break;
      }
    },
    []
  );

  return (
    <aside
      className={[
        "flex h-full flex-col rounded-lg border border-slate-200 bg-white/80 p-4 shadow-sm",
        "backdrop-blur",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <header className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Architect AI Panel
          </h2>
          <p className="text-xs text-slate-500">
            Ask questions, get suggestions, and refine the frame with help from
            the assistant.
          </p>
        </div>

        <div className="flex flex-col items-end gap-1">
          <label className="text-[10px] uppercase tracking-wide text-slate-500">
            Mode
          </label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as AIPanelMode)}
            className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800 shadow-sm"
          >
            <option value="guide">Guide / Q&amp;A</option>
            <option value="explain">Explain setup</option>
            <option value="suggest_fields">Suggest fields</option>
          </select>
        </div>
      </header>

      <section className="mb-3 flex gap-2">
        <button
          type="button"
          onClick={() => handleQuickPrompt("explain_frame")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Explain this frame
        </button>
        <button
          type="button"
          onClick={() => handleQuickPrompt("suggest_missing")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Suggest missing fields
        </button>
        <button
          type="button"
          onClick={() => handleQuickPrompt("improve_output")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Improve output
        </button>
      </section>

      <section className="mb-3 flex-1 overflow-hidden rounded-md border border-slate-200 bg-slate-50">
        <div className="h-full max-h-64 overflow-y-auto p-2 text-xs">
          {messages.length === 0 ? (
            <p className="text-slate-500">
              No conversation yet. Choose a quick prompt above or type your own
              question about this frame, the target language, or the generated
              text.
            </p>
          ) : (
            <ul className="space-y-2">
              {messages.map((m, idx) => (
                <li
                  key={idx}
                  className={
                    m.role === "user"
                      ? "text-slate-800"
                      : "rounded-md bg-white p-2 text-slate-900 shadow-sm"
                  }
                >
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {m.role === "user" ? "You" : "Architect"}
                  </div>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </li>
              ))}
              {isLoading && (
                <li className="rounded-md bg-white p-2 text-slate-500 shadow-sm">
                  <div className="text-[10px] font-semibold uppercase tracking-wide">
                    Architect
                  </div>
                  <div className="mt-1 text-xs">Thinking…</div>
                </li>
              )}
            </ul>
          )}
        </div>
      </section>

      {error && (
        <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </div>
      )}

      {lastSuggestion && onApplySuggestion && (
        <div className="mb-2 flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1">
          <p className="text-[11px] text-emerald-800">
            This reply includes suggested updates for the current frame.
          </p>
          <button
            type="button"
            onClick={handleApplySuggestion}
            className="rounded-sm bg-emerald-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-emerald-700"
          >
            Apply suggestion
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-auto flex flex-col gap-2">
        <label className="text-[11px] text-slate-600">
          Ask the Architect
          <span className="ml-1 text-[10px] text-slate-400">
            ({modeLabel})
          </span>
        </label>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          className="w-full resize-none rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-900 shadow-inner focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
          placeholder="Example: “Why did the system choose this word order?” or “Suggest a more natural wording for this biography.”"
        />
        <div className="flex items-center justify-between gap-2">
          <div className="text-[10px] text-slate-400">
            Context: frame <code>{frameSlug}</code>, lang {language}
          </div>
          <button
            type="submit"
            disabled={!canSend}
            className={`rounded-md px-3 py-1 text-xs font-medium text-white ${
              canSend
                ? "bg-sky-600 hover:bg-sky-700"
                : "cursor-not-allowed bg-slate-300"
            }`}
          >
            {isLoading ? "Sending…" : "Send to Architect"}
          </button>
        </div>
      </form>
    </aside>
  );
};

export default AIPanel;
