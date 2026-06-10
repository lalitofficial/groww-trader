from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from groww_trader.settings import AppSettings

from .calendar import CalendarService
from .catalysts import CatalystService
from .indicators import analyze_candles, normalize_candles
from .intraday import intraday_analysis
from .market_data import MarketDataRouter
from .patterns import detect_patterns
from .public_data import PublicDataService
from .regime import RegimeService
from .scanner import resolve_timeframe
from .sentiment import SentimentService
from .strategies import BUILTIN_STRATEGIES, run_strategy


# Weights agreed in the locked plan (sum = 100).
FACTOR_WEIGHTS: dict[str, int] = {
    "technical": 18,
    "intraday_signal": 14,
    "sentiment": 18,
    "volume_volatility": 12,
    "quant": 10,
    "regime_fit": 10,
    "event_proximity": 6,
    "liquidity": 6,
    "pattern": 6,
}


class FactorPipeline:
    """Builds a directional FactorSnapshot per symbol.

    Each subscore is computed twice — once interpreting the data as a long
    thesis, once as a short thesis. The final pick_score is direction-aware
    with a bias hint and a small set of gating booleans that the Open Desk
    table uses for filtering.
    """

    def __init__(
        self,
        market_data: MarketDataRouter,
        public_data: PublicDataService,
        catalysts: CatalystService,
        regime: RegimeService,
        sentiment: SentimentService,
        calendar: CalendarService,
        settings: AppSettings,
        weights: dict[str, int] | None = None,
    ) -> None:
        self.market_data = market_data
        self.public_data = public_data
        self.catalysts = catalysts
        self.regime = regime
        self.sentiment = sentiment
        self.calendar = calendar
        self.settings = settings
        self.weights = weights or FACTOR_WEIGHTS

    # -------- Public API --------
    def snapshot(self, symbol: str, timeframe: str = "daily", refresh: bool = False) -> dict[str, Any]:
        symbol = symbol.upper()
        tf = resolve_timeframe(timeframe)

        daily_payload = self.market_data.safe_historical_candles(symbol, interval_minutes=1440, lookback_days=365, refresh=refresh)
        daily_candles = normalize_candles(daily_payload)
        if not daily_candles:
            return self._empty(symbol, tf["label"], reason="no_daily_candles")
        intraday_payload = None
        intraday_candles = []
        if tf["interval"] < 60:
            intraday_payload = self.market_data.safe_historical_candles(symbol, interval_minutes=tf["interval"], lookback_days=tf["lookback"], refresh=refresh)
            intraday_candles = normalize_candles(intraday_payload)

        benchmark_return = self._benchmark_return(refresh=refresh)
        daily_analysis = analyze_candles(daily_candles, benchmark_return_pct=benchmark_return, timeframe="daily", interval_minutes=1440)
        intraday_view = intraday_analysis(intraday_candles, interval_minutes=tf["interval"]) if intraday_candles else None
        patterns = detect_patterns(daily_candles)
        catalysts = self.catalysts.catalysts_for(symbol, refresh=False, allow_remote=False, include_static_links=False)
        sentiment_score = self.sentiment.score_for(symbol, catalysts)

        trade_info = self.public_data.trade_info(symbol) or {}
        regime_snapshot = self.regime.snapshot(refresh=False)

        subscores = {
            "technical": self._technical(daily_analysis),
            "intraday_signal": self._intraday_signal(intraday_view),
            "sentiment": self._sentiment(sentiment_score),
            "volume_volatility": self._volume_volatility(daily_analysis, intraday_view),
            "quant": self._quant(symbol, daily_candles),
            "regime_fit": self._regime_fit(daily_analysis, regime_snapshot, symbol),
            "event_proximity": self._event_proximity(symbol, catalysts),
            "liquidity": self._liquidity(trade_info),
            "pattern": self._pattern(patterns),
        }

        long_score, short_score = self._direction_scores(subscores)
        gating = self._gating(symbol, daily_analysis, trade_info)
        bias = "long" if long_score - short_score > 8 else "short" if short_score - long_score > 8 else "neutral"

        return {
            "symbol": symbol,
            "timeframe": tf["label"],
            "computed_at": daily_candles[-1].timestamp if daily_candles else None,
            "weights": self.weights,
            "subscores": {name: pair for name, pair in subscores.items()},
            "long_score": long_score,
            "short_score": short_score,
            "bias": bias,
            "gating": gating,
            "rationale": self._rationale(subscores, daily_analysis, sentiment_score, patterns),
            "snapshot_inputs": {
                "last_price": daily_analysis.get("last_price"),
                "trend_state": daily_analysis.get("trend_state"),
                "rsi": daily_analysis.get("rsi"),
                "macd_state": (daily_analysis.get("macd") or {}).get("state"),
                "support": daily_analysis.get("support"),
                "resistance": daily_analysis.get("resistance"),
                "risk_reward": daily_analysis.get("risk_reward"),
                "atr_pct": (daily_analysis.get("regime") or {}).get("atr_pct"),
                "sentiment_label": sentiment_score.get("label"),
                "sentiment_score": sentiment_score.get("score"),
            },
        }

    def batch(self, symbols: list[str], timeframe: str = "daily", refresh: bool = False, max_workers: int = 8) -> list[dict[str, Any]]:
        if not symbols:
            return []
        symbols = [s.upper() for s in symbols]
        with ThreadPoolExecutor(max_workers=min(max_workers, len(symbols))) as pool:
            rows = list(pool.map(lambda s: self.snapshot(s, timeframe=timeframe, refresh=refresh), symbols))
        return [row for row in rows if row]

    # -------- Subscore implementations (returns {long, short, raw}) --------
    def _technical(self, analysis: dict[str, Any]) -> dict[str, int]:
        score = float(analysis.get("technical_score") or 0)
        trend = analysis.get("trend_state") or ""
        long_score = int(max(0, min(100, score)))
        short_score = int(max(0, min(100, 100 - score))) if "downtrend" in trend or trend == "sideways" else int(max(0, min(100, 100 - score)) * 0.5)
        if "uptrend" in trend:
            short_score = max(0, short_score - 25)
        if "downtrend" in trend:
            long_score = max(0, long_score - 25)
        return {"long": long_score, "short": short_score, "raw": score}

    def _intraday_signal(self, view: dict[str, Any] | None) -> dict[str, int]:
        if not view or view.get("status") != "ok":
            return {"long": 0, "short": 0, "raw": None}
        primary = view.get("primary_signal") or {}
        quality = float(primary.get("quality") or 0)
        direction = primary.get("direction") or "neutral"
        return {
            "long": int(quality) if direction == "long" else 0,
            "short": int(quality) if direction == "short" else 0,
            "raw": quality,
        }

    def _sentiment(self, score: dict[str, Any]) -> dict[str, int]:
        raw = float(score.get("score") or 0)
        long_score = int(max(0, min(100, 50 + raw / 2)))
        short_score = int(max(0, min(100, 50 - raw / 2)))
        return {"long": long_score, "short": short_score, "raw": raw, "label": score.get("label")}

    def _volume_volatility(self, daily: dict[str, Any], intraday: dict[str, Any] | None) -> dict[str, int]:
        vol_x = float(daily.get("volume_expansion") or 1.0)
        atr_pct = float((daily.get("regime") or {}).get("atr_pct") or 0)
        # Stronger volume + healthy ATR is good for both directions; we scale.
        base = min(100, int((vol_x - 1) * 50 + atr_pct * 4))
        return {"long": max(0, base), "short": max(0, base), "raw": {"vol_x": vol_x, "atr_pct": atr_pct}}

    def _quant(self, symbol: str, candles: list[Any]) -> dict[str, int]:
        long_hits = 0
        short_hits = 0
        # Run a curated short list of strategies for speed.
        curated = ["golden_cross_50_200", "supertrend_follow", "rsi2_connors", "bb_squeeze_breakout"]
        for strategy_id in curated:
            spec = BUILTIN_STRATEGIES.get(strategy_id)
            if not spec:
                continue
            try:
                result = run_strategy(spec, candles, timeframe="daily", settings=self.settings)
            except Exception:
                continue
            metrics = result.get("metrics") or {}
            if not metrics.get("sample_size"):
                continue
            profit_factor = float(metrics.get("profit_factor") or 0)
            win_rate = float(metrics.get("win_rate") or 0)
            score = int(min(100, profit_factor * 30 + win_rate / 2))
            if spec.direction in {"long_only", "both"}:
                long_hits = max(long_hits, score)
            if spec.direction in {"short_only", "both"}:
                short_hits = max(short_hits, score)
        return {"long": long_hits, "short": short_hits, "raw": {"hits": curated}}

    def _regime_fit(self, analysis: dict[str, Any], regime_snapshot: dict[str, Any], symbol: str) -> dict[str, int]:
        index_trend = (regime_snapshot.get("benchmark") or {}).get("trend") or "sideways"
        trade_mode = (regime_snapshot.get("trade_mode") or {}).get("bias") or "two-way"
        symbol_trend = analysis.get("trend_state") or "sideways"
        long_score = 50
        short_score = 50
        if "uptrend" in symbol_trend:
            long_score += 25
            if trade_mode == "long-friendly":
                long_score += 15
        if "downtrend" in symbol_trend:
            short_score += 25
            if trade_mode == "short-friendly":
                short_score += 15
        return {"long": min(100, long_score), "short": min(100, short_score), "raw": {"index_trend": index_trend, "trade_mode": trade_mode}}

    def _event_proximity(self, symbol: str, catalysts: list[dict[str, Any]]) -> dict[str, int]:
        # Earnings-today (or in next 3 days) bumps; F&O ban subtracts.
        boost = 0
        if self.calendar.has_results_today(symbol):
            boost += 30
        in_ban = self.calendar.is_in_fno_ban(symbol)
        if in_ban:
            return {"long": 0, "short": 0, "raw": {"reason": "fno_ban"}}
        # Fresh catalyst (within 24h with sentiment) lifts both sides.
        for item in catalysts[:3]:
            if (item.get("relevance_score") or 0) >= 0.6:
                boost += 10
                break
        return {"long": min(100, 40 + boost), "short": min(100, 40 + boost), "raw": {"results_today": boost >= 30}}

    def _liquidity(self, trade_info: dict[str, Any]) -> dict[str, int]:
        traded_value = float(trade_info.get("total_traded_value") or 0)
        # 50 Cr = good intraday liquidity floor (rupees).
        if traded_value <= 0:
            return {"long": 30, "short": 30, "raw": None}
        score = int(min(100, (traded_value / 1_00_00_000) ** 0.5 * 12))
        return {"long": score, "short": score, "raw": traded_value}

    def _pattern(self, patterns: dict[str, Any]) -> dict[str, int]:
        if patterns.get("status") != "ok":
            return {"long": 0, "short": 0, "raw": None}
        return {
            "long": int(patterns.get("long_score") or 0),
            "short": int(patterns.get("short_score") or 0),
            "raw": [item.get("name") for item in patterns.get("detections") or []],
        }

    # -------- Gating + rollup --------
    def _direction_scores(self, subscores: dict[str, dict[str, int]]) -> tuple[int, int]:
        total = sum(self.weights.values()) or 1
        long_sum = 0.0
        short_sum = 0.0
        for name, weight in self.weights.items():
            sub = subscores.get(name) or {}
            long_sum += (sub.get("long") or 0) * weight
            short_sum += (sub.get("short") or 0) * weight
        return int(round(long_sum / total)), int(round(short_sum / total))

    def _gating(self, symbol: str, analysis: dict[str, Any], trade_info: dict[str, Any]) -> dict[str, Any]:
        traded_value = float(trade_info.get("total_traded_value") or 0)
        price = float(analysis.get("last_price") or 0)
        fno_ban = self.calendar.is_in_fno_ban(symbol)
        results_today = self.calendar.has_results_today(symbol)
        return {
            "liquidity_ok": traded_value >= 50 * 1_00_00_000,
            "price_ok": price >= 50,
            "fno_ban": fno_ban,
            "results_today": results_today,
        }

    def _rationale(self, subscores: dict[str, dict[str, int]], analysis: dict[str, Any], sentiment_score: dict[str, Any], patterns: dict[str, Any]) -> dict[str, Any]:
        ranked = sorted(subscores.items(), key=lambda item: max(item[1].get("long") or 0, item[1].get("short") or 0), reverse=True)
        top_positive = [name for name, sub in ranked[:3] if max(sub.get("long") or 0, sub.get("short") or 0) >= 50]
        top_negative = [name for name, sub in ranked[-3:] if max(sub.get("long") or 0, sub.get("short") or 0) < 30]
        return {
            "top_positive": top_positive,
            "top_negative": top_negative,
            "patterns": [item.get("name") for item in (patterns.get("detections") or [])[:3]],
            "sentiment_label": sentiment_score.get("label"),
        }

    def _empty(self, symbol: str, timeframe: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "long_score": 0,
            "short_score": 0,
            "bias": "neutral",
            "gating": {"liquidity_ok": False, "price_ok": False, "fno_ban": False, "results_today": False},
            "subscores": {},
            "rationale": {"top_positive": [], "top_negative": [], "patterns": [], "sentiment_label": "neutral"},
            "error": reason,
        }

    def _benchmark_return(self, refresh: bool) -> float | None:
        bench = self.settings.benchmark_symbol.replace("NSE_", "")
        payload = self.market_data.safe_historical_candles(bench, interval_minutes=1440, lookback_days=120, refresh=refresh)
        analysis = analyze_candles(normalize_candles(payload))
        return analysis.get("return_20d_pct")
