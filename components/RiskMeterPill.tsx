"use client";

import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { getCurrentSession, getPaperSummary } from "@/lib/api";
import type { PaperSummary } from "@/lib/types";

const DAILY_LOSS_PCT_DEFAULT = 3; // mirrors INTRADAY_MAX_DAILY_LOSS_PCT default
const ESTIMATED_CAPITAL_KEY = "groww-daily-capital";

export function RiskMeterPill() {
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [picks, setPicks] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [paperSummary, session] = await Promise.all([getPaperSummary(), getCurrentSession()]);
        if (cancelled) return;
        setSummary(paperSummary);
        setPicks(session.picks?.length ?? 0);
      } catch {
        /* swallow */
      }
    }
    void load();
    const id = window.setInterval(load, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!summary) return null;
  const capital = readCapital();
  const dailyLossCap = capital * (DAILY_LOSS_PCT_DEFAULT / 100);
  const realized = summary.total_pnl;
  const usedPct = realized < 0 ? Math.min(100, (Math.abs(realized) / dailyLossCap) * 100) : 0;
  const tone = usedPct >= 90 ? "red" : usedPct >= 70 ? "amber" : "green";

  return (
    <div className={`risk-meter-pill tone-${tone}`} title="Daily loss vs cap">
      <ShieldAlert size={12} />
      <span>Risk</span>
      <strong>{usedPct.toFixed(0)}%</strong>
      <span className="muted">{realized.toFixed(0)} / -{dailyLossCap.toFixed(0)}</span>
      <span className="muted">· {picks} pick{picks === 1 ? "" : "s"}</span>
    </div>
  );
}

function readCapital() {
  if (typeof window === "undefined") return 500000;
  const stored = window.localStorage.getItem(ESTIMATED_CAPITAL_KEY);
  return Number(stored) || 500000;
}
