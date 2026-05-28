"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export type HealthStatus = "checking" | "booting" | "healthy" | "unreachable";

interface HealthContextValue {
  status: HealthStatus;
  elapsedMs: number;
  data: HealthResponse | null;
  retry: () => void;
}

const HealthContext = createContext<HealthContextValue | null>(null);

const GRACE_MS = 1500;
const POLL_INTERVAL_MS = 2000;
const TIMEOUT_MS = 90_000;

export function HealthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<HealthStatus>("checking");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [data, setData] = useState<HealthResponse | null>(null);
  const [generation, setGeneration] = useState(0);

  const retry = useCallback(() => {
    setStatus("checking");
    setElapsedMs(0);
    setGeneration((g) => g + 1);
  }, []);

  useEffect(() => {
    let active = true;
    const startedAt = Date.now();
    let graceTimer: ReturnType<typeof setTimeout> | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let elapsedTimer: ReturnType<typeof setInterval> | null = null;

    const cleanup = () => {
      if (graceTimer) clearTimeout(graceTimer);
      if (pollTimer) clearInterval(pollTimer);
      if (elapsedTimer) clearInterval(elapsedTimer);
      graceTimer = null;
      pollTimer = null;
      elapsedTimer = null;
    };

    const checkOnce = async () => {
      const result = await getHealth();
      if (!active) return;
      if (result && result.status === "ok") {
        setData(result);
        setStatus("healthy");
        cleanup();
        return;
      }
      if (Date.now() - startedAt >= TIMEOUT_MS) {
        setStatus("unreachable");
        cleanup();
      }
    };

    void checkOnce();

    // Grace window: only flip "checking" → "booting" once it expires, so warm
    // backends never flash the booting card.
    graceTimer = setTimeout(() => {
      if (!active) return;
      setStatus((prev) => (prev === "checking" ? "booting" : prev));
    }, GRACE_MS);

    pollTimer = setInterval(() => {
      void checkOnce();
    }, POLL_INTERVAL_MS);

    elapsedTimer = setInterval(() => {
      if (!active) return;
      setElapsedMs(Date.now() - startedAt);
    }, 250);

    return () => {
      active = false;
      cleanup();
    };
  }, [generation]);

  const value = useMemo(
    () => ({ status, elapsedMs, data, retry }),
    [status, elapsedMs, data, retry],
  );

  return (
    <HealthContext.Provider value={value}>{children}</HealthContext.Provider>
  );
}

export function useHealth(): HealthContextValue {
  const ctx = useContext(HealthContext);
  if (!ctx) throw new Error("useHealth must be used within HealthProvider");
  return ctx;
}
