"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
  /** Set by parent to programmatically prefill (e.g. example chip click). */
  prefill?: string;
  /** Increment to force a re-application of `prefill` even with the same value. */
  prefillKey?: number;
}

const MAX_ROWS = 6;
const LINE_HEIGHT_PX = 20;
const PADDING_Y_PX = 16; // py-2 top+bottom

export default function Composer({ onSubmit, disabled, prefill, prefillKey }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Apply external prefills.
  useEffect(() => {
    if (typeof prefill === "string") {
      setValue(prefill);
      // Move caret to end on next tick.
      requestAnimationFrame(() => {
        const el = ref.current;
        if (el) {
          el.focus();
          el.selectionStart = el.selectionEnd = el.value.length;
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillKey]);

  // Autosize up to MAX_ROWS lines.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = LINE_HEIGHT_PX * MAX_ROWS + PADDING_Y_PX;
    const next = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [value]);

  function trySubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      trySubmit();
    }
  }

  const canSubmit = value.trim().length > 0 && !disabled;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        trySubmit();
      }}
      className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2"
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Ask about Apple, Microsoft, Amazon, Tesla, or NVIDIA 10-K filings…"
        className="block w-full resize-none bg-transparent px-2 py-2 text-sm leading-5 text-text placeholder:text-muted focus:outline-none"
        disabled={disabled}
        aria-label="Ask a question"
      />
      <button
        type="submit"
        disabled={!canSubmit}
        className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-accent px-3 text-sm font-medium text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? (
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-4 w-4 animate-spin"
          >
            <circle
              cx="12"
              cy="12"
              r="9"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray="40 60"
              fill="none"
            />
          </svg>
        ) : (
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4">
            <path
              fill="currentColor"
              d="M3.4 20.4 22 12 3.4 3.6 3.39 10.2 17 12 3.39 13.8z"
            />
          </svg>
        )}
        <span>{disabled ? "Sending" : "Send"}</span>
      </button>
    </form>
  );
}
