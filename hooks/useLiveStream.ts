"use client";

import { useEffect, useRef, useState } from "react";
import { liveStreamUrl } from "@/lib/api";
import type { LiveDepthEvent, LiveQuoteEvent, LiveSignalEvent } from "@/lib/types";

type StreamState = {
  quotes: Record<string, LiveQuoteEvent>;
  depth: Record<string, LiveDepthEvent>;
  signals: LiveSignalEvent[];
  connected: boolean;
  degraded: string | null;
};

const INITIAL: StreamState = {
  quotes: {},
  depth: {},
  signals: [],
  connected: false,
  degraded: null,
};

/**
 * Subscribes to /api/live/stream and exposes the multiplexed stream as
 * grouped pieces of state. Reconnects with backoff on disconnect.
 */
export function useLiveStream(enabled: boolean = true) {
  const [state, setState] = useState<StreamState>(INITIAL);
  const sourceRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(1000);

  useEffect(() => {
    if (!enabled) return undefined;

    function connect() {
      const source = new EventSource(liveStreamUrl());
      sourceRef.current = source;

      source.addEventListener("connected", () => {
        backoffRef.current = 1000;
        setState((current) => ({ ...current, connected: true, degraded: null }));
      });

      source.addEventListener("quote", (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as LiveQuoteEvent;
          setState((current) => ({ ...current, quotes: { ...current.quotes, [data.symbol]: data } }));
        } catch {
          /* ignore parse errors */
        }
      });

      source.addEventListener("depth", (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as LiveDepthEvent;
          setState((current) => ({ ...current, depth: { ...current.depth, [data.symbol]: data } }));
        } catch {
          /* ignore */
        }
      });

      source.addEventListener("signal", (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as LiveSignalEvent;
          setState((current) => ({ ...current, signals: [data, ...current.signals].slice(0, 100) }));
        } catch {
          /* ignore */
        }
      });

      source.addEventListener("market", (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data) as { kind: string; message?: string };
          if (data.kind && data.kind.includes("rate_limit")) {
            setState((current) => ({ ...current, degraded: data.message || data.kind }));
          }
        } catch {
          /* ignore */
        }
      });

      source.onerror = () => {
        source.close();
        sourceRef.current = null;
        setState((current) => ({ ...current, connected: false }));
        const wait = Math.min(backoffRef.current, 30_000);
        backoffRef.current = Math.min(backoffRef.current * 2, 30_000);
        window.setTimeout(connect, wait);
      };
    }

    connect();
    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [enabled]);

  return state;
}
