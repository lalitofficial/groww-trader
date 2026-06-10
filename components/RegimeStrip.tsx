"use client";

import { ArrowDownRight, ArrowUpRight, Gauge, Layers } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { RegimeSnapshot } from "@/lib/types";
import { getRegime } from "@/lib/api";

export function RegimeStrip() {
  const [regime, setRegime] = useState<RegimeSnapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError("");
    try {
      const data = await getRegime(refresh);
      setRegime(data);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Regime unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  if (error && !regime) {
    return <div className="regime-strip muted">Regime unavailable. {error}</div>;
  }

  if (!regime) {
    return <div className="regime-strip muted">Loading market regime…</div>;
  }

  const bench = regime.benchmark || {};
  const mode = regime.trade_mode || {};
  const breadth = regime.sector_breadth || { advancing: 0, declining: 0, total: 0, advance_decline_ratio: null };
  const watchBreadth = regime.watchlist_breadth || { advancing: 0, declining: 0, total: 0 };
  const biasClass = mode.intraday_long_bias ? "long" : mode.intraday_short_bias ? "short" : "neutral";

  return (
    <section className={`regime-strip regime-${biasClass}`}>
      <div className="regime-headline">
        <div>
          <span className="muted">Index regime</span>
          <strong>{bench.symbol || "NIFTY"}</strong>
        </div>
        <RegimeBlock label="Trend" value={prettyTrend(bench.trend)} accent />
        <RegimeBlock label="Last" value={fmt(bench.last)} />
        <RegimeBlock
          label="1D %"
          value={fmt(bench.change_1d_pct, "%")}
          icon={(bench.change_1d_pct ?? 0) >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          positive={(bench.change_1d_pct ?? 0) >= 0}
        />
        <RegimeBlock label="ATR%" value={fmt(bench.atr_pct, "%")} />
        <RegimeBlock label="RSI" value={fmt(bench.rsi)} />
      </div>
      <div className="regime-mode">
        <Gauge size={14} />
        <strong>{mode.bias || "unknown"}</strong>
        <span>{mode.reason}</span>
      </div>
      <div className="regime-breadth">
        <Layers size={14} />
        <span>
          Sectors {breadth.advancing}/{breadth.total} up
          {breadth.advance_decline_ratio !== null ? ` (A/D ${breadth.advance_decline_ratio})` : ""}
        </span>
        <span>
          Watchlist {watchBreadth.advancing}/{watchBreadth.total} up
        </span>
        <button type="button" className="regime-refresh" onClick={() => load(true)} disabled={loading}>
          {loading ? "…" : "Refresh"}
        </button>
      </div>
    </section>
  );
}

function RegimeBlock({ label, value, icon, accent = false, positive }: { label: string; value: string; icon?: React.ReactNode; accent?: boolean; positive?: boolean }) {
  return (
    <div className={`regime-block ${accent ? "accent" : ""} ${positive === undefined ? "" : positive ? "up" : "down"}`}>
      <span>{label}</span>
      <strong>
        {icon}
        {value}
      </strong>
    </div>
  );
}

function prettyTrend(value?: string | null) {
  if (!value) return "unknown";
  return value.replace(/_/g, " ");
}

function fmt(value: unknown, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}
