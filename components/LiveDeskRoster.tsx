"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { LiveQuoteEvent, TradingSession } from "@/lib/types";

type Props = {
  session: TradingSession | null;
  quotes: Record<string, LiveQuoteEvent>;
  focused: string | null;
  onFocus: (symbol: string) => void;
};

export function LiveDeskRoster({ session, quotes, focused, onFocus }: Props) {
  const picks = session?.picks || [];
  if (!picks.length) {
    return <div className="muted">No picks yet. Use Open Desk to commit your picks for the day.</div>;
  }
  return (
    <div className="live-roster">
      {picks.map((pick) => {
        const quote = quotes[pick.symbol];
        const change = quote?.change_pct ?? 0;
        const Icon = change >= 0 ? ArrowUpRight : ArrowDownRight;
        const isFocused = focused === pick.symbol;
        const vwapDelta = quote && quote.vwap ? quote.ltp - quote.vwap : undefined;
        return (
          <button
            type="button"
            key={pick.symbol}
            className={`live-tile ${pick.direction} ${isFocused ? "focused" : ""}`}
            onClick={() => onFocus(pick.symbol)}
          >
            <div className="live-tile-head">
              <strong>{pick.symbol}</strong>
              <span className={`bias-badge bias-${pick.direction}`}>{pick.direction}</span>
            </div>
            <div className="live-tile-price">
              <strong>{fmt(quote?.ltp)}</strong>
              <span className={change >= 0 ? "pnl-pos" : "pnl-neg"}>
                <Icon size={11} />
                {pct(change)}
              </span>
            </div>
            <div className="live-tile-stats">
              <span className="muted">Open {fmt(quote?.open)}</span>
              <span className="muted">VWAP Δ {vwapDelta !== undefined ? fmt(vwapDelta) : "-"}</span>
            </div>
            {quote ? (
              <span className="muted live-tile-age">
                {Math.max(1, Math.round((Date.now() / 1000 - quote.ts) || 0))}s ago
              </span>
            ) : (
              <span className="muted live-tile-age">waiting…</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "-";
}

function pct(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)}%` : "-";
}
