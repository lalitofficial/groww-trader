"use client";

import { ArrowDownRight, ArrowUpRight, Crosshair, Zap } from "lucide-react";
import { useState } from "react";
import { autoOpenPaperTrade, openPaperTrade } from "@/lib/api";
import type { IntradayStrategy, IntradayView, StockAnalysis } from "@/lib/types";

export function IntradayPanel({ analysis }: { analysis: StockAnalysis }) {
  const [status, setStatus] = useState("");
  const [pending, setPending] = useState(false);
  const view: IntradayView | null = analysis.intraday_view || null;

  if (!view || view.status === "empty") {
    return (
      <section className="panel">
        <div className="panel-header">
          <strong>Intraday view</strong>
          <span className="muted">No intraday candles yet</span>
        </div>
        <div className="panel-body muted">
          Switch the workstation to a 5m / 15m / 30m timeframe to populate VWAP, opening range, and intraday signals.
        </div>
      </section>
    );
  }

  const activeView: IntradayView = view;
  const orb = activeView.opening_range;
  const signal = activeView.primary_signal;
  const strategies = activeView.strategies || [];
  const tfMinutes = activeView.timeframe_minutes || activeView.interval_minutes;

  async function paperFromSignal() {
    if (!signal || !signal.entry) return;
    setPending(true);
    setStatus("");
    try {
      const result = await autoOpenPaperTrade({ symbol: analysis.symbol, timeframe: tfMinutes ? (`${tfMinutes}m` as any) : "15m" });
      setStatus(result.opened ? `Opened paper #${result.opened.id} on ${signal.name}.` : result.reason || "No-op");
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Paper open failed");
    } finally {
      setPending(false);
    }
  }

  async function manualPaper(direction: "long" | "short") {
    if (!activeView.last_price) return;
    setPending(true);
    setStatus("");
    try {
      const stop = direction === "long" ? Math.min(activeView.opening_range?.or_low || 0, activeView.last_price! * 0.99) : Math.max(activeView.opening_range?.or_high || 0, activeView.last_price! * 1.01);
      const result = await openPaperTrade({
        symbol: analysis.symbol,
        side: direction === "long" ? "BUY" : "SELL",
        product: "intraday",
        quantity: 1,
        entry_price: activeView.last_price!,
        stop_loss: stop || undefined,
        target: direction === "long" ? activeView.last_price! * 1.015 : activeView.last_price! * 0.985,
        timeframe: tfMinutes ? `${tfMinutes}m` : "15m",
        strategy_id: "manual_intraday",
        notes: `Manual intraday ${direction} at ${activeView.last_price}`,
      });
      setStatus(`Opened paper #${result.id} (${direction}).`);
    } catch (exc) {
      setStatus(exc instanceof Error ? exc.message : "Paper open failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel intraday-panel">
      <div className="panel-header">
        <div>
          <strong>Intraday Desk</strong>
          <div className="muted">{tfMinutes ? `${tfMinutes}m timeframe` : "intraday"}</div>
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={() => manualPaper("long")} disabled={pending}>
            Paper Long
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => manualPaper("short")} disabled={pending}>
            Paper Short
          </button>
          <button type="button" className="btn btn-primary" onClick={paperFromSignal} disabled={pending || !signal}>
            <Zap size={14} />
            Paper-Trade Signal
          </button>
        </div>
      </div>
      <div className="panel-body stack">
        {status ? <div className="context-badge">{status}</div> : null}
        <div className="intraday-metrics">
          <Metric label="LTP" value={fmt(view.last_price)} />
          <Metric label="VWAP" value={fmt(view.vwap)} state={view.vwap_state} />
          <Metric label="ATR %" value={fmt(view.atr_pct, "%")} />
          <Metric label="RSI" value={fmt(view.rsi)} />
          <Metric label="MACD" value={view.macd_state || "-"} />
          <Metric label="MA20" value={fmt(view.ma20)} />
        </div>
        <div className="intraday-orb">
          <strong>Opening Range</strong>
          {orb ? (
            <div className="intraday-orb-grid">
              <span>{orb.bars} bars · {orb.session}</span>
              <span>High {fmt(orb.or_high)}</span>
              <span>Low {fmt(orb.or_low)}</span>
              <span>Range {fmt(orb.range_pct, "%")}</span>
              <strong className={`orb-state orb-${orb.state}`}>{prettyState(orb.state)}</strong>
            </div>
          ) : (
            <div className="muted">No opening range yet (need a few bars from session open).</div>
          )}
        </div>
        <div className="intraday-strategies">
          <strong>Intraday signals</strong>
          {strategies.length === 0 ? (
            <div className="muted">No active intraday triggers right now.</div>
          ) : (
            <ul>
              {strategies.map((strategy) => (
                <SignalRow key={strategy.id} strategy={strategy} active={signal?.id === strategy.id} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

function SignalRow({ strategy, active }: { strategy: IntradayStrategy; active: boolean }) {
  const Icon = strategy.direction === "long" ? ArrowUpRight : ArrowDownRight;
  return (
    <li className={`intraday-signal ${strategy.direction} ${active ? "primary" : ""}`}>
      <div className="intraday-signal-head">
        <Crosshair size={14} />
        <strong>{strategy.name}</strong>
        <span className={`badge ${strategy.direction}`}>{strategy.direction}</span>
        <span className="quality">{strategy.quality}%</span>
      </div>
      <p>
        <Icon size={12} />
        {strategy.trigger}
      </p>
      {strategy.entry || strategy.stop ? (
        <div className="intraday-signal-grid">
          <span>Entry {fmt(strategy.entry)}</span>
          <span>Stop {fmt(strategy.stop)}</span>
        </div>
      ) : null}
    </li>
  );
}

function Metric({ label, value, state }: { label: string; value: string; state?: string }) {
  return (
    <div className={`intraday-metric ${state ? `state-${state}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function prettyState(state: string) {
  return state.replace(/_/g, " ");
}

function fmt(value: unknown, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}
