"use client";

import { ArrowDownRight, ArrowUpRight, Minus, Plus } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { FactorRadar } from "@/components/FactorRadar";
import type { FactorSnapshot, TradingSession } from "@/lib/types";

type Props = {
  rows: FactorSnapshot[];
  session: TradingSession | null;
  onAdd: (symbol: string) => void;
  onRemove: (symbol: string) => void;
  direction: "long" | "short" | "both";
  minScore: number;
};

export function OpenDeskShortlistTable({ rows, session, onAdd, onRemove, direction, minScore }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  const shortlistSet = useMemo(
    () => new Set((session?.shortlist || []).map((item) => item.symbol)),
    [session],
  );

  const ranked = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (!row.gating.liquidity_ok) return false;
      if (!row.gating.price_ok) return false;
      if (row.gating.fno_ban) return false;
      const score = direction === "short" ? row.short_score : row.long_score;
      return score >= minScore;
    });
    filtered.sort((a, b) => {
      const left = direction === "short" ? a.short_score : a.long_score;
      const right = direction === "short" ? b.short_score : b.long_score;
      return right - left;
    });
    return filtered;
  }, [rows, direction, minScore]);

  if (rows.length === 0) {
    return <div className="muted">No factors loaded yet. Click Refresh to scan the universe.</div>;
  }

  return (
    <section className="open-desk-table">
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Symbol</th>
              <th>Bias</th>
              <th>Long</th>
              <th>Short</th>
              <th>Trend</th>
              <th>RSI</th>
              <th>Sent</th>
              <th>R:R</th>
              <th>Top factors</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((row) => (
              <tr
                key={row.symbol}
                onMouseEnter={() => setHovered(row.symbol)}
                onMouseLeave={() => setHovered((current) => (current === row.symbol ? null : current))}
              >
                <td className="radar-cell">{hovered === row.symbol ? <FactorRadar snapshot={row} size={70} /> : null}</td>
                <td>
                  <Link href={`/stock/${row.symbol}?timeframe=15m`}>
                    <strong>{row.symbol}</strong>
                  </Link>
                </td>
                <td>
                  <BiasBadge bias={row.bias} />
                </td>
                <td className={row.long_score >= 60 ? "pnl-pos" : ""}>{row.long_score}</td>
                <td className={row.short_score >= 60 ? "pnl-neg" : ""}>{row.short_score}</td>
                <td>{row.snapshot_inputs?.trend_state || "-"}</td>
                <td>{fmt(row.snapshot_inputs?.rsi)}</td>
                <td>{row.snapshot_inputs?.sentiment_label || "-"}</td>
                <td>{fmt(row.snapshot_inputs?.risk_reward)}</td>
                <td className="muted">{(row.rationale?.top_positive || []).join(", ") || "-"}</td>
                <td>
                  {shortlistSet.has(row.symbol) ? (
                    <button type="button" className="btn btn-secondary" onClick={() => onRemove(row.symbol)} title="Remove from shortlist">
                      <Minus size={12} />
                    </button>
                  ) : (
                    <button type="button" className="btn btn-primary" onClick={() => onAdd(row.symbol)} title="Add to shortlist">
                      <Plus size={12} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {ranked.length === 0 ? (
              <tr>
                <td colSpan={11} className="muted">
                  No rows pass the filters. Lower min score or change direction.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BiasBadge({ bias }: { bias: string }) {
  const Icon = bias === "long" ? ArrowUpRight : bias === "short" ? ArrowDownRight : Minus;
  return (
    <span className={`bias-badge bias-${bias}`}>
      <Icon size={12} />
      {bias}
    </span>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "-";
}
