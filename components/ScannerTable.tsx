"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { ScannerRow } from "@/lib/types";

type Props = {
  rows: ScannerRow[];
  timeframe?: string;
};

export function ScannerTable({ rows, timeframe }: Props) {
  const [trend, setTrend] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [minRr, setMinRr] = useState(0);
  const [query, setQuery] = useState("");
  const [orbFilter, setOrbFilter] = useState<"all" | "broken_up" | "broken_down" | "inside">("all");

  const isIntraday = timeframe && timeframe !== "daily" && timeframe !== "hourly";

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (trend !== "all" && row.trend_state !== trend) return false;
      if ((row.technical_score || 0) < minScore) return false;
      if ((row.risk_reward || 0) < minRr) return false;
      if (orbFilter !== "all" && row.orb_state !== orbFilter) return false;
      if (query && !`${row.symbol} ${row.company}`.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [rows, trend, minScore, minRr, query, orbFilter]);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <strong>Opportunity Scanner</strong>
          <div className="muted">
            {filtered.length} of {rows.length} · {timeframe || "daily"}
          </div>
        </div>
      </div>
      <div className="panel-body">
        <div className="filters">
          <div className="field">
            <label>Search</label>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="RELIANCE, bank..." />
          </div>
          <div className="field">
            <label>Trend</label>
            <select value={trend} onChange={(event) => setTrend(event.target.value)}>
              <option value="all">All trends</option>
              <option value="strong uptrend">Strong uptrend</option>
              <option value="uptrend">Uptrend</option>
              <option value="sideways">Sideways</option>
              <option value="downtrend">Downtrend</option>
            </select>
          </div>
          <div className="field">
            <label>Min score</label>
            <input type="number" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} />
          </div>
          <div className="field">
            <label>Min R:R</label>
            <input type="number" step="0.1" value={minRr} onChange={(event) => setMinRr(Number(event.target.value))} />
          </div>
          {isIntraday ? (
            <div className="field">
              <label>Opening range</label>
              <select value={orbFilter} onChange={(event) => setOrbFilter(event.target.value as any)}>
                <option value="all">All</option>
                <option value="broken_up">Broken up</option>
                <option value="broken_down">Broken down</option>
                <option value="inside">Inside</option>
              </select>
            </div>
          ) : null}
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Score</th>
              <th>Symbol</th>
              <th>Price</th>
              <th>Trend</th>
              <th>RSI</th>
              <th>MACD</th>
              <th>Vol x</th>
              <th>R:R</th>
              {isIntraday ? <th>VWAP</th> : null}
              {isIntraday ? <th>ORB</th> : null}
              {isIntraday ? <th>Signal</th> : null}
              <th>Grade</th>
              <th>Catalysts</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.symbol}>
                <td>
                  <span className={`score ${scoreClass(row.technical_score)}`}>{row.technical_score}</span>
                </td>
                <td>
                  <Link href={`/stock/${row.symbol}${timeframe ? `?timeframe=${timeframe}` : ""}`}>
                    <strong>{row.symbol}</strong>
                    <div className="muted">{row.company}</div>
                  </Link>
                </td>
                <td>{format(row.price)}</td>
                <td>{row.trend_state}</td>
                <td>{format(row.rsi)}</td>
                <td>{row.macd_state || "-"}</td>
                <td>{format(row.volume_expansion)}</td>
                <td>{format(row.risk_reward)}</td>
                {isIntraday ? <td className={`vwap-${row.vwap_state || "neutral"}`}>{row.vwap_state || "-"}</td> : null}
                {isIntraday ? <td>{prettify(row.orb_state)}</td> : null}
                {isIntraday ? (
                  <td>
                    {row.intraday_signal ? (
                      <>
                        <strong>{row.intraday_signal}</strong>
                        <div className="muted">{row.intraday_quality ?? 0}%</div>
                      </>
                    ) : (
                      <span className="muted">-</span>
                    )}
                  </td>
                ) : null}
                <td>{row.grade || "-"}</td>
                <td>{row.catalyst_count}</td>
              </tr>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={isIntraday ? 13 : 10} className="muted">
                  No rows match filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function scoreClass(score: number) {
  if (score >= 70) return "high";
  if (score >= 45) return "mid";
  return "low";
}

function format(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : value.toLocaleString("en-IN");
}

function prettify(value?: string | null) {
  if (!value) return "-";
  return value.replace(/_/g, " ");
}
