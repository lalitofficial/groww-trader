"use client";

import { Bell } from "lucide-react";
import type { LiveSignalEvent } from "@/lib/types";

const EVENT_TONE: Record<string, string> = {
  near_stop: "tone-red",
  near_target: "tone-amber",
  level_break_up: "tone-green",
  level_break_down: "tone-red",
  vol_spike: "tone-blue",
  supertrend_flip: "tone-amber",
  vwap_cross_up: "tone-green",
  vwap_cross_down: "tone-red",
  orb_break_up: "tone-green",
  orb_break_down: "tone-red",
  rsi_extreme: "tone-amber",
  pnl_milestone: "tone-blue",
  daily_loss_threshold: "tone-red",
};

export function EventFeed({ events }: { events: LiveSignalEvent[] }) {
  return (
    <section className="panel event-feed">
      <div className="panel-header">
        <div>
          <Bell size={13} />
          <strong>Event feed</strong>
        </div>
        <span className="muted">{events.length} events</span>
      </div>
      <div className="panel-body">
        {events.length === 0 ? <div className="muted">No events yet.</div> : null}
        <ul>
          {events.slice(0, 20).map((event) => (
            <li key={`${event.symbol}-${event.kind}-${event.at}`} className={EVENT_TONE[event.kind] || "tone-default"}>
              <strong>{event.symbol}</strong>
              <span>{event.kind.replace(/_/g, " ")}</span>
              <span className="muted">{describe(event.payload)}</span>
              <span className="muted event-time">{relative(event.at)}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function describe(payload: Record<string, any>): string {
  if (!payload) return "";
  if (typeof payload.price === "number") return `@ ${payload.price.toFixed(2)}`;
  if (typeof payload.ratio === "number") return `${payload.ratio.toFixed(2)}x avg`;
  if (typeof payload.r_multiple === "number") return `${payload.r_multiple.toFixed(2)}R`;
  return "";
}

function relative(at: number) {
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - at));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}
