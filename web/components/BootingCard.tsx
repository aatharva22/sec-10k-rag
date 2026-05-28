"use client";

import { useHealth } from "./HealthProvider";

const EXPECTED_MS = 50_000;

export default function BootingCard() {
  const { status, elapsedMs, retry } = useHealth();

  if (status === "unreachable") {
    return (
      <section className="rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-rose-500/15 text-rose-400">
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5">
              <path
                fill="currentColor"
                d="M12 2 1 21h22L12 2zm0 3.84L19.53 19H4.47L12 5.84zM11 10h2v5h-2v-5zm0 6h2v2h-2v-2z"
              />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold tracking-tight">
              Couldn&rsquo;t reach the backend
            </h2>
            <p className="mt-1 text-sm text-muted">
              The backend didn&rsquo;t respond within 90 seconds. It may still be
              waking up &mdash; try again, or check back in a minute.
            </p>
            <button
              type="button"
              onClick={retry}
              className="mt-4 inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-accent px-3 text-sm font-medium text-white transition hover:bg-accent-hover"
            >
              Try again
            </button>
          </div>
        </div>
      </section>
    );
  }

  const seconds = Math.floor(elapsedMs / 1000);
  const progress = Math.min(elapsedMs / EXPECTED_MS, 1);

  return (
    <section className="rounded-2xl border border-border bg-surface p-6 sm:p-8">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-amber-400/15 text-amber-300">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-5 w-5 animate-spin"
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
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold tracking-tight">
            Waking up the backend
          </h2>
          <p className="mt-1 text-sm text-muted">
            Hosted on a free tier that sleeps after 15 minutes idle. This
            usually takes 30&ndash;50 seconds &mdash; thanks for your patience.
          </p>
          <div className="mt-4">
            <div
              className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress * 100)}
              aria-label="Backend boot progress"
            >
              <div
                className="h-full rounded-full bg-amber-400/80 transition-[width] duration-300 ease-linear"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="mt-2 text-[11px] text-muted">{seconds}s elapsed</div>
          </div>
        </div>
      </div>
    </section>
  );
}
