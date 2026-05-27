"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "healthy"; data: HealthResponse }
  | { kind: "unreachable" };

export default function HealthBadge() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    void getHealth().then((data) => {
      if (!active) return;
      if (data && data.status === "ok") {
        setState({ kind: "healthy", data });
      } else {
        setState({ kind: "unreachable" });
      }
    });
    return () => {
      active = false;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full bg-muted/60"
        />
        <span>checking…</span>
      </div>
    );
  }

  if (state.kind === "healthy") {
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
          healthy &middot; {state.data.chunks.toLocaleString()} chunks
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
