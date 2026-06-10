"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getOptionChain } from "@/lib/api";
import type { OptionChain } from "@/lib/types";

export function OptionChainPanel({ symbol }: { symbol: string }) {
  const [chain, setChain] = useState<OptionChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getOptionChain(symbol);
      setChain(result);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Option chain unavailable");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = chain?.summary;
  const nearStrikes = chain ? chain.strikes.filter((row) => Math.abs(row.strike - (chain.underlying || 0)) <= 15 * chain.strikes.length).slice(0, 25) : [];

  return (
    <section className="panel option-chain-panel">
      <div className="panel-header">
        <div>
          <strong>Option Chain</strong>
          <div className="muted">NSE F&amp;O · {symbol}</div>
        </div>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>
      <div className="panel-body stack">
        {error ? <div className="context-badge warning">{error}</div> : null}
        {summary ? (
          <div className="option-chain-summary">
            <Tile label="Underlying" value={fmt(chain?.underlying)} />
            <Tile label="PCR" value={summary.pcr ?? "-"} tone={(summary.pcr ?? 0) > 1 ? "good" : "bad"} />
            <Tile label="Max CE OI" value={summary.max_ce_oi_strike} />
            <Tile label="Max PE OI" value={summary.max_pe_oi_strike} />
            <Tile label="Total CE OI" value={fmtInt(summary.total_ce_oi)} />
            <Tile label="Total PE OI" value={fmtInt(summary.total_pe_oi)} />
          </div>
        ) : (
          <div className="muted">{loading ? "Loading from NSE…" : "No option chain loaded."}</div>
        )}
        {nearStrikes.length ? (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>CE OI</th>
                  <th>CE IV</th>
                  <th>CE LTP</th>
                  <th>Strike</th>
                  <th>PE LTP</th>
                  <th>PE IV</th>
                  <th>PE OI</th>
                </tr>
              </thead>
              <tbody>
                {nearStrikes.map((row) => (
                  <tr key={row.strike} className={row.strike === chain?.underlying ? "highlighted" : ""}>
                    <td>{fmtInt(row.ce_oi)}</td>
                    <td>{fmt(row.ce_iv)}</td>
                    <td>{fmt(row.ce_ltp)}</td>
                    <td>
                      <strong>{row.strike}</strong>
                    </td>
                    <td>{fmt(row.pe_ltp)}</td>
                    <td>{fmt(row.pe_iv)}</td>
                    <td>{fmtInt(row.pe_oi)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Tile({ label, value, tone }: { label: string; value: unknown; tone?: "good" | "bad" }) {
  return (
    <div className={`option-tile ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(value ?? "-");
}

function fmtInt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? Math.round(value).toLocaleString("en-IN") : String(value ?? "-");
}
