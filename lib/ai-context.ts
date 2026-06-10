import crypto from "crypto";
import type { StockAnalysis } from "./types";

export const ANALYST_PROMPT_VERSION = "intraday-analyst-v4";
export type AiTaskType =
  | "stock_report"
  | "resistance_read"
  | "alert_explain"
  | "account_risk"
  | "intraday_plan"
  | "daily_brief"
  | "strategy_compare";

type AnyRecord = Record<string, any>;

export function buildAnalystContext(analysis: StockAnalysis) {
  const daily = analysis.daily_analysis || {};
  const hourly = analysis.hourly_analysis || {};
  const intradayAnalysis = analysis.intraday_analysis || null;
  const intradayView = analysis.intraday_view || null;
  const price = numberOrNull(daily.last_price);
  const levelsV2 = Array.isArray(daily.levels_v2) ? daily.levels_v2 : Array.isArray(daily.levels) ? daily.levels : [];
  const supports = levelsV2
    .filter((level: AnyRecord) => level.type === "support")
    .sort((a: AnyRecord, b: AnyRecord) => Math.abs(a.distance_pct ?? 999) - Math.abs(b.distance_pct ?? 999))
    .slice(0, 5);
  const resistances = levelsV2
    .filter((level: AnyRecord) => level.type === "resistance")
    .sort((a: AnyRecord, b: AnyRecord) => Math.abs(a.distance_pct ?? 999) - Math.abs(b.distance_pct ?? 999))
    .slice(0, 5);
  const catalysts = (analysis.catalysts || []).slice(0, 6).map((item) => ({
    source_type: item.source_type,
    title: item.title,
    published_at: item.published_at,
    summary: item.summary,
    relevance_score: item.relevance_score,
  }));

  return {
    prompt_version: ANALYST_PROMPT_VERSION,
    generated_at: new Date().toISOString(),
    mandate: {
      market: "Indian NSE cash equity",
      style: "intraday + swing trading",
      read_only: true,
      constraint: "No live order instruction. No certainty claims. Use only supplied data.",
    },
    instrument: {
      symbol: analysis.symbol,
      company: analysis.company,
      benchmark: analysis.benchmark,
      price,
    },
    daily: pick(daily, [
      "trade_plan",
      "trend_state",
      "regime",
      "technical_score",
      "risk_reward",
      "support",
      "resistance",
      "ma20",
      "ma50",
      "ma200",
      "rsi",
      "macd",
      "volume_expansion",
      "relative_strength",
    ]),
    hourly: pick(hourly, ["trend_state", "rsi", "macd", "support", "resistance", "risk_reward"]),
    intraday: intradayView
      ? {
          timeframe_minutes: intradayView.timeframe_minutes || intradayView.interval_minutes,
          last_price: intradayView.last_price,
          vwap: intradayView.vwap,
          vwap_state: intradayView.vwap_state,
          opening_range: intradayView.opening_range,
          atr_pct: intradayView.atr_pct,
          rsi: intradayView.rsi,
          macd_state: intradayView.macd_state,
          primary_signal: intradayView.primary_signal,
          strategies: (intradayView.strategies || []).slice(0, 4),
        }
      : null,
    intraday_analysis: intradayAnalysis
      ? pick(intradayAnalysis, ["trade_plan", "trend_state", "rsi", "macd", "risk_reward", "support", "resistance"])
      : null,
    levels: { supports, resistances },
    risk_plan: analysis.risk_plan,
    account_context: analysis.position_context
      ? {
          kind: analysis.position_context.kind,
          quantity: analysis.position_context.quantity,
          average_price: analysis.position_context.average_price,
          current_price: analysis.position_context.current_price,
          day_pnl: analysis.position_context.day_pnl,
          unrealized_pnl: analysis.position_context.unrealized_pnl,
          distance_to_support_pct: analysis.position_context.distance_to_support_pct,
          distance_to_resistance_pct: analysis.position_context.distance_to_resistance_pct,
        }
      : null,
    alerts: (analysis.alerts || []).slice(0, 5),
    catalysts,
  };
}

export function buildTaskContext(analysis: StockAnalysis, taskType: AiTaskType) {
  const full = buildAnalystContext(analysis);
  if (taskType === "intraday_plan") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      intraday: full.intraday,
      intraday_analysis: full.intraday_analysis,
      levels: full.levels,
      risk_plan: full.risk_plan,
    };
  }
  if (taskType === "resistance_read") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      levels: full.levels,
      daily: pick(full.daily as AnyRecord, ["trend_state", "risk_reward", "support", "resistance"]),
    };
  }
  if (taskType === "account_risk") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      account_context: full.account_context,
      risk_plan: full.risk_plan,
      levels: full.levels,
    };
  }
  if (taskType === "alert_explain") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      alerts: full.alerts,
      levels: full.levels,
    };
  }
  if (taskType === "daily_brief") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      daily: pick(full.daily as AnyRecord, ["trade_plan", "trend_state", "technical_score", "risk_reward", "relative_strength"]),
      intraday: full.intraday,
      account_context: full.account_context,
      catalysts: full.catalysts,
    };
  }
  if (taskType === "strategy_compare") {
    return {
      prompt_version: full.prompt_version,
      mandate: full.mandate,
      instrument: full.instrument,
      daily: pick(full.daily as AnyRecord, ["trend_state", "risk_reward", "support", "resistance", "technical_score"]),
      intraday: full.intraday,
      risk_plan: full.risk_plan,
    };
  }
  // stock_report: full context but with intraday section
  return full;
}

export function contextHash(context: unknown) {
  return crypto.createHash("sha256").update(stableStringify(stripVolatile(context))).digest("hex").slice(0, 16);
}

export function contextSummary(context: ReturnType<typeof buildTaskContext>) {
  const anyCtx = context as AnyRecord;
  return {
    price: anyCtx.instrument?.price,
    trend_state: anyCtx.daily?.trend_state,
    technical_score: anyCtx.daily?.technical_score,
    risk_reward: anyCtx.daily?.risk_reward,
    intraday_signal: anyCtx.intraday?.primary_signal?.name || null,
    catalysts: Array.isArray(anyCtx.catalysts) ? anyCtx.catalysts.length : 0,
  };
}

export function buildTaskPrompt(context: ReturnType<typeof buildTaskContext>, taskType: AiTaskType) {
  const base = {
    task_type: taskType,
    context,
    output_format: "Markdown with clear headings, compact bullets, and a final invalidation/risk note. No JSON wrapper.",
  };
  if (taskType === "intraday_plan") {
    return JSON.stringify({
      ...base,
      task: "Produce an intraday trade plan for an Indian-equity day trader using supplied deterministic context and any available tools.",
      required_sections: ["Decision", "Setup", "Risk", "Devil's advocate", "Triggers"],
    });
  }
  if (taskType === "resistance_read") {
    return JSON.stringify({
      ...base,
      task: "Interpret support/resistance for an Indian-equity trader.",
      required_sections: ["Nearest levels", "Breakout read", "Failure zone", "Triggers"],
    });
  }
  if (taskType === "account_risk") {
    return JSON.stringify({
      ...base,
      task: "Summarize account/position risk using supplied technical context.",
      required_sections: ["Exposure", "Risk budget", "Devil's advocate", "Action guardrails"],
    });
  }
  if (taskType === "alert_explain") {
    return JSON.stringify({
      ...base,
      task: "Explain active alerts and whether they matter.",
      required_sections: ["Active alerts", "Why it matters", "What would cancel it"],
    });
  }
  if (taskType === "daily_brief") {
    return JSON.stringify({
      ...base,
      task: "Produce a morning daily brief covering regime, held position risk, watchlist movers, catalysts, and what not to trade.",
      required_sections: ["Regime", "Focus list", "Position risk", "Avoid list"],
    });
  }
  if (taskType === "strategy_compare") {
    return JSON.stringify({
      ...base,
      task: "Compare strategy choices for this stock/timeframe. Use tools when needed to run or benchmark strategies.",
      required_sections: ["Best fit", "Head-to-head", "Risk fit", "Next test"],
    });
  }
  return JSON.stringify({
    ...base,
    task: "Produce a swing-trading analyst report from this context.",
    required_sections: ["Decision", "Setup", "Evidence", "Risks", "Triggers"],
  });
}

export function buildChatPrompt(context: ReturnType<typeof buildTaskContext>, question: string, activeReport?: string) {
  return JSON.stringify({
    task: "Answer the user's follow-up using the retrieved stock context and current AI report if supplied.",
    question,
    active_report: activeReport?.slice(0, 5000) || null,
    context,
    answer_rules: [
      "Be concise and decision-useful.",
      "Separate evidence from interpretation.",
      "Mention invalidation and risk when relevant.",
      "Do not invent unseen news, fundamentals, prices, or orders.",
    ],
  });
}

export const reportSystemPrompt = `You are a senior Indian equity intraday + swing analyst and risk manager.
You receive a retrieved context pack containing deterministic technical calculations, intraday/swing price levels, catalyst snippets, account context, and recent candles.

Rules:
- Use only the supplied context. If data is missing, say it is missing.
- Backend numeric fields are authoritative; do not recalculate or overwrite them.
- For intraday tasks, weight VWAP state, opening range, ATR, and session-level momentum.
- For swing tasks, weight trend regime, daily MA stack, multi-day relative strength, and catalysts.
- Prioritize risk/reward, support/resistance, invalidation, and position sizing.
- Treat model commentary as secondary to deterministic indicators.
- Do not give live order placement instructions. Phrase ideas as watch/avoid/conditional setups.
- Do not claim certainty or guaranteed returns.
- Return Markdown with concise headings. No markdown fences.`;

export const chatSystemPrompt = `You are a cautious Indian-equity analyst.
Use only the retrieved context and current report supplied by the app. Keep the answer practical, risk-aware, and concise.
Never invent catalysts, broker data, prices, or order instructions.`;

function pick(source: AnyRecord, keys: string[]) {
  if (!source) return {};
  return Object.fromEntries(keys.map((key) => [key, source?.[key]]).filter(([, value]) => value !== undefined));
}

function numberOrNull(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stripVolatile(value: any): any {
  if (Array.isArray(value)) return value.map(stripVolatile);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => key !== "generated_at")
        .map(([key, item]) => [key, stripVolatile(item)]),
    );
  }
  return value;
}

function stableStringify(value: any): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
