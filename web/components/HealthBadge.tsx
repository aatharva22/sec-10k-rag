"use client";

import { useHealth } from "./HealthProvider";

export default function HealthBadge() {
  const { status, data } = useHealth();

  if (status === "checking") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full bg-muted/60"
        />
        <span>checking&hellip;</span>
      </div>
    );
  }

  if (status === "booting") {
    return (
      <div
        className="flex items-center gap-2 text-xs text-muted"
        title="Backend is waking up"
      >
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.6)]"
        />
        <span>waking up&hellip;</span>
      </div>
    );
  }

  if (status === "healthy") {
    return (
      <div
        className="flex items-center gap-2 text-xs text-muted"
        title="Backend reachable"
      >
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]"
        />
        <span>
          healthy{data ? ` · ${data.chunks.toLocaleString()} chunks` : ""}
        </span>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-2 text-xs text-muted"
      title="Backend unreachable"
    >
      <span
        aria-hidden="true"
        className="inline-block h-2 w-2 rounded-full bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.6)]"
      />
      <span>unreachable</span>
    </div>
  );
}
