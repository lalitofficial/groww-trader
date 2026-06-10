export type Timeframe = "5m" | "15m" | "30m" | "hourly" | "daily";

export type ScannerRow = {
  symbol: string;
  groww_symbol: string;
  company: string;
  price: number | null;
  trend_state: string;
  rsi: number | null;
  macd_state: string | null;
  volume_expansion: number | null;
  relative_strength: number | null;
  support: number | null;
  resistance: number | null;
  risk_reward: number | null;
  technical_score: number;
  ai_confidence: number | null;
  catalyst_count: number;
  data_status: string;
  data_source?: string | null;
  data_freshness?: string | null;
  stale_cache_used?: boolean;
  grade?: string | null;
  action?: string | null;
  timeframe?: string;
  vwap_state?: string | null;
  orb_state?: string | null;
  intraday_signal?: string | null;
  intraday_quality?: number | null;
};

export type Candle = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Catalyst = {
  source_type: string;
  title: string;
  url: string;
  published_at?: string;
  summary?: string;
  relevance_score?: number;
};

export type Instrument = {
  exchange: string;
  trading_symbol: string;
  groww_symbol: string;
  name?: string;
  instrument_type?: string;
  segment?: string;
  series?: string;
};

export type IntradayStrategy = {
  id: string;
  name: string;
  direction: "long" | "short";
  active: boolean;
  quality: number;
  trigger: string;
  entry?: number | null;
  stop?: number | null;
};

export type IntradayView = {
  status?: string;
  interval_minutes?: number;
  timeframe_minutes?: number;
  session?: string;
  last_price?: number;
  vwap?: number | null;
  distance_to_vwap_pct?: number | null;
  vwap_state?: string;
  opening_range?: {
    session: string;
    bars: number;
    or_high: number;
    or_low: number;
    range_pct: number | null;
    last_close: number;
    state: string;
  } | null;
  atr?: number | null;
  atr_pct?: number | null;
  ma20?: number | null;
  rsi?: number | null;
  macd_state?: string | null;
  strategies?: IntradayStrategy[];
  primary_signal?: IntradayStrategy | null;
};

export type StockAnalysis = {
  symbol: string;
  company: string;
  daily_candles: Candle[];
  hourly_candles: Candle[];
  intraday_candles?: Candle[];
  intraday_timeframe?: string | null;
  daily_analysis: Record<string, any>;
  hourly_analysis: Record<string, any>;
  intraday_analysis?: Record<string, any> | null;
  intraday_view?: IntradayView | null;
  risk_plan: Record<string, any>;
  catalysts: Catalyst[];
  benchmark: string;
  chart_overlays?: Record<string, ChartOverlays>;
  chart_markers?: Record<string, ChartMarker[]>;
  setup_mode_summary?: Record<string, any>;
  data_source?: Record<string, any>;
  data_freshness?: Record<string, string | null>;
  fallback_chain?: Record<string, Array<Record<string, string>>>;
  stale_cache_used?: boolean;
  errors?: Record<string, string | null>;
  position_context?: AccountPosition | null;
  alerts?: AlertEvent[];
};

export type ChartPoint = { time: number; value: number };

export type ChartMarker = {
  time: number;
  type: string;
  position: "aboveBar" | "belowBar";
  color: string;
  text: string;
};

export type ChartOverlays = {
  ma20?: ChartPoint[];
  ma50?: ChartPoint[];
  ma200?: ChartPoint[];
  vwap?: ChartPoint[];
  supertrend?: ChartPoint[];
  rsi?: ChartPoint[];
  stoch_rsi_k?: ChartPoint[];
  stoch_rsi_d?: ChartPoint[];
  volume_avg20?: ChartPoint[];
  bollinger?: Record<string, ChartPoint[]>;
  keltner?: Record<string, ChartPoint[]>;
  levels?: Array<Record<string, any>>;
  macd_state?: Record<string, any>;
};

export type ChartContext = {
  symbol: string;
  timeframe: Timeframe;
  candles: Candle[];
  overlays: ChartOverlays;
  markers: ChartMarker[];
  panels: string[];
  data_source?: Record<string, any>;
};

export type BacktestResult = {
  symbol: string;
  timeframe: string;
  strategy_id: string;
  strategy_name?: string;
  engine?: string;
  metrics: Record<string, any>;
  trades: Array<Record<string, any>>;
  equity_curve: Array<Record<string, any>>;
  warnings: string[];
};

export type AccountPosition = {
  kind: "position" | "holding";
  symbol: string;
  company?: string;
  quantity?: number | null;
  average_price?: number | null;
  current_price?: number | null;
  day_pnl?: number | null;
  unrealized_pnl?: number | null;
  product?: string | null;
  nearest_support?: number | null;
  nearest_resistance?: number | null;
  distance_to_support_pct?: number | null;
  distance_to_resistance_pct?: number | null;
  risk_reward?: number | null;
};

export type AccountOrder = {
  order_id: string;
  symbol: string;
  status?: string | null;
  transaction_type?: string | null;
  order_type?: string | null;
  product?: string | null;
  quantity?: number | null;
  filled_quantity?: number | null;
  price?: number | null;
  created_at?: string | null;
};

export type AlertEvent = {
  event_key: string;
  symbol: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  trigger_value?: number | null;
  current_value?: number | null;
  related_level?: number | null;
  status?: string;
  created_at?: string;
};

export type AccountSummary = {
  margin: Record<string, any>;
  positions_count: number;
  holdings_count: number;
  orders_count: number;
  errors: string[];
  read_only: boolean;
};

export type Watchlist = {
  id: number;
  name: string;
  kind: "swing" | "intraday";
  symbols: string[];
  updated_at?: string;
};

export type PaperTrade = {
  id: number;
  symbol: string;
  side: "BUY" | "SELL";
  product: "intraday" | "delivery";
  quantity: number;
  entry_price: number;
  stop_loss?: number | null;
  target?: number | null;
  exit_price?: number | null;
  pnl?: number | null;
  fees?: number | null;
  status: "open" | "closed";
  strategy_id?: string | null;
  timeframe?: string | null;
  grade?: string | null;
  notes?: string | null;
  opened_at?: string;
  closed_at?: string | null;
  live_price?: number | null;
  mtm_pnl?: number | null;
  metadata?: Record<string, any>;
};

export type PaperSummary = {
  total_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number | null;
  total_fees: number;
  expectancy: number;
};

export type FundamentalsSnapshot = {
  symbol: string;
  url: string | null;
  ratios: Record<string, string>;
  snapshot: {
    market_cap?: string | null;
    current_price?: number | null;
    high_low?: string | null;
    pe_ratio?: number | null;
    book_value?: number | null;
    dividend_yield?: number | null;
    roce?: number | null;
    roe?: number | null;
    face_value?: number | null;
    industry_pe?: number | null;
    debt_to_equity?: number | null;
    promoter_holding?: number | null;
  };
};

export type BreadthRow = {
  symbol: string;
  ltp: number | null;
  change_pct: number | null;
  change_abs: number | null;
  volume: number | null;
  value: number | null;
};

export type BreadthSnapshot = {
  gainers: BreadthRow[];
  losers: BreadthRow[];
  mostActive: BreadthRow[];
};

export type OptionChainStrike = {
  strike: number;
  ce_oi: number;
  ce_oi_change: number | null;
  ce_iv: number | null;
  ce_ltp: number | null;
  pe_oi: number;
  pe_oi_change: number | null;
  pe_iv: number | null;
  pe_ltp: number | null;
};

export type OptionChain = {
  symbol: string;
  underlying: number;
  strikes: OptionChainStrike[];
  summary: {
    total_ce_oi: number;
    total_pe_oi: number;
    pcr: number | null;
    max_ce_oi_strike: number;
    max_pe_oi_strike: number;
  };
};

export type StrategyMetricsRow = {
  strategy_id: string;
  name: string;
  author: string | null;
  source_url: string | null;
  tags: string[];
  sample_size: number;
  win_rate: number | null;
  total_return_pct: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number | null;
  expectancy: number | null;
  sharpe: number | null;
};

export type StrategySpecSummary = {
  id: string;
  name: string;
  author?: string;
  source_url?: string | null;
  description?: string | null;
  timeframes: string[];
  direction: string;
  tags?: string[];
  kind?: "builtin" | "user";
  enabled?: boolean;
  spec?: Record<string, any>;
  updated_at?: string;
};

export type RequestBudget = {
  window_seconds: number;
  total: number;
  by_provider: Record<string, Record<string, number>>;
  token_usage?: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }>;
  last_event_at: number | null;
};

export type AiStatus = {
  allowed: boolean;
  reason: "ok" | "disabled_by_user" | "no_heartbeat" | "circuit_open";
  ai_enabled: boolean;
  commentary_enabled: boolean;
  commentary_cadence_seconds: number;
  require_heartbeat: boolean;
  heartbeat_grace_seconds: number;
  last_heartbeat_at: number;
  seconds_since_heartbeat: number | null;
  circuit_open_until: number;
  consecutive_failures: number;
  event_triggers: Record<string, boolean>;
};

export type AiSettings = {
  ai_enabled: boolean;
  commentary_enabled: boolean;
  commentary_cadence_seconds: number;
  event_triggers: Record<string, boolean>;
  require_heartbeat: boolean;
  heartbeat_grace_seconds: number;
  last_heartbeat_at: number;
  circuit_open_until: number;
  consecutive_failures: number;
  updated_at?: string;
};

export type TradingSession = {
  id: number;
  session_date: string;
  status: "open" | "closed";
  macro_snapshot: Record<string, any>;
  shortlist: Array<{
    symbol: string;
    reason?: string;
    factors?: Record<string, any>;
    added_at?: string;
  }>;
  picks: Array<{
    symbol: string;
    direction: "long" | "short";
    plan?: Record<string, any>;
    sized_qty?: number | null;
    notes?: string;
    added_at?: string;
  }>;
  notes: string;
  created_at?: string;
  updated_at?: string;
};

export type SessionEvent = {
  id: number;
  session_date: string;
  symbol: string | null;
  kind: string;
  payload: Record<string, any>;
  at: string;
};

export type FactorSubscore = {
  long: number;
  short: number;
  raw?: any;
  label?: string;
};

export type FactorSnapshot = {
  symbol: string;
  timeframe: string;
  computed_at: number | null;
  weights: Record<string, number>;
  subscores: Record<string, FactorSubscore>;
  long_score: number;
  short_score: number;
  bias: "long" | "short" | "neutral";
  gating: { liquidity_ok: boolean; price_ok: boolean; fno_ban: boolean; results_today: boolean };
  rationale: { top_positive: string[]; top_negative: string[]; patterns: string[]; sentiment_label: string };
  snapshot_inputs: {
    last_price?: number;
    trend_state?: string;
    rsi?: number;
    macd_state?: string;
    support?: number;
    resistance?: number;
    risk_reward?: number;
    atr_pct?: number;
    sentiment_label?: string;
    sentiment_score?: number;
  };
  error?: string;
};

export type GlobalCue = {
  symbol: string;
  label: string;
  group: string;
  last?: number;
  previous?: number;
  change?: number;
  change_pct?: number;
  currency?: string;
  error?: string;
};

export type CalendarSnapshot = {
  as_of: string;
  fno_ban: Array<{ symbol: string; status: string }>;
  results_today: Array<{ symbol: string; company?: string; broadcast_at?: string; period?: string }>;
  corporate_actions: Array<{ symbol: string; purpose?: string; ex_date?: string; record_date?: string }>;
};

export type LiveQuoteEvent = {
  symbol: string;
  ltp: number;
  change_pct: number;
  open?: number;
  high?: number;
  low?: number;
  vwap?: number;
  ts: number;
};

export type LiveDepthEvent = {
  symbol: string;
  bids: Array<{ price: number; qty: number }>;
  asks: Array<{ price: number; qty: number }>;
  total_bid_qty: number;
  total_ask_qty: number;
  imbalance: number | null;
};

export type LiveSignalEvent = {
  symbol: string;
  kind: string;
  payload: Record<string, any>;
  at: number;
};

export type RegimeSnapshot = {
  benchmark: Record<string, any>;
  sectors: Array<Record<string, any>>;
  sector_breadth: {
    advancing: number;
    declining: number;
    neutral: number;
    advance_decline_ratio: number | null;
    total: number;
  };
  watchlist_breadth: {
    advancing: number;
    declining: number;
    neutral: number;
    advance_decline_ratio: number | null;
    total: number;
  };
  trade_mode: {
    bias: string;
    intraday_long_bias: boolean;
    intraday_short_bias: boolean;
    reason: string;
  };
};
