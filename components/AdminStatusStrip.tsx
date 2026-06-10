"use client";

import { useAdminStream } from "@/hooks/useAdminStream";

export function AdminStatusStrip() {
  const { connected, metrics, events } = useAdminStream();
  const budget = metrics?.budget || {};
  const aiTokens = budget.token_usage?.azure_openai?.total_tokens || 0;
  return (
    <div className="admin-status-strip">
      <span className={connected ? "ok" : "warn"}>{connected ? "live" : "offline"}</span>
      <span>{budget.total ?? 0} calls / 1h</span>
      <span>{(aiTokens / 1000).toFixed(1)}k AI tokens</span>
      <span>{events.length} new session events</span>
    </div>
  );
}
