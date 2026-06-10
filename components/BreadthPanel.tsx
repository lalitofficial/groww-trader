"use client";

import { ArrowDownRight, ArrowUpRight, Flame, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getMarketBreadth } from "@/lib/api";
import type { BreadthRow, BreadthSnapshot } from "@/lib/types";

type Tab = "gainers" | "losers" | "mostActive";

const TAB_META: Record<Tab, { label: string; icon: any }> = {
  gainers: { label: "Top Gainers", icon: ArrowUpRight },
  losers: { label: "Top Losers", icon: ArrowDownRight },
  mostActive: { label: "Most Active", icon: Flame },
};

export function BreadthPanel() {
  const [data, setData] = useState<BreadthSnapshot | null>(null);
  const [tab, setTab] = useState<Tab>("gainers");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getMarketBreadth();
      setData(result);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Breadth unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
  }, [load]);

  const rows: BreadthRow[] = data ? data[tab] || [] : [];
  const TabIcon = TAB_META[tab].icon;

  return (
    <section className="panel breadth-panel">
      <div className="panel-header">
        <div>
          <strong>NSE Breadth</strong>
          <div className="muted">Top movers from nseindia.com (free, cached 60s)</div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw size={13} />
            Refresh
          </button>
        </div>
      </div>
      <div className="panel-body stack">
        <div className="breadth-tabs">
          {(Object.keys(TAB_META) as Tab[]).map((key) => (
            <button key={key} type="button" className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              {TAB_META[key].label}
            </button>
          ))}
        </div>
        {error ? <div className="context-badge warning">{error}</div> : null}
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Symbol</th>
                <th>LTP</th>
                <th>Change</th>
                <th>%</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 15).map((row) => (
                <tr key={`${tab}-${row.symbol}`}>
                  <td>
                    <TabIcon size={14} className={tab === "gainers" ? "text-emerald-300" : tab === "losers" ? "text-rose-300" : ""} />
                  </td>
                  <td>
                    <Link href={`/stock/${row.symbol}?timeframe=15m`}>
                      <strong>{row.symbol}</strong>
                    </Link>
                  </td>
                  <td>{fmt(row.ltp)}</td>
                  <td className={(row.change_abs ?? 0) >= 0 ? "pnl-pos" : "pnl-neg"}>{fmt(row.change_abs)}</td>
                  <td className={(row.change_pct ?? 0) >= 0 ? "pnl-pos" : "pnl-neg"}>{pct(row.change_pct)}</td>
                  <td>{fmtInt(row.volume)}</td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    {loading ? "Loading…" : "No rows."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function fmt(value: number | null) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtInt(value: number | null) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return Math.round(value).toLocaleString("en-IN");
}

function pct(value: number | null) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}%`;
}
