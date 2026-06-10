"use client";

import { AlertsPanel, PositionOverlay } from "@/components/AccountTables";
import { AiAnalyst } from "@/components/AiAnalyst";
import { AnalysisPanels } from "@/components/AnalysisPanels";
import { BreadthPanel } from "@/components/BreadthPanel";
import { CatalystTimeline } from "@/components/CatalystTimeline";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import { DecisionCard } from "@/components/DecisionCard";
import { FundamentalsPanel } from "@/components/FundamentalsPanel";
import { IntradayPanel } from "@/components/IntradayPanel";
import { Metrics } from "@/components/Metrics";
import { OptionChainPanel } from "@/components/OptionChainPanel";
import { PaperTradeLedger } from "@/components/PaperTradeLedger";
import { QuantLab } from "@/components/QuantLab";
import { ResistanceLooker } from "@/components/ResistanceLooker";
import { StockCharts } from "@/components/StockCharts";
import { StrategyLab } from "@/components/StrategyLab";
import { TradePlan } from "@/components/TradePlan";
import { TradingViewPanel } from "@/components/TradingViewPanel";
import type { StockAnalysis } from "@/lib/types";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export type StockPanelId =
  | "decision"
  | "overview"
  | "trade_plan"
  | "metrics"
  | "tradingview"
  | "charts"
  | "quant"
  | "resistances"
  | "diagnostics"
  | "ai"
  | "account"
  | "news"
  | "intraday"
  | "paper"
  | "strategy_lab"
  | "fundamentals"
  | "option_chain"
  | "breadth";

export const STOCK_PANELS: Array<{ id: StockPanelId; title: string }> = [
  { id: "decision", title: "Decision" },
  { id: "intraday", title: "Intraday" },
  { id: "trade_plan", title: "Trade Plan" },
  { id: "tradingview", title: "TradingView" },
  { id: "charts", title: "Charts" },
  { id: "resistances", title: "Levels" },
  { id: "metrics", title: "Risk Metrics" },
  { id: "strategy_lab", title: "Strategy Lab" },
  { id: "fundamentals", title: "Fundamentals" },
  { id: "option_chain", title: "Option Chain" },
  { id: "breadth", title: "Market Breadth" },
  { id: "paper", title: "Paper" },
  { id: "ai", title: "AI" },
  { id: "news", title: "Catalysts" },
  { id: "account", title: "Account" },
  { id: "quant", title: "Quant Lab" },
  { id: "diagnostics", title: "Diagnostics" },
  { id: "overview", title: "Overview" },
];

export function StockPanelContent({ panel, analysis }: { panel: StockPanelId; analysis: StockAnalysis }) {
  if (panel === "decision") return <DecisionCard analysis={analysis} />;
  if (panel === "intraday") return <IntradayPanel analysis={analysis} />;
  if (panel === "overview") return <OverviewPanel analysis={analysis} />;
  if (panel === "trade_plan") return <TradePlan analysis={analysis} />;
  if (panel === "metrics") return <Metrics analysis={analysis.daily_analysis} riskPlan={analysis.risk_plan} />;
  if (panel === "tradingview") return <TradingViewPanel symbol={analysis.symbol} timeframe={analysis.intraday_timeframe ?? null} compact />;
  if (panel === "charts")
    return (
      <StockCharts
        daily={analysis.daily_candles}
        hourly={analysis.hourly_candles}
        intraday={analysis.intraday_candles || []}
        intradayLabel={analysis.intraday_timeframe || null}
        levels={analysis.daily_analysis.levels_v2 || analysis.daily_analysis.levels}
        overlays={analysis.chart_overlays}
        markers={analysis.chart_markers}
      />
    );
  if (panel === "quant") return <QuantLab analysis={analysis} />;
  if (panel === "resistances") return <ResistanceLooker levels={analysis.daily_analysis.levels} price={analysis.daily_analysis.last_price} symbol={analysis.symbol} analysis={analysis} />;
  if (panel === "diagnostics") return <AnalysisPanels analysis={analysis} />;
  if (panel === "ai") return <AiAnalyst analysis={analysis} />;
  if (panel === "paper") return <PaperTradeLedger symbolFilter={analysis.symbol} />;
  if (panel === "strategy_lab") return <StrategyLab defaultSymbol={analysis.symbol} />;
  if (panel === "fundamentals") return <FundamentalsPanel symbol={analysis.symbol} />;
  if (panel === "option_chain") return <OptionChainPanel symbol={analysis.symbol} />;
  if (panel === "breadth") return <BreadthPanel />;
  if (panel === "account") {
    return (
      <div className="grid gap-2 p-1">
        <PositionOverlay item={analysis.position_context} />
        <AlertsPanel alerts={analysis.alerts || []} />
      </div>
    );
  }
  if (panel === "news") return <CatalystTimeline catalysts={analysis.catalysts} />;
  return null;
}

function OverviewPanel({ analysis }: { analysis: StockAnalysis }) {
  const errors = Object.values(analysis.errors || {}).filter(Boolean);
  return (
    <div className="grid gap-2 p-1">
      <div className="flex flex-wrap items-center gap-2">
        <Link className="inline-flex h-8 w-fit items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-2.5 text-xs font-semibold text-slate-200 hover:border-emerald-400/40 hover:bg-emerald-400/10" href="/">
          <ArrowLeft size={16} />
          Search
        </Link>
        <Link className="inline-flex h-8 w-fit items-center rounded-md border border-white/10 bg-white/[0.03] px-2.5 text-xs font-semibold text-slate-200 hover:border-emerald-400/40 hover:bg-emerald-400/10" href="/account">
          Account cockpit
        </Link>
        <DataSourceBadge analysis={analysis} />
      </div>
      {errors.length ? (
        <section className="panel">
          <div className="panel-body">
            <strong>Data warning</strong>
            <p className="muted">{errors.join(" ")}</p>
          </div>
        </section>
      ) : null}
      <section className="panel">
        <div className="panel-body overview-identity">
          <span className="muted">Selected stock</span>
          <h2>{analysis.symbol}</h2>
          <p>{analysis.company}</p>
        </div>
      </section>
    </div>
  );
}

export function normalizeStockPanel(value: string): StockPanelId {
  return STOCK_PANELS.some((panel) => panel.id === value) ? (value as StockPanelId) : "tradingview";
}
