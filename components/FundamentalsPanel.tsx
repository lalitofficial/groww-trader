"use client";

import { ExternalLink, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getFundamentals } from "@/lib/api";
import type { FundamentalsSnapshot } from "@/lib/types";

export function FundamentalsPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<FundamentalsSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getFundamentals(symbol);
      setData(result);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Fundamentals unavailable");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    void load();
  }, [load]);

  const snap = data?.snapshot;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <strong>Fundamentals (Screener)</strong>
          <div className="muted">{symbol}</div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw size={13} />
            Refresh
          </button>
          {data?.url ? (
            <a className="btn btn-secondary" href={data.url} target="_blank" rel="noreferrer">
              <ExternalLink size={13} />
              Open
            </a>
          ) : null}
        </div>
      </div>
      <div className="panel-body stack">
        {error ? <div className="context-badge warning">{error}</div> : null}
        {snap ? (
          <div className="fundamentals-grid">
            <Tile label="Market cap" value={snap.market_cap || "-"} />
            <Tile label="P/E" value={fmt(snap.pe_ratio)} />
            <Tile label="Industry P/E" value={fmt(snap.industry_pe)} />
            <Tile label="ROCE %" value={pct(snap.roce)} />
            <Tile label="ROE %" value={pct(snap.roe)} />
            <Tile label="Book value" value={fmt(snap.book_value)} />
            <Tile label="D/E" value={fmt(snap.debt_to_equity)} />
            <Tile label="Promoter %" value={pct(snap.promoter_holding)} />
            <Tile label="Div yield %" value={pct(snap.dividend_yield)} />
            <Tile label="High / Low" value={snap.high_low || "-"} />
          </div>
        ) : (
          <div className="muted">{loading ? "Fetching from Screener.in…" : "No fundamentals loaded yet."}</div>
        )}
        {data?.ratios && Object.keys(data.ratios).length ? (
          <details className="fundamentals-raw">
            <summary>All ratios ({Object.keys(data.ratios).length})</summary>
            <div className="fundamentals-raw-grid">
              {Object.entries(data.ratios).map(([label, value]) => (
                <div key={label} className="kv">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </section>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="fundamentals-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(value ?? "-");
}

function pct(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}%`;
}
