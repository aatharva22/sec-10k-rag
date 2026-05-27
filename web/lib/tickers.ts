import type { Ticker } from "./types";

export interface TickerStyle {
  label: string;
  name: string;
  /** Tailwind classes for the pill background + text. */
  pill: string;
  /** Solid hex used in rare inline contexts. */
  hex: string;
}

export const TICKERS: Record<Ticker, TickerStyle> = {
  AAPL: {
    label: "AAPL",
    name: "Apple",
    pill: "bg-slate-200 text-slate-900",
    hex: "#e2e8f0",
  },
  MSFT: {
    label: "MSFT",
    name: "Microsoft",
    pill: "bg-sky-200 text-sky-900",
    hex: "#bae6fd",
  },
  AMZN: {
    label: "AMZN",
    name: "Amazon",
    pill: "bg-amber-200 text-amber-900",
    hex: "#fde68a",
  },
  TSLA: {
    label: "TSLA",
    name: "Tesla",
    pill: "bg-rose-200 text-rose-900",
    hex: "#fecdd3",
  },
  NVDA: {
    label: "NVDA",
    name: "NVIDIA",
    pill: "bg-emerald-200 text-emerald-900",
    hex: "#a7f3d0",
  },
};

export function tickerStyle(t: Ticker): TickerStyle {
  return TICKERS[t];
}
