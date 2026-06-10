"use client";

import { Filter, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GlobalCuesStrip } from "@/components/GlobalCuesStrip";
import { Header } from "@/components/Header";
import { NarrowComparisonGrid } from "@/components/NarrowComparisonGrid";
import { OpenDeskShortlistTable } from "@/components/OpenDeskShortlistTable";
import { PicksTray } from "@/components/PicksTray";
import { RegimeStrip } from "@/components/RegimeStrip";
import { ScanProgress } from "@/components/ScanProgress";
import { TodayCalendarPanel } from "@/components/TodayCalendarPanel";
import {
  addShortlist,
  clearShortlist,
  getCurrentSession,
  removeShortlist,
} from "@/lib/api";
import { runFactorScan, type FactorScanHandle, type FactorScanProgress } from "@/lib/factor-stream";
import type { FactorSnapshot, TradingSession } from "@/lib/types";

// Universes (the AppSettings server-side has the full Nifty 100 default). We hardcode a
// compact list here for the browser-side picker so we don't bake the full universe into the
// client bundle. Each maps to a server-provided list; "watchlist" pulls live from session.
const UNIVERSE_SAMPLES: Record<string, string[]> = {
  "nifty100": [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "SBIN",
    "BHARTIARTL", "BAJFINANCE", "KOTAKBANK", "LT", "AXISBANK", "MARUTI", "ASIANPAINT",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "BAJAJFINSV", "WIPRO", "NESTLEIND", "ONGC",
    "POWERGRID", "NTPC", "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "HCLTECH", "TECHM",
    "M&M", "ADANIENT", "ADANIPORTS", "GRASIM", "CIPLA", "DRREDDY", "DIVISLAB",
    "BRITANNIA", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "COALINDIA", "BPCL", "IOC",
    "TATACONSUM", "INDUSINDBK", "HDFCLIFE", "SBILIFE", "APOLLOHOSP", "UPL", "HINDALCO",
  ],
  "watchlist": [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "LT", "AXISBANK", "ITC", "BHARTIARTL",
  ],
  "banks": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "AUBANK", "BANKBARODA", "PNB", "FEDERALBNK"],
  "it": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "PERSISTENT", "COFORGE", "MPHASIS"],
  "auto": ["MARUTI", "TATAMOTORS", "M&M", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "TVSMOTOR"],
};

export default function OpenDeskPage() {
  const [session, setSession] = useState<TradingSession | null>(null);
  const [factors, setFactors] = useState<Record<string, FactorSnapshot>>({});
  const [direction, setDirection] = useState<"long" | "short" | "both">("both");
  const [minScore, setMinScore] = useState(55);
  const [universe, setUniverse] = useState<keyof typeof UNIVERSE_SAMPLES>("nifty100");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [picks, setPicks] = useState<Array<{ symbol: string; direction: "long" | "short" }>>([]);
  const [scanProgress, setScanProgress] = useState<FactorScanProgress | null>(null);
  const scanHandleRef = useRef<FactorScanHandle | null>(null);

  useEffect(() => () => scanHandleRef.current?.cancel(), []);

  const refreshSession = useCallback(async () => {
    try {
      setSession(await getCurrentSession());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Session unavailable");
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  function cancelScan() {
    scanHandleRef.current?.cancel();
    scanHandleRef.current = null;
    setLoading(false);
  }

  async function scan() {
    if (scanHandleRef.current) {
      scanHandleRef.current.cancel();
      scanHandleRef.current = null;
    }
    setError("");
    setFactors({});
    setLoading(true);
    const symbols = UNIVERSE_SAMPLES[universe];
    setScanProgress({
      done: 0,
      total: symbols.length,
      succeeded: 0,
      failed: 0,
      in_flight: [],
      errors: [],
      elapsed_ms: 0,
      eta_ms: null,
      finished: false,
    });
    const handle = runFactorScan(symbols, {
      timeframe: "daily",
      concurrency: 6,
      onProgress: (progress) => setScanProgress(progress),
      onRow: (row) => setFactors((current) => ({ ...current, [row.symbol]: row })),
    });
    scanHandleRef.current = handle;
    try {
      await handle.promise;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Scan failed");
    } finally {
      if (scanHandleRef.current === handle) {
        scanHandleRef.current = null;
      }
      setLoading(false);
    }
  }

  async function addToShortlist(symbol: string) {
    await addShortlist({ symbol });
    await refreshSession();
  }

  async function removeFromShortlist(symbol: string) {
    await removeShortlist(symbol);
    await refreshSession();
  }

  async function clearAllShortlist() {
    if (!confirm("Clear today's shortlist?")) return;
    await clearShortlist();
    await refreshSession();
  }

  function promotePick(symbol: string, dir: "long" | "short") {
    setPicks((current) => {
      if (current.some((pick) => pick.symbol === symbol)) return current;
      return [...current, { symbol, direction: dir }];
    });
  }

  const promotedSet = useMemo(() => new Set(picks.map((pick) => pick.symbol)), [picks]);

  const rows = Object.values(factors);

  return (
    <main className="shell">
      <Header subtitle="Open Desk — premarket discovery" />
      <div className="content stack-lg">
        <RegimeStrip />
        <GlobalCuesStrip />
        <TodayCalendarPanel />

        <section className="panel">
          <div className="panel-header">
            <div>
              <strong>Stage B · Shortlist scan</strong>
              <div className="muted">Pick universe → run factor pipeline → add stocks to today&apos;s shortlist.</div>
            </div>
            <div className="panel-actions">
              <select className="input" value={universe} onChange={(event) => setUniverse(event.target.value as any)}>
                <option value="nifty100">Nifty 100</option>
                <option value="watchlist">My Watchlist</option>
                <option value="banks">Banks</option>
                <option value="it">IT</option>
                <option value="auto">Auto</option>
              </select>
              <select className="input" value={direction} onChange={(event) => setDirection(event.target.value as any)}>
                <option value="both">Long + Short</option>
                <option value="long">Long only</option>
                <option value="short">Short only</option>
              </select>
              <label className="filter-label">
                <Filter size={12} /> ≥
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(event) => setMinScore(Number(event.target.value))}
                  className="input"
                  style={{ width: 60 }}
                />
              </label>
              <button type="button" className="btn btn-primary" onClick={scan} disabled={loading}>
                <RefreshCw size={13} />
                {loading ? "Scanning…" : "Scan universe"}
              </button>
            </div>
          </div>
          <div className="panel-body stack">
            {error ? <div className="context-badge warning">{error}</div> : null}
            <ScanProgress progress={scanProgress} onCancel={loading ? cancelScan : undefined} />
            <OpenDeskShortlistTable
              rows={rows}
              session={session}
              onAdd={addToShortlist}
              onRemove={removeFromShortlist}
              direction={direction === "both" ? "long" : direction}
              minScore={minScore}
            />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <strong>Today&apos;s shortlist ({session?.shortlist?.length ?? 0})</strong>
              <div className="muted">Promote candidates into the picks tray below.</div>
            </div>
            <div className="panel-actions">
              <button type="button" className="btn btn-secondary" onClick={clearAllShortlist}>
                <Trash2 size={13} />
                Clear
              </button>
            </div>
          </div>
          <div className="panel-body stack">
            <div className="shortlist-chips">
              {(session?.shortlist || []).map((item) => (
                <span key={item.symbol} className="watchlist-chip">
                  {item.symbol}
                </span>
              ))}
              {(session?.shortlist || []).length === 0 ? <span className="muted">Empty</span> : null}
            </div>
            <NarrowComparisonGrid session={session} factors={factors} onPromote={promotePick} promoted={promotedSet} />
          </div>
        </section>

        <PicksTray picks={picks} setPicks={setPicks} />
      </div>
    </main>
  );
}
