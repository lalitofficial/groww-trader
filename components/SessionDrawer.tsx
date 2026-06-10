"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { closeSession, getCurrentSession, getSessionEvents } from "@/lib/api";
import type { SessionEvent, TradingSession } from "@/lib/types";

export function SessionDrawer({ onClose }: { onClose: () => void }) {
  const [session, setSession] = useState<TradingSession | null>(null);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [current, eventList] = await Promise.all([
        getCurrentSession(),
        getSessionEvents({ limit: 100 }),
      ]);
      setSession(current);
      setEvents(eventList.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function close() {
    if (!confirm("Close today's trading session?")) return;
    await closeSession();
    await load();
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <header className="drawer-header">
          <div>
            <strong>Session</strong>
            <div className="muted">{session?.session_date} · {session?.status}</div>
          </div>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={14} />
          </button>
        </header>
        <div className="drawer-body stack">
          {loading ? <div className="muted">Loading…</div> : null}
          <section className="drawer-section">
            <strong>Shortlist · {session?.shortlist?.length ?? 0}</strong>
            <div className="shortlist-chips">
              {(session?.shortlist || []).map((item) => (
                <span key={item.symbol} className="watchlist-chip">
                  {item.symbol}
                </span>
              ))}
              {(session?.shortlist || []).length === 0 ? <span className="muted">Empty</span> : null}
            </div>
          </section>
          <section className="drawer-section">
            <strong>Picks · {session?.picks?.length ?? 0}</strong>
            <div className="picks-chips">
              {(session?.picks || []).map((pick) => (
                <span key={pick.symbol} className={`pick-chip pick-${pick.direction}`}>
                  <strong>{pick.symbol}</strong>
                  <span>{pick.direction}</span>
                </span>
              ))}
              {(session?.picks || []).length === 0 ? <span className="muted">No picks committed.</span> : null}
            </div>
          </section>
          <section className="drawer-section">
            <strong>Recent events ({events.length})</strong>
            <ul className="session-event-list">
              {events.slice(-30).reverse().map((event) => (
                <li key={event.id}>
                  <strong>{event.kind}</strong>
                  <span className="muted">{event.symbol || "—"}</span>
                  <span className="muted">{event.at}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
        <footer className="drawer-footer">
          <button type="button" className="btn btn-secondary" onClick={close}>
            Close session
          </button>
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </footer>
      </aside>
    </div>
  );
}
