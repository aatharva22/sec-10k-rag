"use client";

import { ALL_FISCAL_YEARS, ALL_TICKERS, type FiscalYear, type Ticker } from "@/lib/types";
import { tickerStyle } from "@/lib/tickers";

interface Props {
  ticker: Ticker | null;
  fiscalYear: FiscalYear | null;
  onTickerChange: (t: Ticker | null) => void;
  onYearChange: (y: FiscalYear | null) => void;
  disabled?: boolean;
}

export default function FilterChips({
  ticker,
  fiscalYear,
  onTickerChange,
  onYearChange,
  disabled,
}: Props) {
  const hasFilter = ticker !== null || fiscalYear !== null;
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[11px]">
      <span className="font-semibold uppercase tracking-wider text-muted">
        Filter:
      </span>
      {ALL_TICKERS.map((t) => {
        const active = ticker === t;
        const style = tickerStyle(t);
        return (
          <button
            key={t}
            type="button"
            disabled={disabled}
            onClick={() => onTickerChange(active ? null : t)}
            aria-pressed={active}
            className={[
              "rounded-full border px-2.5 py-1 font-medium transition",
              active
                ? `${style.pill} border-transparent shadow-sm`
                : "border-border bg-surface text-text/80 hover:border-accent/50 hover:text-text",
              "disabled:cursor-not-allowed disabled:opacity-50",
            ].join(" ")}
          >
            {style.label}
          </button>
        );
      })}
      <span className="ml-2 text-muted/70">·</span>
      {ALL_FISCAL_YEARS.map((y) => {
        const active = fiscalYear === y;
        return (
          <button
            key={y}
            type="button"
            disabled={disabled}
            onClick={() => onYearChange(active ? null : y)}
            aria-pressed={active}
            className={[
              "rounded-full border px-2.5 py-1 font-medium transition",
              active
                ? "border-transparent bg-accent text-white shadow-sm"
                : "border-border bg-surface text-text/80 hover:border-accent/50 hover:text-text",
              "disabled:cursor-not-allowed disabled:opacity-50",
            ].join(" ")}
          >
            FY{String(y).slice(-2)}
          </button>
        );
      })}
      {hasFilter && (
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            onTickerChange(null);
            onYearChange(null);
          }}
          className="ml-1 rounded-full px-2 py-1 text-muted hover:text-text disabled:opacity-50"
          aria-label="Clear all filters"
        >
          ✕ clear
        </button>
      )}
    </div>
  );
}
