"use client";

import { useMemo, useState } from "react";
import type { StockAnalysis } from "@/lib/types";

type TradePlanTab = "daily" | "intraday" | "risk";

export function TradePlan({ analysis }: { analysis: StockAnalysis }) {
  const dailyPlan = analysis.daily_analysis?.trade_plan;
  const intradayPlan = analysis.intraday_analysis?.trade_plan;
  const risk = analysis.risk_plan || {};
  const tabs = useMemo(
    () => [
      { id: "daily" as const, label: "Daily", disabled: !dailyPlan },
      { id: "intraday" as const, label: analysis.intraday_timeframe ? `Intraday ${analysis.intraday_timeframe}` : "Intraday", disabled: !intradayPlan },
      { id: "risk" as const, label: "Risk", disabled: false },
    ],
    [analysis.intraday_timeframe, dailyPlan, intradayPlan],
  );
  const [tab, setTab] = useState<TradePlanTab>(dailyPlan ? "daily" : intradayPlan ? "intraday" : "risk");
  const activeTab = tabs.find((item) => item.id === tab && !item.disabled)?.id || "risk";

  return (
    <section className="trade-plan-tabbed dq-card tone-watch">
      <div className="trade-tabs" role="tablist" aria-label="Trade plan views">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            className={activeTab === item.id ? "active" : ""}
            disabled={item.disabled}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {activeTab === "daily" && dailyPlan ? <PlanView kind="Daily / Swing" plan={dailyPlan} /> : null}
      {activeTab === "intraday" && intradayPlan ? <PlanView kind="Intraday" plan={intradayPlan} /> : null}
      {activeTab === "risk" ? <RiskView risk={risk} /> : null}
    </section>
  );
}

function PlanView({ kind, plan }: { kind: string; plan: any }) {
  return (
    <div className="trade-plan-card compact">
      <div className="trade-plan-main">
        <div>
          <span className="muted">{kind}</span>
          <h2>{plan.action || "No action"}</h2>
          <p>{plan.analyst_note || "No analyst note available."}</p>
        </div>
        <div className={`grade grade-${String(plan.grade || "").replace("-", "").toLowerCase()}`}>
          <span>Grade</span>
          <strong>{plan.grade || "-"}</strong>
        </div>
      </div>

      <div className="trade-plan-grid">
        <TradeBox label="Bias" value={plan.bias} />
        <TradeBox label="Setup" value={plan.setup_type} />
        <TradeBox label="Score" value={plan.score} />
        <TradeBox label="Entry zone" value={`${fmt(plan.entry_zone?.low)} - ${fmt(plan.entry_zone?.high)}`} />
        <TradeBox label="Stop" value={fmt(plan.stop_loss)} />
        <TradeBox label="ATR / mult" value={`${fmt(plan.atr)} x${plan.atr_mult ?? "-"}`} />
        <TradeBox label="Invalidation" value={plan.invalidation} wide />
      </div>

      <div className="trade-plan-details">
        <details open>
          <summary>Targets</summary>
          <div className="target-list">
            {(plan.targets || []).map((target: any) => (
              <div className="kv" key={target.label}>
                <span>{target.label}</span>
                <strong>{fmt(target.price)}</strong>
              </div>
            ))}
            {(plan.targets || []).length === 0 ? <div className="muted">No targets resolved.</div> : null}
          </div>
        </details>
        <details open>
          <summary>Checklist</summary>
          <div className="check-list">
            {(plan.checklist || []).map((item: any) => (
              <div className={`check ${item.status}`} key={item.label}>
                <span>{item.status === "pass" ? "PASS" : "WAIT"}</span>
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.detail}</p>
                </div>
              </div>
            ))}
            {(plan.checklist || []).length === 0 ? <div className="muted">No checklist returned.</div> : null}
          </div>
        </details>
      </div>
    </div>
  );
}

function RiskView({ risk }: { risk: Record<string, any> }) {
  return (
    <section className="trade-plan-risk compact">
      <strong>Risk allocation</strong>
      <div className="trade-plan-grid">
        <TradeBox label="Capital" value={fmt(risk.account_capital)} />
        <TradeBox label="Risk %" value={`${risk.risk_per_trade_pct ?? "-"}%`} />
        <TradeBox label="Risk budget" value={fmt(risk.risk_budget)} />
        <TradeBox label="Risk / share" value={fmt(risk.risk_per_share)} />
        <TradeBox label="Swing qty" value={fmt(risk.swing_quantity)} />
        <TradeBox label="Intraday qty" value={fmt(risk.intraday_quantity)} />
        <TradeBox label="Leverage" value={`${risk.intraday_leverage ?? 1}x intraday`} />
        <TradeBox label="Max intra value" value={fmt(risk.max_intraday_position_value)} />
      </div>
    </section>
  );
}

function TradeBox({ label, value, wide = false }: { label: string; value: unknown; wide?: boolean }) {
  return (
    <div className={`trade-box ${wide ? "wide" : ""}`}>
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(value ?? "-");
}
