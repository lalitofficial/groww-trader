import type {
  AccountOrder,
  AccountPosition,
  AccountSummary,
  AiSettings,
  AiStatus,
  AlertEvent,
  BacktestResult,
  BreadthSnapshot,
  CalendarSnapshot,
  ChartContext,
  FactorSnapshot,
  FundamentalsSnapshot,
  GlobalCue,
  Instrument,
  OptionChain,
  PaperSummary,
  PaperTrade,
  RegimeSnapshot,
  RequestBudget,
  ScannerRow,
  SessionEvent,
  StockAnalysis,
  StrategyMetricsRow,
  StrategySpecSummary,
  Timeframe,
  TradingSession,
  Watchlist,
} from "./types";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function getScanner(params: { limit?: number; refresh?: boolean; universe?: string; symbols?: string; timeframe?: Timeframe } = {}) {
  const query = new URLSearchParams({
    limit: String(params.limit ?? 25),
    refresh: String(params.refresh ?? false),
    universe: params.universe ?? "watchlist",
    timeframe: params.timeframe ?? "daily",
  });
  if (params.symbols) query.set("symbols", params.symbols);
  const data = await fetchJson<{ items: ScannerRow[] }>(`${backendUrl}/api/scanner?${query.toString()}`);
  return data.items;
}

export async function getStockAnalysis(symbol: string, options: { refresh?: boolean; timeframe?: Timeframe } = {}) {
  const query = new URLSearchParams({
    refresh: String(options.refresh ?? false),
    timeframe: options.timeframe ?? "daily",
  });
  return fetchJson<StockAnalysis>(`${backendUrl}/api/stocks/${encodeURIComponent(symbol)}/analysis?${query.toString()}`);
}

export async function getChartContext(symbol: string, timeframe: Timeframe = "daily", refresh = false) {
  return fetchJson<ChartContext>(
    `${backendUrl}/api/stocks/${encodeURIComponent(symbol)}/chart-context?timeframe=${timeframe}&refresh=${refresh}`,
  );
}

export async function getStockQuote(symbol: string) {
  return fetchJson<{ symbol: string; ltp: number; open: number; high: number; low: number; volume: number; provider: string; freshness: string; timestamp: number }>(
    `${backendUrl}/api/stocks/${encodeURIComponent(symbol)}/quote`,
  );
}

export async function runBacktest(
  symbol: string,
  payload: { strategy_id: string; timeframe?: Timeframe; params?: Record<string, any>; refresh?: boolean },
) {
  return fetchJson<BacktestResult>(`${backendUrl}/api/stocks/${encodeURIComponent(symbol)}/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function searchInstruments(search: string, limit = 12) {
  const query = new URLSearchParams({ search, limit: String(limit) });
  return fetchJson<{ items: Instrument[]; count: number }>(`${backendUrl}/api/instruments?${query.toString()}`);
}

export async function getRegime(refresh = false) {
  return fetchJson<RegimeSnapshot>(`${backendUrl}/api/regime?refresh=${refresh}`);
}

export async function getAccountSummary() {
  return fetchJson<AccountSummary>(`${backendUrl}/api/account/summary`);
}

export async function getAccountPositions() {
  return fetchJson<{ items: AccountPosition[]; count: number; error?: string }>(`${backendUrl}/api/account/positions`);
}

export async function getAccountHoldings() {
  return fetchJson<{ items: AccountPosition[]; count: number; error?: string }>(`${backendUrl}/api/account/holdings`);
}

export async function getAccountOrders() {
  return fetchJson<{ items: AccountOrder[]; count: number; error?: string }>(`${backendUrl}/api/account/orders`);
}

export async function getAccountAlerts(symbol?: string) {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return fetchJson<{ items: AlertEvent[]; count: number }>(`${backendUrl}/api/account/alerts${query}`);
}

export async function evaluateAccountAlerts(symbol?: string, deliver = false) {
  const query = new URLSearchParams();
  if (symbol) query.set("symbol", symbol);
  query.set("deliver", String(deliver));
  return fetchJson<{ items: AlertEvent[]; count: number; delivery?: any }>(
    `${backendUrl}/api/account/alerts/evaluate?${query.toString()}`,
    { method: "POST" },
  );
}

export async function deliverAlerts(symbol?: string) {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return fetchJson<{ channels: Record<string, any>; delivered: number }>(`${backendUrl}/api/alerts/deliver${query}`, { method: "POST" });
}

export async function getWatchlists() {
  return fetchJson<{ items: Watchlist[] }>(`${backendUrl}/api/watchlists`);
}

export async function saveWatchlist(payload: { name: string; kind: string; symbols: string[] }) {
  return fetchJson<{ item: Watchlist }>(`${backendUrl}/api/watchlists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteWatchlist(name: string) {
  return fetchJson<{ deleted: boolean }>(`${backendUrl}/api/watchlists/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export async function getPaperTrades(params: { status?: "open" | "closed"; symbol?: string; limit?: number } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.symbol) query.set("symbol", params.symbol);
  if (params.limit) query.set("limit", String(params.limit));
  return fetchJson<{ items: PaperTrade[]; count: number }>(`${backendUrl}/api/paper/trades?${query.toString()}`);
}

export async function getPaperSummary() {
  return fetchJson<PaperSummary>(`${backendUrl}/api/paper/summary`);
}

export async function openPaperTrade(payload: {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  entry_price: number;
  product?: "intraday" | "delivery";
  stop_loss?: number | null;
  target?: number | null;
  strategy_id?: string;
  timeframe?: string;
  grade?: string;
  notes?: string;
}) {
  return fetchJson<PaperTrade>(`${backendUrl}/api/paper/trades`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function closePaperTrade(tradeId: number, payload: { exit_price: number; notes?: string }) {
  return fetchJson<PaperTrade>(`${backendUrl}/api/paper/trades/${tradeId}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function autoOpenPaperTrade(payload: { symbol: string; timeframe?: Timeframe }) {
  return fetchJson<{ opened: PaperTrade | null; reason?: string }>(`${backendUrl}/api/paper/auto-open`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// -------- Public sources (NSE / Google / Screener) --------

export async function getRequestBudget() {
  return fetchJson<RequestBudget>(`${backendUrl}/api/sources/budget`);
}

export async function getMarketBreadth() {
  return fetchJson<BreadthSnapshot>(`${backendUrl}/api/sources/breadth`);
}

export async function getFiiDii() {
  return fetchJson<{ items: Array<Record<string, any>> }>(`${backendUrl}/api/sources/fii-dii`);
}

export async function getFundamentals(symbol: string) {
  return fetchJson<FundamentalsSnapshot>(`${backendUrl}/api/sources/fundamentals/${encodeURIComponent(symbol)}`);
}

export async function getPublicQuote(symbol: string) {
  return fetchJson<Record<string, any>>(`${backendUrl}/api/sources/quote/${encodeURIComponent(symbol)}`);
}

export async function getOptionChain(symbol: string) {
  return fetchJson<OptionChain>(`${backendUrl}/api/sources/option-chain/${encodeURIComponent(symbol)}`);
}

export async function getCorporateAnnouncements(symbol?: string) {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return fetchJson<{ items: Array<Record<string, any>> }>(`${backendUrl}/api/sources/announcements${query}`);
}

// -------- Strategy Lab --------

export async function listStrategies() {
  return fetchJson<{ items: StrategySpecSummary[]; count: number }>(`${backendUrl}/api/strategies`);
}

export async function importStrategy(payload: { url?: string; spec?: Record<string, any> }) {
  return fetchJson<{ item: StrategySpecSummary }>(`${backendUrl}/api/strategies/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteStrategy(strategyId: string) {
  return fetchJson<{ deleted: boolean }>(`${backendUrl}/api/strategies/${encodeURIComponent(strategyId)}`, { method: "DELETE" });
}

export async function runStrategy(strategyId: string, payload: { symbol: string; timeframe?: Timeframe; refresh?: boolean }) {
  return fetchJson<BacktestResult & { source_url?: string }>(`${backendUrl}/api/strategies/${encodeURIComponent(strategyId)}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function benchStrategies(payload: { symbol: string; timeframe?: Timeframe; strategy_ids?: string[]; refresh?: boolean }) {
  return fetchJson<{ symbol: string; timeframe: string; results: StrategyMetricsRow[] }>(`${backendUrl}/api/strategies/bench`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// -------- Trading session --------

export async function getCurrentSession() {
  return fetchJson<TradingSession>(`${backendUrl}/api/session`);
}

export async function addShortlist(payload: { symbol: string; reason?: string; factors?: Record<string, any> }) {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/shortlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function removeShortlist(symbol: string) {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/shortlist/${encodeURIComponent(symbol)}`, { method: "DELETE" });
}

export async function clearShortlist() {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/shortlist`, { method: "DELETE" });
}

export async function setSessionPicks(picks: Array<{ symbol: string; direction?: "long" | "short"; plan?: Record<string, any>; sized_qty?: number; notes?: string }>) {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/picks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ picks }),
  });
}

export async function removeSessionPick(symbol: string) {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/picks/${encodeURIComponent(symbol)}`, { method: "DELETE" });
}

export async function recordSessionEvent(payload: { kind: string; symbol?: string; payload?: Record<string, any> }) {
  return fetchJson<SessionEvent>(`${backendUrl}/api/session/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getSessionEvents(params: { since_id?: number; limit?: number; kinds?: string[] } = {}) {
  const query = new URLSearchParams();
  if (params.since_id) query.set("since_id", String(params.since_id));
  if (params.limit) query.set("limit", String(params.limit));
  if (params.kinds && params.kinds.length) query.set("kinds", params.kinds.join(","));
  return fetchJson<{ items: SessionEvent[]; count: number; next_since_id: number }>(
    `${backendUrl}/api/session/events?${query.toString()}`,
  );
}

export async function closeSession() {
  return fetchJson<TradingSession>(`${backendUrl}/api/session/close`, { method: "POST" });
}

// -------- AI governance --------

export async function getAiStatus() {
  return fetchJson<AiStatus>(`${backendUrl}/api/ai/status`);
}

export async function getAiSettings() {
  return fetchJson<AiSettings>(`${backendUrl}/api/ai/settings`);
}

export async function updateAiSettings(payload: Partial<AiSettings>) {
  return fetchJson<AiSettings>(`${backendUrl}/api/ai/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function sendAiHeartbeat() {
  return fetchJson<AiStatus>(`${backendUrl}/api/ai/heartbeat`, { method: "POST" });
}

export async function enableAi() {
  return fetchJson<AiStatus>(`${backendUrl}/api/ai/enable`, { method: "POST" });
}

export async function disableAi() {
  return fetchJson<AiStatus>(`${backendUrl}/api/ai/disable`, { method: "POST" });
}

// -------- Factor pipeline --------

export async function getFactorSnapshot(symbol: string, timeframe: Timeframe = "daily", refresh = false) {
  const query = new URLSearchParams({ timeframe, refresh: String(refresh) });
  return fetchJson<FactorSnapshot>(`${backendUrl}/api/factors/${encodeURIComponent(symbol)}?${query.toString()}`);
}

export async function getFactorBatch(payload: { symbols: string[]; timeframe?: Timeframe; refresh?: boolean }) {
  return fetchJson<{ items: FactorSnapshot[]; count: number }>(`${backendUrl}/api/factors/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// -------- Global cues + Calendar --------

export async function getGlobalCues(refresh = false) {
  return fetchJson<{ as_of: number; items: GlobalCue[]; by_group: Record<string, GlobalCue[]> }>(
    `${backendUrl}/api/sources/global-cues?refresh=${refresh}`,
  );
}

export async function getCalendar(refresh = false) {
  return fetchJson<CalendarSnapshot>(`${backendUrl}/api/sources/calendar?refresh=${refresh}`);
}

// -------- AI commentary --------

export async function fireCommentaryManual(payload: { symbol: string; paper_trade?: any }) {
  return fetchJson<any>(`${backendUrl}/api/ai/commentary/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fireCommentaryEvent(payload: { symbol: string; kind: string; payload?: any; paper_trade?: any }) {
  return fetchJson<any>(`${backendUrl}/api/ai/commentary/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// -------- Shortlist ranker --------

export async function rankShortlist(payload: { symbols: string[]; timeframe?: Timeframe }) {
  return fetchJson<{ ranking: Array<{ symbol: string; long_score?: number; short_score?: number; bias?: string; reason?: string }>; fallback?: boolean; reason?: string }>(
    `${backendUrl}/api/ai/shortlist-ranker`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

// -------- Live focus --------

export async function setLiveFocus(symbol: string | null) {
  return fetchJson<{ focused: string | null }>(`${backendUrl}/api/live/focus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
}

export function liveStreamUrl() {
  return `${backendUrl}/api/live/stream`;
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
