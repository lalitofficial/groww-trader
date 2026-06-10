"use client";

import { CalendarDays, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getCalendar } from "@/lib/api";
import type { CalendarSnapshot } from "@/lib/types";

export function TodayCalendarPanel() {
  const [snapshot, setSnapshot] = useState<CalendarSnapshot | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      setSnapshot(await getCalendar(refresh));
    } catch {
      /* swallow */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!snapshot) {
    return <div className="muted">{loading ? "Loading calendar…" : "Calendar unavailable."}</div>;
  }

  return (
    <section className="calendar-panel">
      <header>
        <div>
          <CalendarDays size={14} />
          <strong>Today</strong>
        </div>
        <button type="button" className="btn-icon" onClick={() => load(true)} disabled={loading}>
          <RefreshCw size={13} />
        </button>
      </header>
      <div className="calendar-grid">
        <Block title={`Results today (${snapshot.results_today.length})`}>
          {snapshot.results_today.slice(0, 8).map((row, index) => (
            <div key={`${row.symbol}-${index}`} className="calendar-row">
              <strong>{row.symbol}</strong>
              <span className="muted">{row.company}</span>
            </div>
          ))}
          {snapshot.results_today.length === 0 ? <div className="muted">No results today.</div> : null}
        </Block>
        <Block title={`F&O ban (${snapshot.fno_ban.length})`}>
          {snapshot.fno_ban.slice(0, 12).map((row, index) => (
            <span key={`${row.symbol}-${index}`} className="ban-chip">
              {row.symbol}
            </span>
          ))}
          {snapshot.fno_ban.length === 0 ? <div className="muted">None banned.</div> : null}
        </Block>
        <Block title="Corporate actions">
          {snapshot.corporate_actions.slice(0, 6).map((row, index) => (
            <div key={`${row.symbol}-${index}`} className="calendar-row">
              <strong>{row.symbol}</strong>
              <span className="muted">{row.purpose}</span>
              {row.ex_date ? <span className="muted">ex {row.ex_date}</span> : null}
            </div>
          ))}
          {snapshot.corporate_actions.length === 0 ? <div className="muted">None.</div> : null}
        </Block>
      </div>
    </section>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="calendar-block">
      <span className="muted">{title}</span>
      <div className="stack">{children}</div>
    </div>
  );
}
