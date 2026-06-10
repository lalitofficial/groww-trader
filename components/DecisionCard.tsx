"use client";

import { AlertTriangle, Bell, Bot, CheckCircle2, CircleSlash2, Gauge, Layers, PlayCircle, Target, XCircle, Zap } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { useDecisionState } from "@/hooks/useDecisionState";
import { useLivePrice } from "@/hooks/useLivePrice";
import { autoOpenPaperTrade, openPaperTrade } from "@/lib/api";
import type { StockAnalysis, Timeframe } from "@/lib/types";
import { useWorkstation } from "@/components/WorkstationContext";

const STOP_ALERTS_KEY = "groww-stop-alerts-v1";

type TargetRow = { label?: string; price?: number | null };

export function DecisionCard({ analysis }: { analysis: StockAnalysis }) {
  const workstation = useWorkstation();
  const daily = analysis.daily_analysis || {};
  const plan = daily.trade_plan || {};
  const risk = analysis.risk_plan || {};
  const intraday = analysis.intraday_view || null;
  const signal = intraday?.primary_signal || null;
  const source = analysis.data_source?.daily || {};
  const errors = Object.values(analysis.errors || {}).filter(Boolean);
  const entry = entryPrice(plan.entry_zone, signal?.entry, daily.last_price);
  const stop = numberOrNull(plan.stop_loss ?? signal?.stop);
  const firstTarget = firstTargetPrice(plan.targets);
  const live = useLivePrice(analysis.symbol, { entry, stop, fallbackPrice: daily.last_price });
  const state = useDecisionState(analysis, live.price);
  const [actionStatus, setActionStatus] = useState("");
  const checklist = Array.isArray(plan.checklist) ? plan.checklist : [];
  const passed = checklist.filter((item: { status?: string }) => item.status === "pass").length;
  const total = checklist.length || 5;
  const Icon = state.tone === "go" ? CheckCircle2 : state.tone === "avoid" ? CircleSlash2 : AlertTriangle;
  const targets = useMemo(() => normalizeTargets(plan.targets), [plan.targets]);

  async function paperTrade() {
    setActionStatus("Opening paper trade...");
    try {
      if (signal?.active && signal.entry) {
        const result = await autoOpenPaperTrade({ symbol: analysis.symbol, timeframe: safeTimeframe(analysis.intraday_timeframe) });
        setActionStatus(result.opened ? `Paper trade #${result.opened.id} opened` : result.reason || "No paper trade opened");
        return;
      }
      const quantity = Number(risk.swing_quantity || risk.estimated_quantity || risk.intraday_quantity || 1);
      const trade = await openPaperTrade({
        symbol: analysis.symbol,
        side: signal?.direction === "short" || String(plan.action || "").toLowerCase().includes("short") ? "SELL" : "BUY",
        quantity: Math.max(1, Math.floor(Number.isFinite(quantity) ? quantity : 1)),
        entry_price: entry || Number(daily.last_price || 0),
        product: "delivery",
        stop_loss: stop,
        target: firstTarget,
        strategy_id: "decision_card",
        timeframe: workstation?.timeframe || "daily",
        grade: String(plan.grade || ""),
        notes: plan.analyst_note || "Decision card paper trade",
      });
      setActionStatus(`Paper trade #${trade.id} opened`);
    } catch (exc) {
      setActionStatus(exc instanceof Error ? exc.message : "Paper trade failed");
    }
  }

  function runStrategyLab() {
    workstation?.openPanel("strategy_lab");
    setActionStatus("StrategyLab opened");
  }

  function alertAtStop() {
    if (!stop) {
      setActionStatus("Stop unavailable");
      return;
    }
    const next = readStopAlerts().filter((item) => item.symbol !== analysis.symbol);
    next.push({ symbol: analysis.symbol, stop, createdAt: new Date().toISOString(), note: plan.invalidation || "" });
    window.localStorage.setItem(STOP_ALERTS_KEY, JSON.stringify(next));
    setActionStatus(`Local stop reminder saved at ${fmt(stop)}`);
  }

  return (
    <section className={`dq-card tone-${state.tone} urgency-${state.urgency}`}>
      <div className="dq-hero">
        <div className="dq-symbol">
          <span>{analysis.company}</span>
          <strong>{analysis.symbol}</strong>
          <em>{state.intent}</em>
        </div>
        <div className="dq-action">
          <Icon size={18} />
          <span>{state.tone === "go" ? "Actionable" : state.tone === "divergent" ? "Divergence" : state.tone === "watch" ? "Watch" : "Avoid"}</span>
          <strong>{plan.action || "No decision"}</strong>
        </div>
        <div className="dq-grade-box">
          <span>Grade</span>
          <strong>{plan.grade || "-"}</strong>
        </div>
      </div>

      {state.divergence ? (
        <div className="dq-divergence">
          <Zap size={14} />
          <strong>Divergence</strong>
          <span>Daily: {state.divergence.daily}</span>
          <span>Intraday: {state.divergence.intraday}</span>
        </div>
      ) : null}

      <div className="dq-strip">
        <DecisionMetric label="LTP" value={fmt(live.price ?? daily.last_price)} hot />
        <DecisionMetric label="Entry drift" value={pct(live.driftFromEntryPct)} />
        <DecisionMetric label="Stop dist" value={pct(live.distanceToStopPct)} />
        <DecisionMetric label="Score" value={fmt(plan.score ?? daily.technical_score)} />
        <DecisionMetric label="Trend" value={daily.trend_state || "-"} />
        <DecisionMetric label="R:R" value={fmt(daily.risk_reward)} />
        <DecisionMetric label="Checklist" value={`${passed}/${total}`} />
      </div>

      <TargetsBar entry={entry} stop={stop} targets={targets} price={live.price ?? daily.last_price} />

      <div className="dq-plan">
        <DecisionLevel icon={<Gauge size={14} />} label="Entry" value={entryZone(plan.entry_zone)} />
        <DecisionLevel icon={<XCircle size={14} />} label="Stop" value={fmt(stop)} />
        <DecisionLevel icon={<Target size={14} />} label="Next target" value={fmt(firstTarget)} />
        <DecisionLevel icon={<Layers size={14} />} label="Sizing" value={`Swing ${fmt(risk.swing_quantity)} / Intra ${fmt(risk.intraday_quantity)}`} />
      </div>

      {signal ? (
        <div className="dq-intraday">
          <Zap size={14} />
          <div>
            <strong>Intraday signal · {signal.name}</strong>
            <p>{signal.trigger}</p>
          </div>
          <div className="dq-intraday-stats">
            <span>{signal.direction}</span>
            <span>{signal.quality}%</span>
          </div>
        </div>
      ) : null}

      <div className="dq-details-grid">
        <details className="dq-details" open>
          <summary>Checklist</summary>
          <div className="dq-detail-body dq-checklist">
            {checklist.map((item: any) => (
              <div className={`dq-check ${item.status}`} key={item.label}>
                <span>{item.status === "pass" ? "PASS" : "WAIT"}</span>
                <p>
                  <strong>{item.label}</strong>
                  {item.detail}
                </p>
              </div>
            ))}
            {!checklist.length ? <p className="muted">No checklist returned.</p> : null}
          </div>
        </details>
        <details className="dq-details" open>
          <summary>Risk allocation</summary>
          <div className="dq-detail-body dq-risk-mini">
            <DecisionMetric label="Risk budget" value={fmt(risk.risk_budget)} />
            <DecisionMetric label="Risk/share" value={fmt(risk.risk_per_share)} />
            <DecisionMetric label="Leverage" value={`${risk.intraday_leverage ?? 1}x`} />
          </div>
        </details>
      </div>

      <div className="dq-note">
        <strong>Invalidation</strong>
        <p>{plan.invalidation || "No invalidation rule available."}</p>
      </div>
      <div className="dq-note dq-evidence">
        <strong>Reason</strong>
        <p>{plan.analyst_note || "Analysis did not return a clean thesis."}</p>
      </div>

      <div className="dq-actionbar">
        <button type="button" onClick={paperTrade}>
          <PlayCircle size={14} />
          Paper-trade this
        </button>
        <button type="button" onClick={runStrategyLab}>
          <Bot size={14} />
          Run StrategyLab
        </button>
        <button type="button" onClick={alertAtStop}>
          <Bell size={14} />
          Alert at stop
        </button>
      </div>

      <div className="dq-footer">
        <span>{live.loading ? "live quote loading" : live.error ? "live quote fallback" : `${live.provider || source.provider || "source"} ${live.freshness || ""}`}</span>
        <span>{source.freshness || analysis.data_freshness?.daily || "unknown freshness"}</span>
        {analysis.stale_cache_used ? <span>stale cache</span> : null}
        {errors.length ? <span>{errors.length} data warning{errors.length > 1 ? "s" : ""}</span> : null}
        {actionStatus ? <span>{actionStatus}</span> : null}
      </div>
    </section>
  );
}

function DecisionMetric({ label, value, hot = false }: { label: string; value: unknown; hot?: boolean }) {
  return (
    <div className={hot ? "hot" : ""}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function DecisionLevel({ icon, label, value }: { icon: ReactNode; label: string; value: unknown }) {
  return (
    <div className="dq-level">
      {icon}
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function TargetsBar({ entry, stop, targets, price }: { entry: number | null; stop: number | null; targets: TargetRow[]; price: unknown }) {
  const values = [entry, stop, numberOrNull(price), ...targets.map((target) => numberOrNull(target.price))].filter((value): value is number => value !== null);
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 0.01);
  const pos = (value: number | null) => (value === null ? 0 : Math.min(100, Math.max(0, ((value - min) / span) * 100)));

  return (
    <div className="dq-targets-bar">
      <div className="dq-bar-track">
        {stop !== null ? <span className="dq-bar-stop" style={{ left: `${pos(stop)}%` }} /> : null}
        {entry !== null ? <span className="dq-bar-entry" style={{ left: `${pos(entry)}%` }} /> : null}
        {targets.map((target, index) =>
          numberOrNull(target.price) !== null ? <span key={`${target.label || "T"}-${index}`} className="dq-bar-target" style={{ left: `${pos(numberOrNull(target.price))}%` }} /> : null,
        )}
        {numberOrNull(price) !== null ? <span className="dq-bar-ltp" style={{ left: `${pos(numberOrNull(price))}%` }} /> : null}
      </div>
      <div className="dq-bar-labels">
        <span>Stop {fmt(stop)}</span>
        <span>Entry {fmt(entry)}</span>
        {targets.slice(0, 3).map((target) => (
          <span key={target.label || String(target.price)}>
            {target.label || "T"} {fmt(target.price)}
          </span>
        ))}
      </div>
    </div>
  );
}

function readStopAlerts(): Array<{ symbol: string; stop: number; createdAt: string; note?: string }> {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STOP_ALERTS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizeTargets(targets: unknown): TargetRow[] {
  if (!Array.isArray(targets)) return [];
  return targets
    .map((target: any, index) => ({ label: target?.label || `T${index + 1}`, price: numberOrNull(target?.price) }))
    .filter((target) => target.price !== null);
}

function firstTargetPrice(targets: unknown) {
  return normalizeTargets(targets)[0]?.price ?? null;
}

function entryPrice(entryZoneValue: unknown, signalEntry?: number | null, fallback?: unknown) {
  if (typeof signalEntry === "number") return signalEntry;
  if (entryZoneValue && typeof entryZoneValue === "object") {
    const zone = entryZoneValue as { low?: unknown; high?: unknown };
    const low = numberOrNull(zone.low);
    const high = numberOrNull(zone.high);
    if (low !== null && high !== null) return (low + high) / 2;
    return low ?? high;
  }
  return numberOrNull(fallback);
}

function entryZone(value: unknown) {
  if (!value || typeof value !== "object") return "-";
  const zone = value as { low?: unknown; high?: unknown };
  return `${fmt(zone.low)} - ${fmt(zone.high)}`;
}

function safeTimeframe(value: unknown): Timeframe {
  return value === "5m" || value === "15m" || value === "30m" || value === "hourly" || value === "daily" ? value : "15m";
}

function numberOrNull(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function pct(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

function fmt(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(value ?? "-");
}
