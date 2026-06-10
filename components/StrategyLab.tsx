"use client";

import { Beaker, ExternalLink, FlaskConical, Github, Play, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  benchStrategies,
  deleteStrategy,
  importStrategy,
  listStrategies,
  runStrategy,
} from "@/lib/api";
import type { StrategyMetricsRow, StrategySpecSummary, Timeframe } from "@/lib/types";

const TF_OPTIONS: Timeframe[] = ["5m", "15m", "30m", "hourly", "daily"];

export function StrategyLab({ defaultSymbol = "RELIANCE", defaultTimeframe = "daily" as Timeframe }: { defaultSymbol?: string; defaultTimeframe?: Timeframe }) {
  const [strategies, setStrategies] = useState<StrategySpecSummary[]>([]);
  const [symbol, setSymbol] = useState(defaultSymbol);
  const [timeframe, setTimeframe] = useState<Timeframe>(defaultTimeframe);
  const [bench, setBench] = useState<StrategyMetricsRow[] | null>(null);
  const [runResult, setRunResult] = useState<any | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [importUrl, setImportUrl] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await listStrategies();
      setStrategies(data.items);
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Library load failed");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const builtin = useMemo(() => strategies.filter((item) => item.kind !== "user"), [strategies]);
  const user = useMemo(() => strategies.filter((item) => item.kind === "user"), [strategies]);

  async function runOne(id: string) {
    setLoading(true);
    setStatus("");
    setActiveId(id);
    setRunResult(null);
    try {
      const result = await runStrategy(id, { symbol: symbol.toUpperCase(), timeframe });
      setRunResult(result);
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Run failed");
    } finally {
      setLoading(false);
    }
  }

  async function runBench() {
    setLoading(true);
    setStatus("");
    setBench(null);
    try {
      const result = await benchStrategies({ symbol: symbol.toUpperCase(), timeframe });
      setBench(result.results);
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Bench failed");
    } finally {
      setLoading(false);
    }
  }

  async function importFromGithub() {
    if (!importUrl.trim()) return;
    setLoading(true);
    setStatus("");
    try {
      await importStrategy({ url: importUrl.trim() });
      setImportUrl("");
      setStatus("Imported.");
      await load();
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Import failed");
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: string) {
    if (!confirm(`Delete strategy ${id}?`)) return;
    await deleteStrategy(id);
    await load();
  }

  return (
    <section className="panel strategy-lab">
      <div className="panel-header">
        <div>
          <strong>Strategy Lab</strong>
          <div className="muted">
            {builtin.length} built-in · {user.length} imported · GitHub spec import enabled
          </div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw size={13} />
            Refresh
          </button>
          <button type="button" className="btn btn-primary" onClick={runBench} disabled={loading}>
            <FlaskConical size={14} />
            Bench all on {symbol}
          </button>
        </div>
      </div>
      <div className="panel-body stack">
        <div className="strategy-controls">
          <div className="field">
            <label>Symbol</label>
            <input className="input" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="RELIANCE" />
          </div>
          <div className="field">
            <label>Timeframe</label>
            <select className="input" value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}>
              {TF_OPTIONS.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </div>
          <div className="field strategy-import-field">
            <label>Import strategy spec (GitHub raw or blob URL)</label>
            <div className="strategy-import-row">
              <input
                className="input"
                placeholder="https://github.com/user/repo/blob/main/strategies/golden-cross.yaml"
                value={importUrl}
                onChange={(event) => setImportUrl(event.target.value)}
              />
              <button type="button" className="btn btn-primary" onClick={importFromGithub} disabled={loading}>
                <Github size={13} />
                Import
              </button>
            </div>
          </div>
        </div>
        {status ? <div className="context-badge">{status}</div> : null}

        <div className="strategy-grid">
          {strategies.map((spec) => (
            <article key={spec.id} className={`strategy-card ${activeId === spec.id ? "active" : ""}`}>
              <header>
                <div>
                  <strong>{spec.name}</strong>
                  <span className="muted">{spec.kind === "user" ? "Imported" : "Builtin"} · {(spec.timeframes || ["daily"]).join(", ")}</span>
                </div>
                <div className="strategy-card-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => runOne(spec.id)} disabled={loading}>
                    <Play size={13} />
                    Run
                  </button>
                  {spec.kind === "user" ? (
                    <button type="button" className="btn btn-secondary" onClick={() => remove(spec.id)} title="Delete">
                      <Trash2 size={13} />
                    </button>
                  ) : null}
                </div>
              </header>
              {spec.description ? <p>{spec.description}</p> : null}
              <footer>
                <span>{spec.author || "community"}</span>
                {spec.source_url ? (
                  <a href={spec.source_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={11} />
                    source
                  </a>
                ) : null}
                <div className="strategy-tags">
                  {(spec.tags || []).map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
              </footer>
            </article>
          ))}
        </div>

        {runResult ? <RunResultView result={runResult} /> : null}
        {bench ? <BenchTable rows={bench} /> : null}
      </div>
    </section>
  );
}

function RunResultView({ result }: { result: any }) {
  const metrics = result.metrics || {};
  return (
    <section className="strategy-run">
      <div className="strategy-run-head">
        <Beaker size={14} />
        <strong>{result.strategy_name}</strong>
        <span className="muted">{result.timeframe}</span>
      </div>
      <div className="strategy-run-metrics">
        <Metric label="Trades" value={metrics.sample_size} />
        <Metric label="Win %" value={pct(metrics.win_rate)} />
        <Metric label="Total %" value={pct(metrics.total_return_pct)} tone={metrics.total_return_pct >= 0 ? "good" : "bad"} />
        <Metric label="Profit factor" value={metrics.profit_factor ?? "-"} />
        <Metric label="Max DD %" value={pct(metrics.max_drawdown_pct)} tone="bad" />
        <Metric label="Sharpe" value={metrics.sharpe ?? "-"} />
        <Metric label="Expectancy" value={fmt(metrics.expectancy)} />
        <Metric label="Fees" value={fmt(metrics.total_fees)} />
      </div>
      {result.warnings?.length ? <p className="muted">{result.warnings.join(" ")}</p> : null}
    </section>
  );
}

function BenchTable({ rows }: { rows: StrategyMetricsRow[] }) {
  return (
    <section className="strategy-bench">
      <strong>Leaderboard</strong>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Strategy</th>
              <th>Sharpe</th>
              <th>PF</th>
              <th>Return %</th>
              <th>Win %</th>
              <th>DD %</th>
              <th>Trades</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.strategy_id}>
                <td>{index + 1}</td>
                <td>
                  <strong>{row.name}</strong>
                  <div className="muted">{row.author}</div>
                </td>
                <td>{row.sharpe ?? "-"}</td>
                <td>{row.profit_factor ?? "-"}</td>
                <td className={(row.total_return_pct ?? 0) >= 0 ? "pnl-pos" : "pnl-neg"}>{pct(row.total_return_pct)}</td>
                <td>{pct(row.win_rate)}</td>
                <td>{pct(row.max_drawdown_pct)}</td>
                <td>{row.sample_size}</td>
                <td>
                  {row.source_url ? (
                    <a href={row.source_url} target="_blank" rel="noreferrer">
                      link
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="muted">
                  No strategies ran successfully.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: "good" | "bad" }) {
  return (
    <div className={`strategy-metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
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
