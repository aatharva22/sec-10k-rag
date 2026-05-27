"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, postQuery } from "@/lib/api";
import { REFUSAL_TEXT, type Message } from "@/lib/types";
import Composer from "./Composer";
import ExampleChips from "./ExampleChips";
import MessageBubble from "./MessageBubble";

function makeId(): string {
  // Avoid pulling in a uuid lib for one ID per message.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inFlight, setInFlight] = useState(false);

  const scrollerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const ask = useCallback(async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed) return;

    const userMsg: Message = {
      id: makeId(),
      role: "user",
      content: trimmed,
      status: "ok",
    };
    const assistantId = makeId();
    const pendingMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      status: "pending",
      sourceQuestion: trimmed,
    };

    setMessages((prev) => [...prev, userMsg, pendingMsg]);
    setInFlight(true);

    try {
      const data = await postQuery(trimmed);
      const isRefusal =
        data.citations.length === 0 && data.answer.trim() === REFUSAL_TEXT;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: data.answer,
                citations: data.citations,
                status: isRefusal ? "refusal" : "ok",
              }
            : m,
        ),
      );
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 503
            ? "Backend is temporarily unavailable. Please retry."
            : err.message
          : err instanceof Error
            ? err.message
            : "Unexpected error.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, status: "error", error: msg }
            : m,
        ),
      );
    } finally {
      setInFlight(false);
    }
  }, []);

  const handleChipPick = useCallback(
    (q: string) => {
      // Immediately submit chip questions per spec.
      void ask(q);
    },
    [ask],
  );

  const handleRetry = useCallback(
    (q: string) => {
      // Drop the failed assistant message + its preceding user echo,
      // then re-ask so the conversation reads cleanly.
      setMessages((prev) => {
        // Find the trailing error message tied to q.
        let cutFrom = prev.length;
        for (let i = prev.length - 1; i >= 0; i--) {
          const m = prev[i];
          if (
            m.role === "assistant" &&
            m.status === "error" &&
            m.sourceQuestion === q
          ) {
            // Also strip the user message immediately before it.
            cutFrom = i - 1 >= 0 && prev[i - 1].role === "user" ? i - 1 : i;
            break;
          }
        }
        return prev.slice(0, cutFrom);
      });
      void ask(q);
    },
    [ask],
  );

  const isEmpty = messages.length === 0;

  return (
    <>
      <div
        ref={scrollerRef}
        className="flex-1 overflow-y-auto"
        aria-live="polite"
      >
        <div className="mx-auto max-w-3xl px-4 py-6">
          {isEmpty ? (
            <section className="rounded-2xl border border-border bg-surface p-6 sm:p-8">
              <div className="flex items-start gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent/15 text-accent">
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                  >
                    <path
                      fill="currentColor"
                      d="M4 4h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8l-4 4V4zm2 2v12.17L7.17 18H16a 1 1 0 0 0 1-1V6a 1 1 0 0 0-1-1H6z"
                    />
                  </svg>
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold tracking-tight">
                    Ask the 10-K corpus
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    Ask a question about Apple, Microsoft, Amazon, Tesla, or
                    NVIDIA 10-K filings (FY2022&ndash;2024). Answers are
                    grounded in retrieved excerpts, with citations linking
                    back to the original filing on EDGAR.
                  </p>
                </div>
              </div>
              <div className="mt-5">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Try one of these
                </div>
                <ExampleChips onPick={handleChipPick} disabled={inFlight} />
              </div>
            </section>
          ) : (
            <ol className="space-y-4">
              {messages.map((m) => (
                <li key={m.id}>
                  <MessageBubble message={m} onRetry={handleRetry} />
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 border-t border-border bg-bg/95 backdrop-blur">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <Composer onSubmit={(q) => void ask(q)} disabled={inFlight} />
          <div className="mt-1.5 px-1 text-[11px] text-muted">
            Press <kbd className="rounded bg-surface-2 px-1 py-0.5">Enter</kbd>{" "}
            to send,{" "}
            <kbd className="rounded bg-surface-2 px-1 py-0.5">Shift</kbd>+
            <kbd className="rounded bg-surface-2 px-1 py-0.5">Enter</kbd> for a
            new line.
          </div>
        </div>
      </div>

    </>
  );
}
