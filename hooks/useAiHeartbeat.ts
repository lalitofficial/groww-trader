"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAiStatus, sendAiHeartbeat } from "@/lib/api";
import type { AiStatus } from "@/lib/types";

const HEARTBEAT_INTERVAL_MS = 60_000;

/**
 * Pings the backend's AI heartbeat endpoint while the document is visible.
 *
 * The backend gates every AI call on a recent heartbeat (10 min grace by
 * default). If the user closes the tab or the server goes down, AI auto-mutes
 * — so we never accidentally rack up cost while no one is watching.
 */
export function useAiHeartbeat(enabled: boolean = true) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await getAiStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  const ping = useCallback(async () => {
    try {
      setStatus(await sendAiHeartbeat());
    } catch {
      // swallow — backend down is exactly the case the gate is meant to handle
    }
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;

    // Initial heartbeat on mount.
    void ping();

    function start() {
      if (intervalRef.current) return;
      intervalRef.current = setInterval(() => {
        if (document.visibilityState === "visible") {
          void ping();
        }
      }, HEARTBEAT_INTERVAL_MS);
    }
    function stop() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    function onVisibility() {
      if (document.visibilityState === "visible") {
        void ping();
        start();
      } else {
        stop();
      }
    }

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled, ping]);

  return { status, refresh, ping };
}
