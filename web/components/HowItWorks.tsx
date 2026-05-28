"use client";

interface Bullet {
  title: string;
  detail: string;
}

const BULLETS: Bullet[] = [
  {
    title: "Hybrid retrieval",
    detail:
      "BM25 (Postgres tsvector + GIN) and dense vector (pgvector HNSW, cosine) both pull top-20, fused with Reciprocal Rank Fusion (k=60). Toggle 'retrieval details' on any answer to see which ranker found each citation.",
  },
  {
    title: "1,531 chunks across 15 filings",
    detail:
      "Five tickers × three fiscal years (2022–2024), parsed from EDGAR iXBRL HTML and split into ~800-token chunks with 80-token overlap, anchored to Item-level section boundaries.",
  },
  {
    title: "768-dim Matryoshka embeddings",
    detail:
      "gemini-embedding-2 with output_dimensionality=768 (truncated from 3072). RETRIEVAL_DOCUMENT for ingest, RETRIEVAL_QUERY for searches — different projections for each side of the dot product.",
  },
  {
    title: "Grounded generation, refusal contract",
    detail:
      "gemini-2.5-flash with grammar-constrained JSON output. System prompt forbids outside knowledge and pins the exact refusal string; citation metadata is re-derived from the matched chunk so it can't drift.",
  },
  {
    title: "Citations deep-link with text fragments",
    detail:
      "Click any citation card and the SEC filing opens scrolled to (and highlighting) the exact quoted passage, via the browser's #:~:text= text-fragment syntax.",
  },
  {
    title: "Typical 2–5s round-trip",
    detail:
      "One embed call + two Postgres SELECTs + one Gemini generate call. Latency badge under each answer breaks it down. Free-tier Render adds ~30–50s cold start after 15 min idle.",
  },
];

export default function HowItWorks() {
  return (
    <details className="group mt-4 rounded-xl border border-border bg-surface/60 p-4 open:bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-2 select-none">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-4 w-4 text-muted transition-transform group-open:rotate-90"
        >
          <path fill="currentColor" d="M9 6l6 6-6 6V6z" />
        </svg>
        <span className="text-sm font-semibold tracking-tight">How it works</span>
        <span className="text-[11px] text-muted">
          BM25 + vector · RRF · 1,531 chunks · grounded answers
        </span>
      </summary>
      <ul className="mt-3 space-y-2.5 pl-1">
        {BULLETS.map((b) => (
          <li key={b.title} className="text-[12px] leading-snug">
            <span className="font-semibold text-text/95">{b.title}.</span>{" "}
            <span className="text-muted">{b.detail}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
