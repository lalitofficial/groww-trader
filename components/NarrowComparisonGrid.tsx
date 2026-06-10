"use client";

import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { rankShortlist } from "@/lib/api";
import type { FactorSnapshot, TradingSession } from "@/lib/types";

const FACTOR_ROWS = [
  { key: "technical", label: "Technical" },
  { key: "intraday_signal", label: "Intraday" },
  { key: "sentiment", label: "Sentiment" },
  { key: "volume_volatility", label: "Vol/Vol" },
  { key: "quant", label: "Quant" },
  { key: "regime_fit", label: "Regime" },
  { key: "event_proximity", label: "Event" },
  { key: "liquidity", label: "Liquidity" },
  { key: "pattern", label: "Pattern" },
];

type Props = {
  session: TradingSession | null;
  factors: Record<string, FactorSnapshot>;
  onPromote: (symbol: string, direction: "long" | "short") => void;
  promoted: Set<string>;
};

export function NarrowComparisonGrid({ session, factors, onPromote, promoted }: Props) {
  const [ranking, setRanking] = useState<Array<{ symbol: string; long_score?: number; short_score?: number; bias?: string; reason?: string }> | null>(null);
  const [loading, setLoading] = useState(false);
  const [aiFallback, setAiFallback] = useState<string | null>(null);

  const shortlistSymbols = useMemo(() => (session?.shortlist || []).map((item) => item.symbol), [session]);
  const validSymbols = shortlistSymbols.filter((symbol) => factors[symbol]);

  async function runRanker() {
    if (!validSymbols.length) return;
    setLoading(true);
    try {
      const result = await rankShortlist({ symbols: validSymbols, timeframe: "daily" });
      setRanking(result.ranking);
      setAiFallback(result.fallback ? `Deterministic fallback (${result.reason || "AI gated"})` : null);
    } catch (exc) {
      setAiFallback(exc instanceof Error ? exc.message : "Ranker failed");
    } finally {
      setLoading(false);
    }
  }

  if (validSymbols.length === 0) {
    return <div className="muted">Add at least one stock to your shortlist first.</div>;
  }

  return (
    <section className="narrow-grid-section">
      <header>
        <div>
          <strong>Narrow shortlist</strong>
          <div className="muted">Compare and promote final picks for the Live Desk.</div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-primary" onClick={runRanker} disabled={loading}>
            <Sparkles size={14} />
            {loading ? "Ranking…" : "AI rank shortlist"}
          </button>
        </div>
      </header>
      {aiFallback ? <div className="context-badge">{aiFallback}</div> : null}
      {ranking ? (
        <div className="narrow-ranking">
          {ranking.slice(0, 5).map((row, index) => (
            <div key={row.symbol} className={`narrow-rank rank-${index + 1}`}>
              <span>#{index + 1}</span>
              <strong>{row.symbol}</strong>
              <span className="muted">{row.bias}</span>
              <span className="muted">L {row.long_score ?? "-"} · S {row.short_score ?? "-"}</span>
              <p>{row.reason || "—"}</p>
            </div>
          ))}
        </div>
      ) : null}
      <div style={{ overflowX: "auto" }}>
        <table className="narrow-grid">
          <thead>
            <tr>
              <th>Factor</th>
              {validSymbols.map((symbol) => (
                <th key={symbol}>
                  <strong>{symbol}</strong>
                  <div className="muted">{factors[symbol]?.bias}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FACTOR_ROWS.map((row) => (
              <tr key={row.key}>
                <td className="muted">{row.label}</td>
                {validSymbols.map((symbol) => {
                  const sub = factors[symbol]?.subscores?.[row.key];
                  if (!sub) return <td key={symbol}>-</td>;
                  return (
                    <td key={symbol}>
                      <div className="cell-pair">
                        <span className={(sub.long || 0) >= 50 ? "pnl-pos" : ""}>{sub.long ?? 0}</span>
                        <span className="cell-sep">·</span>
                        <span className={(sub.short || 0) >= 50 ? "pnl-neg" : ""}>{sub.short ?? 0}</span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <td className="muted">Final</td>
              {validSymbols.map((symbol) => {
                const snapshot = factors[symbol];
                return (
                  <td key={symbol}>
                    <strong className="pnl-pos">L {snapshot?.long_score ?? 0}</strong>
                    <span className="cell-sep">·</span>
                    <strong className="pnl-neg">S {snapshot?.short_score ?? 0}</strong>
                  </td>
                );
              })}
            </tr>
            <tr>
              <td></td>
              {validSymbols.map((symbol) => {
                const snapshot = factors[symbol];
                const direction = snapshot?.bias === "short" ? "short" : "long";
                const isPromoted = promoted.has(symbol);
                return (
                  <td key={symbol}>
                    <button
                      type="button"
                      className={isPromoted ? "btn btn-secondary" : "btn btn-primary"}
                      onClick={() => onPromote(symbol, direction as "long" | "short")}
                      disabled={isPromoted}
                    >
                      {isPromoted ? "Promoted" : `Promote ${direction}`}
                    </button>
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
