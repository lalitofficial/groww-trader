"use client";

import { Activity } from "lucide-react";
import { useEffect, useState } from "react";

type Usage = {
  total_requests: number;
  error_requests: number;
  recent_5m: number;
  uptime_seconds: number;
  last_status: number | null;
  last_path: string | null;
  avg_duration_ms_5m: number;
  error?: string;
};

export function ApiUsage() {
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch("/api/usage", { cache: "no-store" });
        const data = await response.json();
        if (active) setUsage(data);
      } catch {
        if (active) setUsage(null);
      }
    }
    load();
    const id = window.setInterval(load, 15_000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, []);

  const healthy = !usage?.error && (!usage?.last_status || usage.last_status < 400);
  const title = usage
    ? `Total ${usage.total_requests} · Errors ${usage.error_requests} · Avg ${usage.avg_duration_ms_5m}ms · Last ${usage.last_path || "-"}`
    : "API usage loading";

  return (
    <div className="api-usage" title={title}>
      <span className={healthy ? "inline-flex items-center gap-1 text-emerald-300" : "inline-flex items-center gap-1 text-amber-300"}>
        <Activity size={13} />
        {usage ? `${usage.recent_5m}/5m` : "API"}
      </span>
      {usage ? <span className="text-slate-500">{usage.avg_duration_ms_5m}ms</span> : null}
    </div>
  );
}
