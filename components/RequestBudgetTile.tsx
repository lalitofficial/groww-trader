"use client";

import { ServerCog } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getRequestBudget } from "@/lib/api";
import type { RequestBudget } from "@/lib/types";

export function RequestBudgetTile() {
  const [budget, setBudget] = useState<RequestBudget | null>(null);

  const load = useCallback(async () => {
    try {
      setBudget(await getRequestBudget());
    } catch {
      setBudget(null);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  const providers = budget?.by_provider || {};
  const grow = providers["groww"]?.total || providers["groww_fallback"]?.total || 0;
  const yahoo = providers["yahoo"]?.total || 0;
  const cache = providers["cache"]?.total || 0;
  const nse = providers["nse"]?.total || 0;
  const screener = providers["screener"]?.total || 0;
  const google = providers["google_finance"]?.total || 0;
  const azure = providers["azure_openai"]?.total || 0;
  const azureTokens = budget?.token_usage?.azure_openai?.total_tokens || 0;

  return (
    <div className="request-budget" title="API requests in the last hour">
      <ServerCog size={14} />
      <span>last hour</span>
      <strong className="rb-cache">cache {cache}</strong>
      <strong className="rb-free">NSE {nse}</strong>
      <strong className="rb-free">Yahoo {yahoo}</strong>
      <strong className="rb-free">Google {google}</strong>
      <strong className="rb-free">Screener {screener}</strong>
      <strong className={azure > 40 ? "rb-warn" : "rb-free"}>AI {azure}</strong>
      {azureTokens ? <strong className="rb-cache">{(azureTokens / 1000).toFixed(1)}k tok</strong> : null}
      <strong className={grow > 30 ? "rb-warn" : "rb-groww"}>Groww {grow}</strong>
    </div>
  );
}
