"use client";

import React, { useCallback, useMemo, useState, FormEvent } from "react";
import { 
  architectApi, 
  IntentRequest, 
  IntentResponse, 
  AIMessage, 
  AIFramePatch 
} from "../lib/api";

export type AIPanelMode = "guide" | "explain" | "suggest_fields";

export interface AIPanelProps {
  /**
   * The type of entity being edited (e.g. "construction", "bio", "function").
   */
  entityType: string;

  /**
   * ID of the entity if we are editing an existing one.
   */
  entityId?: string;

  /**
   * Current form values.
   */
  currentValues: Record<string, unknown>;

  /**
   * Target language code (e.g. "en", "fr").
   */
  language?: string;

  /**
   * Hook to apply AI-suggested updates back into the form.
   */
  onApplySuggestion?: (updates: Record<string, unknown>) => void;

  className?: string;
}

/**
 * Right-side “Ask the Architect” helper panel.
 * Connects to POST /ai/intent via architectApi.
 */
const AIPanel: React.FC<AIPanelProps> = ({
  entityType,
  entityId,
  currentValues,
  language = "en",
  onApplySuggestion,
  className,
}) => {
  const [mode, setMode] = useState<AIPanelMode>("guide");
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Store the accumulated updates from patches
  const [lastSuggestionPayload, setLastSuggestionPayload] =
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
        return "Suggest / refine fields";
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

      // 1. Add User Message to Chat
      const userMsg: AIMessage = { role: "user", content: trimmedInput };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");

      try {
        // 2. Build Request
        // Matches the IntentRequest interface in lib/api.ts
        const requestPayload: IntentRequest = {
          message: trimmedInput,
          lang: language,
          workspace_slug: entityId,
          context_frame: {
            frame_type: entityType,
            payload: currentValues
          }
        };

        // 3. Call API
        const response: IntentResponse = await architectApi.processIntent(requestPayload);

        // 4. Handle Response
        // The backend returns a list of messages (e.g. reasoning steps + final answer)
        if (response.assistant_messages && response.assistant_messages.length > 0) {
            setMessages((prev) => [...prev, ...response.assistant_messages]);
        } else {
            // Fallback if no messages returned
            setMessages((prev) => [...prev, { role: "assistant", content: "Done." }]);
        }

        // 5. Handle Patches
        // Convert the list of patches into a simplified object for the parent form
        if (response.patches && response.patches.length > 0) {
          const updates: Record<string, unknown> = {};
          
          response.patches.forEach((patch: AIFramePatch) => {
             // Basic support for top-level fields. 
             // Note: Deep nested patching would require a more complex merger 
             // or a library like immer/lodash.set, but this covers the 80% case.
             updates[patch.path] = patch.value;
          });

          setLastSuggestionPayload(updates);
        } else {
          setLastSuggestionPayload(null);
        }

      } catch (e: unknown) {
        console.error("AI panel error", e);
        setError(
          e instanceof Error 
            ? e.message 
            : "The Architect assistant could not be reached."
        );
      } finally {
        setIsLoading(false);
      }
    },
    [canSend, trimmedInput, entityId, currentValues, language, entityType]
  );

  const handleApplySuggestion = useCallback(() => {
    if (!lastSuggestionPayload || !onApplySuggestion) return;
    onApplySuggestion(lastSuggestionPayload);
    
    setLastSuggestionPayload(null); 
    setMessages(prev => [...prev, { role: "system", content: "Suggestion applied to form." }]);
  }, [lastSuggestionPayload, onApplySuggestion]);

  const handleQuickPrompt = useCallback(
    (preset: "explain_frame" | "suggest_missing" | "improve_output") => {
      switch (preset) {
        case "explain_frame":
          setMode("explain");
          setInput(
            "Explain the current configuration of this entity. Are there any inconsistencies?"
          );
          break;
        case "suggest_missing":
          setMode("suggest_fields");
          setInput(
            "Check for missing or underspecified fields in this entity and suggest values."
          );
          break;
        case "improve_output":
          setMode("guide");
          setInput(
            "I want to improve the quality of this definition. What should I change?"
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
            Architect AI
          </h2>
          <p className="text-xs text-slate-500">
            Context: {entityType} {language ? `(${language})` : ""}
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
            <option value="guide">Guide / Q&A</option>
            <option value="explain">Explain</option>
            <option value="suggest_fields">Suggest</option>
          </select>
        </div>
      </header>

      {/* Quick Action Buttons */}
      <section className="mb-3 flex gap-2">
        <button
          type="button"
          onClick={() => handleQuickPrompt("explain_frame")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Explain
        </button>
        <button
          type="button"
          onClick={() => handleQuickPrompt("suggest_missing")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Suggest
        </button>
        <button
          type="button"
          onClick={() => handleQuickPrompt("improve_output")}
          className="flex-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
        >
          Improve
        </button>
      </section>

      {/* Chat Area */}
      <section className="mb-3 flex-1 overflow-hidden rounded-md border border-slate-200 bg-slate-50">
        <div className="h-full max-h-64 overflow-y-auto p-2 text-xs">
          {messages.length === 0 ? (
            <p className="text-slate-500 italic">
              No conversation yet. Ask the Architect about this entity...
            </p>
          ) : (
            <ul className="space-y-3">
              {messages.map((m, idx) => (
                <li
                  key={idx}
                  className={`flex flex-col ${
                    m.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div className={`max-w-[90%] rounded-md p-2 shadow-sm ${
                      m.role === "user" 
                        ? "bg-sky-100 text-sky-900" 
                        : m.role === "system"
                        ? "bg-slate-200 text-slate-600 italic"
                        : "bg-white text-slate-900"
                    }`}
                  >
                    <div className="mb-1 text-[9px] font-bold uppercase tracking-wide opacity-50">
                      {m.role === "user" ? "You" : "Architect"}
                    </div>
                    <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                  </div>
                </li>
              ))}
              {isLoading && (
                <li className="flex items-start">
                   <div className="rounded-md bg-white p-2 text-slate-500 shadow-sm">
                      <span className="animate-pulse">Thinking...</span>
                   </div>
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

      {/* Suggestion Banner */}
      {lastSuggestionPayload && onApplySuggestion && (
        <div className="mb-2 flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 shadow-sm">
          <div className="mr-2">
            <p className="text-[11px] font-medium text-emerald-800">
              Suggestion Available
            </p>
            <p className="text-[10px] text-emerald-600">
              The Architect proposed updates to the form fields.
            </p>
          </div>
          <button
            type="button"
            onClick={handleApplySuggestion}
            className="whitespace-nowrap rounded bg-emerald-600 px-3 py-1.5 text-[11px] font-medium text-white shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1"
          >
            Apply Changes
          </button>
        </div>
      )}

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="mt-auto flex flex-col gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          className="w-full resize-none rounded-md border border-slate-200 bg-white px-2 py-2 text-xs text-slate-900 shadow-inner focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          placeholder="Type your instructions..."
        />
        <div className="flex items-center justify-end">
          <button
            type="submit"
            disabled={!canSend}
            className={`rounded-md px-4 py-1.5 text-xs font-semibold text-white transition-colors ${
              canSend
                ? "bg-sky-600 hover:bg-sky-700 shadow-sm"
                : "cursor-not-allowed bg-slate-300"
            }`}
          >
            {isLoading ? "Sending..." : "Send"}
          </button>
        </div>
      </form>
    </aside>
  );
};

export default AIPanel;