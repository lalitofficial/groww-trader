import type { StockAnalysis } from "@/lib/types";

export type DecisionTone = "go" | "watch" | "avoid" | "divergent";

export type DecisionState = {
  tone: DecisionTone;
  intent: string;
  urgency: "hot" | "normal" | "low";
  divergence: null | {
    daily: string;
    intraday: string;
  };
};

export function useDecisionState(analysis: StockAnalysis, livePrice?: number | null): DecisionState {
  const daily = analysis.daily_analysis || {};
  const plan = daily.trade_plan || {};
  const signal = analysis.intraday_view?.primary_signal || null;
  const hasWarning = Object.values(analysis.errors || {}).some(Boolean) || Boolean(analysis.stale_cache_used);
  const dailyStance = normalizeDaily(plan.action, plan.grade);
  const intradayStance = normalizeIntraday(signal);
  const divergence = dailyStance && intradayStance && dailyStance !== intradayStance ? { daily: dailyStance, intraday: intradayStance } : null;
  const stop = numberOrNull(plan.stop_loss ?? signal?.stop);
  const price = numberOrNull(livePrice ?? daily.last_price ?? signal?.entry);
  const atr = numberOrNull(plan.atr ?? analysis.intraday_view?.atr);
  const atrDistance = price !== null && stop !== null && atr ? Math.abs(price - stop) / atr : null;

  let tone: DecisionTone = "avoid";
  if (divergence) tone = "divergent";
  else if (hasWarning) tone = "watch";
  else if (dailyStance === "long" || dailyStance === "short" || intradayStance === "long" || intradayStance === "short") tone = "go";
  else if (dailyStance === "watch" || intradayStance === "watch") tone = "watch";

  const urgency: DecisionState["urgency"] = signal?.active || (atrDistance !== null && atrDistance <= 1.2) ? "hot" : tone === "avoid" ? "low" : "normal";
  const intent = microcopy(tone, dailyStance, intradayStance, signal?.name, hasWarning);
  return { tone, intent, urgency, divergence };
}

function normalizeDaily(action: unknown, grade: unknown) {
  const actionText = String(action || "").toLowerCase();
  const gradeText = String(grade || "").toUpperCase();
  if (actionText.includes("avoid") || gradeText === "D") return "avoid";
  if (actionText.includes("short")) return "short";
  if (actionText.includes("buy") || actionText.includes("long") || actionText.includes("actionable") || gradeText === "A" || gradeText === "B") return "long";
  if (actionText.includes("watch") || actionText.includes("developing") || gradeText.startsWith("C")) return "watch";
  return "";
}

function normalizeIntraday(signal: any) {
  if (!signal) return "";
  if (!signal.active) return "watch";
  if (signal.direction === "long") return "long";
  if (signal.direction === "short") return "short";
  return "watch";
}

function microcopy(tone: DecisionTone, daily: string, intraday: string, signalName?: string, warning?: boolean) {
  if (warning) return "Data warning - verify before acting";
  if (tone === "divergent") return `Daily ${daily || "mixed"}; intraday ${intraday || "mixed"}`;
  if (tone === "go" && signalName) return `Actionable now - ${signalName} hot`;
  if (tone === "go") return "Actionable setup - plan and risk aligned";
  if (tone === "watch") return "Daily setup waiting; intraday neutral";
  return "Low quality setup - protect capital";
}

function numberOrNull(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
