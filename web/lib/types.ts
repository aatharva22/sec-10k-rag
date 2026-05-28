export type Ticker = "AAPL" | "MSFT" | "AMZN" | "TSLA" | "NVDA";
export type FiscalYear = 2022 | 2023 | 2024;

export interface Citation {
  chunk_id: number;
  ticker: Ticker;
  fiscal_year: FiscalYear;
  section: string;
  quote: string;
  source_url: string | null;
  bm25_rank: number | null;
  vector_rank: number | null;
  rrf_score: number | null;
}

export interface Timing {
  embed_ms: number;
  retrieve_ms: number;
  generate_ms: number;
  total_ms: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  timing: Timing | null;
  retrieved_count: number;
}

export interface HealthResponse {
  status: string;
  db: string;
  chunks: number;
}

export type MessageRole = "user" | "assistant";
export type MessageStatus = "pending" | "ok" | "error" | "refusal";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  citations?: Citation[];
  status: MessageStatus;
  error?: string;
  timing?: Timing | null;
  retrievedCount?: number;
  /** Original question for assistant messages, used by Retry. */
  sourceQuestion?: string;
  /** Filters in effect at submit time — preserved so Retry uses the same scope. */
  sourceTicker?: Ticker | null;
  sourceFiscalYear?: FiscalYear | null;
}

export const REFUSAL_TEXT =
  "I don't have enough information in the provided 10-K excerpts to answer that.";

export const ALL_TICKERS: Ticker[] = ["AAPL", "MSFT", "AMZN", "TSLA", "NVDA"];
export const ALL_FISCAL_YEARS: FiscalYear[] = [2022, 2023, 2024];
