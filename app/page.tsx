import { BreadthPanel } from "@/components/BreadthPanel";
import { Header } from "@/components/Header";
import { PaperTradeLedger } from "@/components/PaperTradeLedger";
import { RegimeStrip } from "@/components/RegimeStrip";
import { RequestBudgetTile } from "@/components/RequestBudgetTile";
import { ScannerTable } from "@/components/ScannerTable";
import { StrategyLab } from "@/components/StrategyLab";
import { SymbolSelector } from "@/components/SymbolSelector";
import { WatchlistManager } from "@/components/WatchlistManager";
import { getScanner } from "@/lib/api";
import type { ScannerRow, Timeframe } from "@/lib/types";

const VALID: Timeframe[] = ["5m", "15m", "30m", "hourly", "daily"];

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ universe?: string; refresh?: string; symbols?: string; timeframe?: string }>;
}) {
  const params = await searchParams;
  const symbols = params.symbols || "";
  const timeframe = VALID.includes((params.timeframe || "") as Timeframe) ? (params.timeframe as Timeframe) : "15m";
  const universe = params.universe === "nifty50" ? "nifty50" : "watchlist";
  let rows: ScannerRow[] = [];
  let error = "";
  try {
    rows = await getScanner({
      limit: 50,
      universe,
      symbols: symbols || undefined,
      timeframe,
      refresh: params.refresh === "true",
    });
  } catch (exc) {
    error = exc instanceof Error ? exc.message : "Unable to load scanner.";
  }

  return (
    <main className="shell">
      <Header />
      <div className="content stack-lg">
        <RegimeStrip />
        <RequestBudgetTile />
        <section className="page-hero">
          <div>
            <span className="eyebrow">Intraday + Swing trading terminal</span>
            <h1>Pick a stock. Get a complete plan.</h1>
            <p>
              Multi-timeframe scanner (5m / 15m / 30m / hourly / daily), VWAP &amp; opening-range intraday triggers, ATR-based stops,
              paper trade ledger, and an AI analyst grounded in deterministic indicators.
            </p>
          </div>
          <SymbolSelector initialSymbols={symbols} />
        </section>
        <section className="scanner-toolbar">
          <div className="scanner-toolbar-tabs">
            <ScannerLink label="Watchlist" current={universe} target="watchlist" symbols={symbols} timeframe={timeframe} />
            <ScannerLink label="Nifty 50" current={universe} target="nifty50" symbols={symbols} timeframe={timeframe} />
          </div>
          <div className="scanner-toolbar-tfs">
            {VALID.map((tf) => (
              <a
                key={tf}
                className={tf === timeframe ? "tf-pill active" : "tf-pill"}
                href={`/?${new URLSearchParams({
                  ...(symbols ? { symbols } : {}),
                  universe,
                  timeframe: tf,
                }).toString()}`}
              >
                {tf}
              </a>
            ))}
          </div>
        </section>
        {error ? (
          <section className="panel">
            <div className="panel-body">
              <strong>Scanner unavailable</strong>
              <p className="muted">Start the backend with <code>groww-trader dashboard --api-only</code> or <code>uvicorn groww_trader.api.app:app --reload</code>.</p>
              <p>{error}</p>
            </div>
          </section>
        ) : (
          <ScannerTable rows={rows} timeframe={timeframe} />
        )}
        <div className="home-grid">
          <WatchlistManager />
          <PaperTradeLedger />
        </div>
        <BreadthPanel />
        <StrategyLab defaultSymbol={(symbols && symbols.split(/[,\s]+/)[0]) || "RELIANCE"} defaultTimeframe={timeframe} />
      </div>
    </main>
  );
}

function ScannerLink({
  label,
  current,
  target,
  symbols,
  timeframe,
}: {
  label: string;
  current: string;
  target: string;
  symbols: string;
  timeframe: string;
}) {
  const params = new URLSearchParams({ universe: target, timeframe });
  if (symbols) params.set("symbols", symbols);
  return (
    <a className={current === target ? "tf-pill active" : "tf-pill"} href={`/?${params.toString()}`}>
      {label}
    </a>
  );
}
