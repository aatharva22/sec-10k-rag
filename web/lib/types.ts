export type Ticker = "AAPL" | "MSFT" | "AMZN" | "TSLA" | "NVDA";
export type FiscalYear = 2022 | 2023 | 2024;

export interface Citation {
  chunk_id: number;
  ticker: Ticker;
  fiscal_year: FiscalYear;
  section: string;
  quote: string;
  source_url: string | null;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
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
  /** Original question for assistant messages, used by Retry. */
  sourceQuestion?: string;
}

export const REFUSAL_TEXT =
  "I don't have enough information in the provided 10-K excerpts to answer that.";
