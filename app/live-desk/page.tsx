"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AiCommentaryStream } from "@/components/AiCommentaryStream";
import { EventFeed } from "@/components/EventFeed";
import { Header } from "@/components/Header";
import { LiveDeskRoster } from "@/components/LiveDeskRoster";
import { MarketDepthLadder } from "@/components/MarketDepthLadder";
import { RegimeStrip } from "@/components/RegimeStrip";
import { TradingViewPanel } from "@/components/TradingViewPanel";
import { useLiveStream } from "@/hooks/useLiveStream";
import { getCurrentSession, setLiveFocus } from "@/lib/api";
import type { TradingSession } from "@/lib/types";

export default function LiveDeskPage() {
  const [session, setSession] = useState<TradingSession | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const stream = useLiveStream(true);

  const loadSession = useCallback(async () => {
    try {
      setSession(await getCurrentSession());
    } catch {
      /* swallow */
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  useEffect(() => {
    if (session?.picks?.length && !focused) {
      setFocused(session.picks[0].symbol);
    }
  }, [session, focused]);

  useEffect(() => {
    if (focused) {
      void setLiveFocus(focused).catch(() => null);
    }
  }, [focused]);

  const focusedDepth = focused ? stream.depth[focused] : undefined;
  const focusedSignals = useMemo(
    () => (focused ? stream.signals.filter((event) => event.symbol === focused) : stream.signals),
    [stream.signals, focused],
  );

  return (
    <main className="shell">
      <Header subtitle="Live Desk — execution cockpit" />
      <div className="content stack-lg live-desk">
        <RegimeStrip />
        {stream.degraded ? <div className="context-badge warning">{stream.degraded}</div> : null}
        {!stream.connected ? <div className="context-badge">Connecting to live stream…</div> : null}
        <LiveDeskRoster session={session} quotes={stream.quotes} focused={focused} onFocus={setFocused} />
        <div className="live-desk-grid">
          <div className="live-desk-chart">
            {focused ? <TradingViewPanel symbol={focused} timeframe="15m" /> : <div className="muted">Pick a symbol above.</div>}
          </div>
          <div className="live-desk-side">
            <MarketDepthLadder depth={focusedDepth} />
            <AiCommentaryStream symbol={focused} />
          </div>
        </div>
        <EventFeed events={focusedSignals} />
      </div>
    </main>
  );
}
