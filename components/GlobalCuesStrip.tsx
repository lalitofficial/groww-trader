"use client";

import { ArrowDownRight, ArrowUpRight, Globe2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getGlobalCues } from "@/lib/api";
import type { GlobalCue } from "@/lib/types";

const GROUP_ORDER = ["us_futures", "asia", "india", "commodity", "fx"];
const GROUP_LABEL: Record<string, string> = {
  us_futures: "US Futures",
  asia: "Asia",
  india: "India",
  commodity: "Commodities",
  fx: "FX",
};

export function GlobalCuesStrip() {
  const [cues, setCues] = useState<Record<string, GlobalCue[]>>({});
  const [loading, setLoading] = useState(false);
  const [asOf, setAsOf] = useState<number | null>(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const data = await getGlobalCues(refresh);
      setCues(data.by_group || {});
      setAsOf(data.as_of);
    } catch {
      /* swallow */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="global-cues-strip">
      <header>
        <div className="global-cues-title">
          <Globe2 size={14} />
          <strong>Global cues</strong>
          {asOf ? <span className="muted">· {new Date(asOf * 1000).toLocaleTimeString()}</span> : null}
        </div>
        <button type="button" className="btn-icon" onClick={() => load(true)} disabled={loading} title="Refresh">
          <RefreshCw size={13} />
        </button>
      </header>
      <div className="global-cues-grid">
        {GROUP_ORDER.map((group) => {
          const rows = cues[group] || [];
          if (!rows.length) return null;
          return (
            <div key={group} className="global-cues-group">
              <span className="muted">{GROUP_LABEL[group] || group}</span>
              <div className="global-cues-rows">
                {rows.map((row) => (
                  <div key={row.symbol} className="global-cue-tile">
                    <strong>{row.label}</strong>
                    <span className="cue-last">{fmt(row.last)}</span>
                    <span className={cueClass(row.change_pct)}>
                      {(row.change_pct ?? 0) >= 0 ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
                      {pct(row.change_pct)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function cueClass(change: number | undefined) {
  if (change === undefined || change === null) return "muted";
  return change >= 0 ? "cue-up" : "cue-down";
}

function fmt(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) return "-";
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function pct(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}%`;
}
