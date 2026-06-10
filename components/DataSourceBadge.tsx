import type { StockAnalysis } from "@/lib/types";

export function DataSourceBadge({ analysis }: { analysis: StockAnalysis }) {
  const daily = analysis.data_source?.daily || {};
  const provider = daily.provider || "unknown";
  const freshness = daily.freshness || analysis.data_freshness?.daily || "unknown";
  const stale = analysis.stale_cache_used || daily.stale_cache_used;
  const label = `${labelize(provider)} ${stale ? "stale" : freshness}`;

  return (
    <div className={stale ? "source-badge stale" : "source-badge"}>
      <span>{label}</span>
      {daily.normalized_symbol ? <strong>{daily.normalized_symbol}</strong> : null}
    </div>
  );
}

function labelize(value: string) {
  if (value === "alpha_vantage") return "Alpha";
  if (value === "groww_fallback") return "Groww fallback";
  if (value === "stale_cache") return "Stale cache";
  return value.charAt(0).toUpperCase() + value.slice(1);
}
