from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from groww_trader.settings import AppSettings

from .indicators import analyze_candles, atr, normalize_candles, rsi, sma
from .market_data import MarketDataRouter


class RegimeService:
    """NIFTY regime + sector breadth + watchlist breadth gauge."""

    def __init__(self, market_data: MarketDataRouter, settings: AppSettings) -> None:
        self.market_data = market_data
        self.settings = settings

    def snapshot(self, refresh: bool = False) -> dict[str, Any]:
        nifty = self._index_view(self.settings.benchmark_symbol, refresh=refresh)
        sector_views = self._fetch_many(self.settings.sector_index_symbols, refresh=refresh)
        sector_breadth = _breadth(sector_views)
        watchlist_views = self._fetch_many(self.settings.scan_symbols, refresh=refresh, light=True)
        watchlist_breadth = _breadth(watchlist_views)
        return {
            "benchmark": nifty,
            "sectors": sector_views,
            "sector_breadth": sector_breadth,
            "watchlist_breadth": watchlist_breadth,
            "trade_mode": _trade_mode(nifty, sector_breadth, watchlist_breadth),
        }

    def _fetch_many(self, symbols: tuple[str, ...], refresh: bool, light: bool = False) -> list[dict[str, Any]]:
        if not symbols:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as pool:
            return [view for view in pool.map(lambda s: self._index_view(s, refresh=refresh, light=light), symbols) if view]

    def _index_view(self, symbol: str, refresh: bool, light: bool = False) -> dict[str, Any] | None:
        clean = symbol.replace("NSE_", "").replace("BSE_", "")
        try:
            payload = self.market_data.safe_historical_candles(clean, interval_minutes=1440, lookback_days=120, refresh=refresh)
        except Exception as exc:  # pragma: no cover - defensive
            return {"symbol": clean, "error": str(exc)}
        candles = normalize_candles(payload)
        if not candles:
            return {"symbol": clean, "error": "no data"}
        closes = [c.close for c in candles]
        ma20 = sma(closes, 20)
        ma50 = sma(closes, 50)
        ma200 = sma(closes, 200)
        last = closes[-1]
        change_1d_pct = ((last - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else None
        change_5d_pct = ((last - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 else None
        atr_value = atr(candles)
        atr_pct = (atr_value / last * 100) if atr_value and last else None
        trend = _trend(last, ma20, ma50, ma200)
        if light:
            return {
                "symbol": clean,
                "last": round(last, 2),
                "change_1d_pct": round(change_1d_pct, 2) if change_1d_pct is not None else None,
                "trend": trend,
            }
        return {
            "symbol": clean,
            "last": round(last, 2),
            "ma20": round(ma20, 2) if ma20 else None,
            "ma50": round(ma50, 2) if ma50 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "rsi": rsi(closes),
            "atr_pct": round(atr_pct, 2) if atr_pct else None,
            "change_1d_pct": round(change_1d_pct, 2) if change_1d_pct is not None else None,
            "change_5d_pct": round(change_5d_pct, 2) if change_5d_pct is not None else None,
            "trend": trend,
            "volatility_regime": _volatility(atr_pct),
            "provider": payload.get("data_source"),
            "freshness": payload.get("data_freshness"),
        }


def _trend(price: float, ma20: float | None, ma50: float | None, ma200: float | None) -> str:
    if ma20 and ma50 and ma200 and price > ma20 > ma50 > ma200:
        return "strong_uptrend"
    if ma20 and ma50 and price > ma20 > ma50:
        return "uptrend"
    if ma20 and ma50 and price < ma20 < ma50:
        return "downtrend"
    if ma20 and ma50 and ma200 and price < ma20 < ma50 < ma200:
        return "strong_downtrend"
    return "sideways"


def _volatility(atr_pct: float | None) -> str:
    if atr_pct is None:
        return "unknown"
    if atr_pct > 4:
        return "high"
    if atr_pct > 2:
        return "medium"
    return "low"


def _breadth(views: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [view for view in views if view and not view.get("error")]
    if not rows:
        return {"advancing": 0, "declining": 0, "neutral": 0, "advance_decline_ratio": None, "total": 0}
    advancing = sum(1 for row in rows if (row.get("change_1d_pct") or 0) > 0)
    declining = sum(1 for row in rows if (row.get("change_1d_pct") or 0) < 0)
    neutral = len(rows) - advancing - declining
    ratio = round(advancing / declining, 2) if declining else None
    return {
        "advancing": advancing,
        "declining": declining,
        "neutral": neutral,
        "advance_decline_ratio": ratio,
        "total": len(rows),
    }


def _trade_mode(nifty: dict[str, Any] | None, sector_breadth: dict[str, Any], watchlist_breadth: dict[str, Any]) -> dict[str, Any]:
    if not nifty or nifty.get("error"):
        return {"bias": "unknown", "intraday_long_bias": False, "intraday_short_bias": False, "reason": "Benchmark data unavailable"}
    trend = nifty.get("trend")
    change = nifty.get("change_1d_pct") or 0
    sector_adv = sector_breadth.get("advancing", 0)
    sector_total = max(sector_breadth.get("total") or 1, 1)
    sector_pct = sector_adv / sector_total

    if trend in {"strong_uptrend", "uptrend"} and change >= 0 and sector_pct >= 0.5:
        return {"bias": "long-friendly", "intraday_long_bias": True, "intraday_short_bias": False, "reason": "Index uptrend with broad sector participation."}
    if trend in {"strong_downtrend", "downtrend"} and change <= 0 and sector_pct <= 0.5:
        return {"bias": "short-friendly", "intraday_long_bias": False, "intraday_short_bias": True, "reason": "Index downtrend with broad weakness."}
    return {"bias": "two-way", "intraday_long_bias": False, "intraday_short_bias": False, "reason": "Mixed trend / breadth; prefer levels-based setups only."}
