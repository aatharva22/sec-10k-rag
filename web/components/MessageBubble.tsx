"use client";

import { useState } from "react";
import type { Message } from "@/lib/types";
import Citations from "./Citations";

interface Props {
  message: Message;
  onRetry?: (question: string) => void;
}

function formatSeconds(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function AnswerMeta({ message, expanded, onToggle }: {
  message: Message;
  expanded: boolean;
  onToggle: () => void;
}) {
  const parts: string[] = [];
  if (message.timing) {
    parts.push(`Answered in ${formatSeconds(message.timing.total_ms)}`);
  }
  if (typeof message.retrievedCount === "number" && message.retrievedCount > 0) {
    parts.push(`${message.retrievedCount} chunk${message.retrievedCount === 1 ? "" : "s"} retrieved`);
  }
  if (parts.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/60 pt-2 text-[11px] text-muted">
      <span>{parts.join(" · ")}</span>
      {message.timing ? (
        <span
          className="font-mono"
          title={`retrieve=${message.timing.retrieve_ms}ms · generate=${message.timing.generate_ms}ms`}
        >
          ({message.timing.retrieve_ms}ms retrieve / {message.timing.generate_ms}ms generate)
        </span>
      ) : null}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="ml-auto rounded border border-border bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-text/80 hover:border-accent/60 hover:text-text"
      >
        {expanded ? "Hide" : "Show"} retrieval details
      </button>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-2 py-1">
      <div className="shimmer h-3 w-11/12 rounded" />
      <div className="shimmer h-3 w-10/12 rounded" />
      <div className="shimmer h-3 w-8/12 rounded" />
    </div>
  );
}

export default function MessageBubble({ message, onRetry }: Props) {
  const [showDetails, setShowDetails] = useState(false);
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-sm text-white shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // assistant
  if (message.status === "pending") {
    return (
      <div className="flex justify-start">
        <div className="w-full max-w-[80%] rounded-2xl rounded-bl-md border border-border bg-surface px-3.5 py-2.5">
          <Skeleton />
        </div>
      </div>
    );
  }

  if (message.status === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-sm">
          <div className="font-medium text-rose-200">Couldn&rsquo;t reach the backend</div>
          <div className="mt-1 text-xs text-rose-200/80">
            {message.error ?? "Something went wrong."}
          </div>
          {onRetry && message.sourceQuestion ? (
            <button
              type="button"
              onClick={() => onRetry(message.sourceQuestion as string)}
              className="mt-2 inline-flex items-center rounded-md border border-rose-300/40 px-2 py-1 text-xs font-medium text-rose-100 hover:bg-rose-400/10"
            >
              Retry
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (message.status === "refusal") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-bl-md border border-dashed border-border bg-surface/60 px-3.5 py-2.5 text-sm italic text-muted">
          <div className="flex items-start gap-2">
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="mt-0.5 h-4 w-4 shrink-0 text-muted"
            >
              <path
                fill="currentColor"
                d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 5a1.25 1.25 0 1 1-1.25 1.25A1.25 1.25 0 0 1 12 7zm1 11h-2v-7h2z"
              />
            </svg>
            <span>{message.content}</span>
          </div>
        </div>
      </div>
    );
  }

  // ok
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%] rounded-2xl rounded-bl-md border border-border bg-surface px-3.5 py-2.5">
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-text">
          {message.content}
        </div>
        {message.citations && message.citations.length > 0 ? (
          <Citations citations={message.citations} showDetails={showDetails} />
        ) : null}
        <AnswerMeta
          message={message}
          expanded={showDetails}
          onToggle={() => setShowDetails((s) => !s)}
        />
      </div>
    </div>
  );
}
