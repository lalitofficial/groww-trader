"use client";

import { useEffect, useState } from "react";
import { adminStreamUrl } from "@/lib/admin";

export function useAdminStream() {
  const [metrics, setMetrics] = useState<Record<string, any> | null>(null);
  const [events, setEvents] = useState<Array<Record<string, any>>>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(adminStreamUrl());
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("metrics", (event) => {
      setMetrics(JSON.parse((event as MessageEvent).data));
    });
    source.addEventListener("event", (event) => {
      setEvents((items) => [JSON.parse((event as MessageEvent).data), ...items].slice(0, 20));
    });
    return () => source.close();
  }, []);

  return { connected, metrics, events };
}
