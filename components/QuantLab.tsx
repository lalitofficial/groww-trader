"use client";

import { FlaskConical, Play } from "lucide-react";
import { useState } from "react";
import type { BacktestResult, StockAnalysis } from "@/lib/types";

const STRATEGIES = [
  { id: "ma_trend_pullback", label: "MA trend pullback" },
  { id: "supertrend_follow", label: "Supertrend follow" },
  { id: "rsi_mean_reversion", label: "RSI mean reversion" },
  { id: "breakout_retest", label: "Breakout / retest" },
];

export function QuantLab({ analysis }: { analysis: StockAnalysis }) {
  const [strategy, setStrategy] = useState("ma_trend_pullback");
  const [timeframe, setTimeframe] = useState<"daily" | "hourly">("daily");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  async function run() {
    setLoading(true);
    try {
      const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${backend}/api/stocks/${encodeURIComponent(analysis.symbol)}/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_id: strategy, timeframe }),
      });
      setResult(await response.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel h-full overflow-auto">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <FlaskConical size={14} />
          <strong>Quant Lab</strong>
        </div>
        <button type="button" className="btn btn-primary" onClick={run} disabled={loading}>
          <Play size={13} />
          {loading ? "Running" : "Run"}
        </button>
      </div>
      <div className="panel-body grid gap-3">
        <div className="grid grid-cols-2 gap-2">
          <label className="field">
            <span>Strategy</span>
            <select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
              {STRATEGIES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Timeframe</span>
            <select value={timeframe} onChange={(event) => setTimeframe(event.target.value as "daily" | "hourly")}>
              <option value="daily">Daily</option>
              <option value="hourly">Hourly</option>
            </select>
          </label>
        </div>

        {result ? (
          <>
            <div className="metrics">
              <Metric label="Engine" value={result.engine} />
              <Metric label="Trades" value={result.metrics.sample_size} />
              <Metric label="Win rate" value={`${result.metrics.win_rate ?? 0}%`} />
              <Metric label="Return" value={`${result.metrics.total_return_pct ?? 0}%`} />
              <Metric label="Max DD" value={`${result.metrics.max_drawdown_pct ?? 0}%`} />
              <Metric label="PF" value={result.metrics.profit_factor ?? "-"} />
              <Metric label="Expectancy" value={result.metrics.expectancy ?? "-"} />
            </div>
            {result.warnings?.length ? <div className="context-badge">{result.warnings.join(" ")}</div> : null}
            <div className="overflow-auto">
              <table>
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>P&L</th>
                    <th>Return</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.slice(-12).map((trade, index) => (
                    <tr key={`${trade.entry_time}-${index}`}>
                      <td>{trade.entry}</td>
                      <td>{trade.exit}</td>
                      <td>{trade.pnl}</td>
                      <td>{trade.return_pct}%</td>
                      <td>{trade.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="ai-report">Run a read-only backtest to check whether this setup has historical edge on the selected timeframe.</div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}
