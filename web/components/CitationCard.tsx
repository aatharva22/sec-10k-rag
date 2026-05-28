"use client";

import type { Citation } from "@/lib/types";
import { tickerStyle } from "@/lib/tickers";
import { buildSourceLink } from "@/lib/source-link";

interface Props {
  citation: Citation;
  showDetails?: boolean;
}

function RetrievalDetails({ citation }: { citation: Citation }) {
  const parts: string[] = [];
  if (citation.bm25_rank !== null) parts.push(`BM25 #${citation.bm25_rank}`);
  if (citation.vector_rank !== null) parts.push(`Vec #${citation.vector_rank}`);
  if (citation.rrf_score !== null && citation.rrf_score !== undefined) {
    parts.push(`RRF ${citation.rrf_score.toFixed(4)}`);
  }
  if (parts.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1 text-[10px]">
      {parts.map((p) => (
        <span
          key={p}
          className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-muted"
        >
          {p}
        </span>
      ))}
    </div>
  );
}

export default function CitationCard({ citation, showDetails }: Props) {
  const style = tickerStyle(citation.ticker);
  const hasLink = typeof citation.source_url === "string" && citation.source_url.length > 0;

  const inner = (
    <>
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide ${style.pill}`}
        >
          {style.label}
        </span>
        <span className="text-[11px] font-medium text-muted">
          FY{citation.fiscal_year}
        </span>
        {hasLink ? (
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="ml-auto h-3.5 w-3.5 text-muted"
          >
            <path
              fill="currentColor"
              d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3zm-2 4H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7h-2v7H5V9h7V7z"
            />
          </svg>
        ) : null}
      </div>
      <div className="mt-1 line-clamp-2 text-[11px] font-medium text-text/90">
        {citation.section}
      </div>
      <p className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-muted">
        &ldquo;{citation.quote}&rdquo;
      </p>
      {showDetails ? <RetrievalDetails citation={citation} /> : null}
    </>
  );

  const baseClasses =
    "group flex w-64 shrink-0 flex-col rounded-lg border border-border bg-surface p-3 transition";

  if (!hasLink) {
    return (
      <div
        className={`${baseClasses} cursor-default opacity-70`}
        title={citation.quote}
      >
        {inner}
        <span className="mt-2 text-[10px] italic text-muted/70">
          No source URL
        </span>
      </div>
    );
  }

  return (
    <a
      href={buildSourceLink(citation.source_url as string, citation.quote)}
      target="_blank"
      rel="noopener noreferrer"
      title={citation.quote}
      className={`${baseClasses} hover:-translate-y-0.5 hover:border-accent/60 hover:bg-surface-2`}
    >
      {inner}
    </a>
  );
}
