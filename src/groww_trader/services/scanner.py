from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any

from groww_trader.settings import AppSettings

from .catalysts import CatalystService
from .backtests import run_backtest
from .charting import build_chart_context
from .indicators import analyze_candles, normalize_candles
from .intraday import intraday_analysis
from .market_data import MarketDataRouter


TIMEFRAME_MAP: dict[str, dict[str, Any]] = {
    "5m": {"interval": 5, "lookback": 30, "label": "5m"},
    "15m": {"interval": 15, "lookback": 45, "label": "15m"},
    "30m": {"interval": 30, "lookback": 55, "label": "30m"},
    "hourly": {"interval": 60, "lookback": 120, "label": "hourly"},
    "daily": {"interval": 1440, "lookback": 365, "label": "daily"},
}


def resolve_timeframe(value: str | None) -> dict[str, Any]:
    if not value:
        return TIMEFRAME_MAP["daily"]
    normalized = value.strip().lower()
    return TIMEFRAME_MAP.get(normalized, TIMEFRAME_MAP["daily"])


class ScannerService:
    def __init__(self, data: MarketDataRouter, catalysts: CatalystService, settings: AppSettings) -> None:
        self.data = data
        self.catalysts = catalysts
        self.settings = settings
        self._detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._detail_cache_lock = threading.Lock()
        self._detail_ttl_seconds = 20

    def scan(
        self,
        limit: int = 50,
        refresh: bool = False,
        universe: str = "watchlist",
        symbols: str | None = None,
        timeframe: str = "daily",
    ) -> list[dict[str, Any]]:
        tf = resolve_timeframe(timeframe)
        instruments = self._universe(limit=limit, refresh=refresh, universe=universe, symbols=symbols)
        benchmark_return = self._benchmark_return(refresh=refresh)

        def scan_one(instrument: dict[str, Any]) -> dict[str, Any] | None:
            symbol = str(instrument.get("trading_symbol", "")).upper()
            if not symbol:
                return None
            payload = self.data.safe_historical_candles(
                symbol,
                interval_minutes=tf["interval"],
                lookback_days=tf["lookback"],
                refresh=refresh,
            )
            candles = normalize_candles(payload)
            analysis = analyze_candles(
                candles,
                benchmark_return_pct=benchmark_return,
                timeframe=tf["label"],
                interval_minutes=tf["interval"],
            )
            catalysts = self.catalysts.catalysts_for(
                symbol,
                str(instrument.get("name") or symbol),
                refresh=False,
                allow_remote=False,
                include_static_links=False,
            )
            row: dict[str, Any] = {
                "symbol": symbol,
                "groww_symbol": instrument.get("groww_symbol") or f"NSE-{symbol}",
                "company": instrument.get("name") or symbol,
                "price": analysis.get("last_price"),
                "trend_state": analysis.get("trend_state", "unknown"),
                "rsi": analysis.get("rsi"),
                "macd_state": (analysis.get("macd") or {}).get("state"),
                "volume_expansion": analysis.get("volume_expansion"),
                "relative_strength": analysis.get("relative_strength"),
                "support": analysis.get("support"),
                "resistance": analysis.get("resistance"),
                "risk_reward": analysis.get("risk_reward"),
                "technical_score": analysis.get("technical_score", 0),
                "ai_confidence": None,
                "catalyst_count": len(catalysts),
                "data_status": analysis.get("status"),
                "data_source": payload.get("data_source"),
                "data_freshness": payload.get("data_freshness"),
                "stale_cache_used": payload.get("stale_cache_used", False),
                "grade": (analysis.get("trade_plan") or {}).get("grade"),
                "action": (analysis.get("trade_plan") or {}).get("action"),
                "timeframe": tf["label"],
            }
            if tf["interval"] < 1440:
                intraday = intraday_analysis(candles, interval_minutes=tf["interval"], benchmark_return_pct=benchmark_return)
                row["vwap_state"] = intraday.get("vwap_state")
                row["orb_state"] = (intraday.get("opening_range") or {}).get("state")
                row["intraday_signal"] = (intraday.get("primary_signal") or {}).get("name")
                row["intraday_quality"] = (intraday.get("primary_signal") or {}).get("quality")
            return row

        if not instruments:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(instruments))) as pool:
            rows = [row for row in pool.map(scan_one, instruments) if row]
        return sorted(rows, key=lambda row: row.get("technical_score") or 0, reverse=True)

    def detail(self, symbol: str, refresh: bool = False, timeframe: str = "daily") -> dict[str, Any]:
        symbol = symbol.upper()
        requested_tf = resolve_timeframe(timeframe)
        cache_key = f"{symbol}:{requested_tf['label']}"
        if not refresh:
            cached = self._get_detail_cache(cache_key)
            if cached is not None:
                return cached
        default_tf_value = max(self.settings.intraday_default_timeframe, 5)

        with ThreadPoolExecutor(max_workers=5) as pool:
            instruments_future = pool.submit(self.data.load_instruments, search=symbol, limit=10, allow_remote=refresh)
            benchmark_future = pool.submit(self._benchmark_return, refresh=refresh)
            daily_future = pool.submit(self.data.safe_historical_candles, symbol, interval_minutes=1440, lookback_days=365, refresh=refresh)
            hourly_future = pool.submit(self.data.safe_historical_candles, symbol, interval_minutes=60, lookback_days=90, refresh=refresh)
            intraday_future = (
                pool.submit(
                    self.data.safe_historical_candles,
                    symbol,
                    interval_minutes=requested_tf["interval"],
                    lookback_days=requested_tf["lookback"],
                    refresh=refresh,
                )
                if requested_tf["interval"] < 60
                else pool.submit(self.data.safe_historical_candles, symbol, interval_minutes=default_tf_value, lookback_days=15, refresh=False)
            )

            instruments = instruments_future.result()
            benchmark_return = benchmark_future.result()
            daily_payload = daily_future.result()
            hourly_payload = hourly_future.result()
            primary_intraday_payload = intraday_future.result()

        instrument = next((item for item in instruments if item.get("trading_symbol") == symbol), None)
        company = str((instrument or {}).get("name") or symbol)
        daily = normalize_candles(daily_payload)
        hourly = normalize_candles(hourly_payload)
        daily_analysis = analyze_candles(daily, benchmark_return_pct=benchmark_return, timeframe="daily", interval_minutes=1440)
        hourly_analysis = analyze_candles(hourly, benchmark_return_pct=None, timeframe="hourly", interval_minutes=60)
        daily_source = _payload_source(daily_payload)
        hourly_source = _payload_source(hourly_payload)
        daily_chart = build_chart_context(symbol, "daily", daily, daily_analysis, daily_source)
        hourly_chart = build_chart_context(symbol, "hourly", hourly, hourly_analysis, hourly_source)

        # Intraday timeframe (5m/15m) requested-on-demand for the workstation.
        intraday_payload: dict[str, Any] | None = None
        intraday_candles_data: list[dict[str, Any]] = []
        intraday_analysis_data: dict[str, Any] | None = None
        intraday_chart: dict[str, Any] | None = None
        intraday_view: dict[str, Any] | None = None
        if requested_tf["interval"] < 60:
            intraday_payload = primary_intraday_payload
            intraday_candles = normalize_candles(intraday_payload)
            intraday_analysis_data = analyze_candles(
                intraday_candles,
                benchmark_return_pct=None,
                timeframe=requested_tf["label"],
                interval_minutes=requested_tf["interval"],
            )
            intraday_chart = build_chart_context(
                symbol,
                requested_tf["label"],
                intraday_candles,
                intraday_analysis_data,
                _payload_source(intraday_payload),
            )
            intraday_candles_data = [c.__dict__ for c in intraday_candles]
            intraday_view = intraday_analysis(intraday_candles, interval_minutes=requested_tf["interval"])

        # Always compute intraday view at default TF for the panel even if not requested.
        if intraday_view is None:
            tf_candles = normalize_candles(primary_intraday_payload)
            intraday_view = intraday_analysis(tf_candles, interval_minutes=default_tf_value)
            intraday_view["timeframe_minutes"] = default_tf_value

        catalysts = self.catalysts.catalysts_for(symbol, company, refresh=refresh, allow_remote=refresh)
        risk_plan = self._risk_plan(daily_analysis, intraday_view=intraday_view)
        result = {
            "symbol": symbol,
            "company": company,
            "instrument": instrument,
            "daily_candles": [c.__dict__ for c in daily],
            "hourly_candles": [c.__dict__ for c in hourly],
            "intraday_candles": intraday_candles_data,
            "intraday_timeframe": requested_tf["label"] if requested_tf["interval"] < 60 else None,
            "daily_analysis": daily_analysis,
            "hourly_analysis": hourly_analysis,
            "intraday_analysis": intraday_analysis_data,
            "intraday_view": intraday_view,
            "risk_plan": risk_plan,
            "catalysts": catalysts,
            "benchmark": self.settings.benchmark_symbol,
            "chart_overlays": {
                "daily": daily_chart["overlays"],
                "hourly": hourly_chart["overlays"],
                **({requested_tf["label"]: intraday_chart["overlays"]} if intraday_chart else {}),
            },
            "chart_markers": {
                "daily": daily_chart["markers"],
                "hourly": hourly_chart["markers"],
                **({requested_tf["label"]: intraday_chart["markers"]} if intraday_chart else {}),
            },
            "setup_mode_summary": daily_analysis.get("setup_mode_summary"),
            "data_source": {
                "daily": daily_source,
                "hourly": hourly_source,
                **({requested_tf["label"]: _payload_source(intraday_payload)} if intraday_payload else {}),
            },
            "data_freshness": {
                "daily": daily_payload.get("data_freshness"),
                "hourly": hourly_payload.get("data_freshness"),
                **({requested_tf["label"]: (intraday_payload or {}).get("data_freshness")} if intraday_payload else {}),
            },
            "fallback_chain": {
                "daily": daily_payload.get("fallback_chain", []),
                "hourly": hourly_payload.get("fallback_chain", []),
                **({requested_tf["label"]: (intraday_payload or {}).get("fallback_chain", [])} if intraday_payload else {}),
            },
            "stale_cache_used": bool(daily_payload.get("stale_cache_used") or hourly_payload.get("stale_cache_used")),
            "errors": {
                "daily": daily_payload.get("error"),
                "hourly": hourly_payload.get("error"),
                **({requested_tf["label"]: (intraday_payload or {}).get("error")} if intraday_payload else {}),
            },
        }
        if not refresh:
            self._set_detail_cache(cache_key, result)
        return result

    def chart_context(self, symbol: str, timeframe: str = "daily", refresh: bool = False) -> dict[str, Any]:
        symbol = symbol.upper()
        tf = resolve_timeframe(timeframe)
        payload = self.data.safe_historical_candles(
            symbol,
            interval_minutes=tf["interval"],
            lookback_days=tf["lookback"],
            refresh=refresh,
        )
        candles = normalize_candles(payload)
        benchmark_return = self._benchmark_return(refresh=refresh) if tf["label"] == "daily" else None
        analysis = analyze_candles(candles, benchmark_return_pct=benchmark_return, timeframe=tf["label"], interval_minutes=tf["interval"])
        return build_chart_context(symbol, tf["label"], candles, analysis, _payload_source(payload))

    def backtest(self, symbol: str, strategy_id: str, timeframe: str = "daily", params: dict[str, Any] | None = None, refresh: bool = False) -> dict[str, Any]:
        detail = self.detail(symbol=symbol, refresh=refresh, timeframe=timeframe)
        tf = resolve_timeframe(timeframe)
        candles_key = "daily_candles" if tf["label"] == "daily" else ("hourly_candles" if tf["label"] == "hourly" else "intraday_candles")
        source = detail.get(candles_key) or detail["daily_candles"]
        candles = normalize_candles({"candles": [[c["timestamp"], c["open"], c["high"], c["low"], c["close"], c["volume"]] for c in source]})
        result = run_backtest(candles, strategy_id=strategy_id, params=params, timeframe=tf["label"], settings=self.settings)
        return {"symbol": detail["symbol"], "timeframe": tf["label"], **result}

    def _universe(self, limit: int, refresh: bool, universe: str, symbols: str | None) -> list[dict[str, Any]]:
        selected_symbols = _parse_symbols(symbols)
        if not selected_symbols:
            if universe == "nifty50":
                selected_symbols = self.settings.nifty50_symbols
            else:
                selected_symbols = self.settings.scan_symbols
        if universe in {"watchlist", "nifty50"} or selected_symbols:
            instruments = []
            for symbol in selected_symbols:
                found = self.data.load_instruments(search=symbol, limit=5, refresh=refresh, allow_remote=refresh)
                match = next((item for item in found if item.get("trading_symbol") == symbol), None)
                instruments.append(match or {"trading_symbol": symbol, "groww_symbol": f"NSE-{symbol}", "name": symbol})
            return instruments[:limit]
        return self.data.load_instruments(limit=limit, refresh=refresh, allow_remote=refresh)

    def _benchmark_return(self, refresh: bool) -> float | None:
        symbol = self.settings.benchmark_symbol.replace("NSE_", "")
        payload = self.data.safe_historical_candles(symbol, interval_minutes=1440, lookback_days=120, refresh=refresh)
        analysis = analyze_candles(normalize_candles(payload))
        return analysis.get("return_20d_pct")

    def _get_detail_cache(self, key: str) -> dict[str, Any] | None:
        with self._detail_cache_lock:
            cached = self._detail_cache.get(key)
            if not cached:
                return None
            timestamp, payload = cached
            if time.time() - timestamp > self._detail_ttl_seconds:
                self._detail_cache.pop(key, None)
                return None
            return copy.deepcopy(payload)

    def _set_detail_cache(self, key: str, payload: dict[str, Any]) -> None:
        with self._detail_cache_lock:
            self._detail_cache[key] = (time.time(), copy.deepcopy(payload))

    def _risk_plan(self, analysis: dict[str, Any], intraday_view: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = analysis.get("last_price")
        plan = analysis.get("trade_plan") or {}
        stop = plan.get("stop_loss") or analysis.get("support")
        target = plan.get("targets", [{}])[0].get("price") if plan.get("targets") else analysis.get("resistance")
        capital = self.settings.account_capital
        risk_budget = capital * (self.settings.risk_per_trade_pct / 100)
        max_position_value_swing = capital
        max_position_value_intra = capital * (self.settings.intraday_max_position_pct / 100) * self.settings.intraday_leverage

        risk_per_share = (entry - stop) if entry and stop and entry > stop else None
        swing_qty = int(risk_budget / risk_per_share) if risk_per_share else 0
        intraday_qty = int(min(risk_budget / risk_per_share, max_position_value_intra / entry)) if risk_per_share and entry else 0
        swing_qty = max(swing_qty, 0)
        intraday_qty = max(intraday_qty, 0)

        return {
            "account_capital": capital,
            "risk_per_trade_pct": self.settings.risk_per_trade_pct,
            "risk_budget": round(risk_budget, 2),
            "entry": entry,
            "stop_loss": stop,
            "target": target,
            "risk_reward": analysis.get("risk_reward"),
            "risk_per_share": round(risk_per_share, 2) if risk_per_share else None,
            "swing_quantity": swing_qty,
            "intraday_quantity": intraday_qty,
            "intraday_leverage": self.settings.intraday_leverage,
            "intraday_max_daily_loss_pct": self.settings.intraday_max_daily_loss_pct,
            "max_intraday_position_value": round(max_position_value_intra, 2),
            "max_swing_position_value": round(max_position_value_swing, 2),
            "estimated_quantity": swing_qty or intraday_qty,
            "intraday_view": intraday_view,
        }


def _parse_symbols(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip().upper() for part in raw.replace("\n", ",").split(",") if part.strip())


def _payload_source(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        "provider": payload.get("data_source") or payload.get("source"),
        "freshness": payload.get("data_freshness"),
        "age_seconds": payload.get("data_age_seconds"),
        "normalized_symbol": payload.get("normalized_symbol"),
        "stale_cache_used": payload.get("stale_cache_used", False),
    }
