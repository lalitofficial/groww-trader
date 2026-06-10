"use client";

import { useCallback, useEffect, useState } from "react";
import { closePaperTrade, getPaperSummary, getPaperTrades } from "@/lib/api";
import type { PaperSummary, PaperTrade } from "@/lib/types";

export function PaperTradeLedger({ symbolFilter }: { symbolFilter?: string }) {
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyTrade, setBusyTrade] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [paper, paperSummary] = await Promise.all([
        getPaperTrades({ symbol: symbolFilter, limit: 50 }),
        getPaperSummary(),
      ]);
      setTrades(paper.items);
      setSummary(paperSummary);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Paper trades unavailable");
    } finally {
      setLoading(false);
    }
  }, [symbolFilter]);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  async function close(trade: PaperTrade) {
    const price = window.prompt(`Close ${trade.symbol} at price?`, String(trade.live_price ?? trade.entry_price));
    if (!price) return;
    const value = Number(price);
    if (!Number.isFinite(value)) return;
    setBusyTrade(trade.id);
    try {
      await closePaperTrade(trade.id, { exit_price: value });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Close failed");
    } finally {
      setBusyTrade(null);
    }
  }

  return (
    <section className="panel paper-ledger">
      <div className="panel-header">
        <div>
          <strong>Paper trade ledger</strong>
          <div className="muted">{symbolFilter ? `Filtered: ${symbolFilter}` : "All open + recent closed"}</div>
        </div>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          {loading ? "…" : "Refresh"}
        </button>
      </div>
      <div className="panel-body stack">
        {error ? <div className="context-badge warning">{error}</div> : null}
        {summary ? (
          <div className="paper-summary">
            <SummaryBox label="Closed" value={summary.total_trades} />
            <SummaryBox label="Open" value={summary.open_trades} />
            <SummaryBox label="Win %" value={`${summary.win_rate_pct}%`} />
            <SummaryBox label="Total P&L" value={fmt(summary.total_pnl)} tone={summary.total_pnl >= 0 ? "good" : "bad"} />
            <SummaryBox label="Profit factor" value={summary.profit_factor !== null ? summary.profit_factor : "-"} />
            <SummaryBox label="Expectancy" value={fmt(summary.expectancy)} />
            <SummaryBox label="Fees" value={fmt(summary.total_fees)} />
          </div>
        ) : null}
        <div style={{ overflowX: "auto" }}>
          <table className="paper-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>TF</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Stop</th>
                <th>Target</th>
                <th>LTP / Exit</th>
                <th>P&L</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const display = trade.status === "open" ? trade.live_price ?? trade.entry_price : trade.exit_price ?? trade.entry_price;
                const pnl = trade.status === "open" ? trade.mtm_pnl ?? null : trade.pnl ?? null;
                return (
                  <tr key={trade.id}>
                    <td>{trade.symbol}</td>
                    <td className={trade.side === "BUY" ? "side-buy" : "side-sell"}>{trade.side}</td>
                    <td>{trade.timeframe || "-"}</td>
                    <td>{trade.quantity}</td>
                    <td>{fmt(trade.entry_price)}</td>
                    <td>{fmt(trade.stop_loss)}</td>
                    <td>{fmt(trade.target)}</td>
                    <td>{fmt(display)}</td>
                    <td className={pnl === null ? "" : pnl >= 0 ? "pnl-pos" : "pnl-neg"}>
                      {pnl === null ? "-" : fmt(pnl)}
                    </td>
                    <td>{trade.status}</td>
                    <td>
                      {trade.status === "open" ? (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busyTrade === trade.id}
                          onClick={() => close(trade)}
                        >
                          Close
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={11} className="muted">
                    No paper trades yet. Use the Intraday panel or scanner to open one.
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

function SummaryBox({ label, value, tone }: { label: string; value: unknown; tone?: "good" | "bad" }) {
  return (
    <div className={`paper-summary-box ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function fmt(value?: number | null) {
  if (value === undefined || value === null || !Number.isFinite(value)) return "-";
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
