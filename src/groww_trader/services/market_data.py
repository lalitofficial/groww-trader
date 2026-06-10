from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Protocol

import requests

from groww_trader.groww_client import groww_constant
from groww_trader.settings import AppSettings

from .groww_data import GrowwDataService
from .request_budget import budget
from .storage import Storage


@dataclass(frozen=True)
class MarketDataRequest:
    symbol: str
    interval_minutes: int
    lookback_days: int


class MarketDataProvider(Protocol):
    name: str

    def supports_interval(self, interval_minutes: int) -> bool: ...

    def historical_candles(self, request: MarketDataRequest) -> dict[str, Any]: ...


class MarketDataRouter:
    def __init__(self, storage: Storage, settings: AppSettings, groww_data: GrowwDataService, public_data: Any | None = None) -> None:
        self.storage = storage
        self.settings = settings
        self.groww_data = groww_data
        self.public_data = public_data
        self.providers: dict[str, MarketDataProvider] = {
            "yahoo": YahooProvider(),
            "alpha_vantage": AlphaVantageProvider(settings.alpha_vantage_api_key),
            "stooq": StooqProvider(),
            "groww": GrowwMarketFallbackProvider(groww_data),
        }

    def load_instruments(
        self,
        refresh: bool = False,
        limit: int = 5000,
        search: str | None = None,
        allow_remote: bool = True,
    ) -> list[dict[str, Any]]:
        cached = self.storage.list_instruments(search=search, limit=limit)
        if cached and not refresh:
            return cached
        if not allow_remote:
            return cached or _fallback_instruments(search, limit)
        try:
            refreshed = self.groww_data.load_instruments(refresh=refresh, limit=limit, search=search)
            if refreshed:
                return refreshed
        except Exception:
            pass
        if cached:
            return cached
        return _fallback_instruments(search, limit)

    def safe_historical_candles(self, trading_symbol: str, interval_minutes: int, lookback_days: int, refresh: bool = False) -> dict[str, Any]:
        request = MarketDataRequest(trading_symbol.upper(), interval_minutes, lookback_days)
        key = self._cache_key(request)
        ttl = self._ttl_minutes(interval_minutes)
        cached = self.storage.get_candles_record(key)
        if cached and not refresh and _is_fresh(cached, ttl):
            budget().record("cache", f"candles_{interval_minutes}m")
            return self._with_meta(cached["payload"], cached, "cache", [], stale=False)

        fallback_chain: list[dict[str, str]] = []
        for provider_name in self.settings.market_data_provider_order:
            provider_name = provider_name.lower()
            if provider_name == "groww" and not self.settings.market_data_allow_groww_fallback:
                fallback_chain.append({"provider": "groww", "status": "disabled"})
                continue
            provider = self.providers.get(provider_name)
            if not provider or not provider.supports_interval(interval_minutes):
                fallback_chain.append({"provider": provider_name, "status": "unsupported"})
                continue
            try:
                budget().record(provider.name, f"candles_{request.interval_minutes}m")
                payload = provider.historical_candles(request)
                if payload.get("candles"):
                    metadata = self._metadata(request, provider.name, payload)
                    self.storage.set_candles(key, metadata, payload)
                    record = self.storage.get_candles_record(key)
                    fallback_chain.append({"provider": provider.name, "status": "ok"})
                    return self._with_meta(payload, record or metadata, provider.name, fallback_chain, stale=False)
                fallback_chain.append({"provider": provider.name, "status": "empty"})
            except Exception as exc:
                fallback_chain.append({"provider": provider.name, "status": "error", "message": str(exc)})

        stale = cached or self.storage.get_latest_candles_record(trading_symbol, interval_minutes)
        if stale:
            payload = dict(stale["payload"])
            payload["warning"] = "Using stale cached market data after provider fallback failed."
            return self._with_meta(payload, stale, "stale_cache", fallback_chain, stale=True)
        return {
            "candles": [],
            "source": "market_data_router",
            "error": "No market data provider returned candles.",
            "data_source": "none",
            "data_freshness": "missing",
            "fallback_chain": fallback_chain,
            "stale_cache_used": False,
        }

    def _cache_key(self, request: MarketDataRequest) -> str:
        bucket = _cache_bucket(request.interval_minutes)
        return f"{request.symbol}|NSE|CASH|{request.interval_minutes}|{request.lookback_days}d|{bucket}"

    def _metadata(self, request: MarketDataRequest, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        end = datetime.now().replace(second=0, microsecond=0)
        start = end - timedelta(days=request.lookback_days)
        return {
            "trading_symbol": request.symbol,
            "exchange": "NSE",
            "segment": "CASH",
            "interval_minutes": request.interval_minutes,
            "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
            "provider": provider,
            "normalized_symbol": payload.get("normalized_symbol"),
            "warning": payload.get("warning"),
            "error": payload.get("error"),
        }

    def _ttl_minutes(self, interval_minutes: int) -> int:
        if interval_minutes >= 1440:
            return self.settings.market_data_daily_ttl_min
        if interval_minutes >= 60:
            return max(self.settings.market_data_intraday_ttl_min, 10)
        return self.settings.market_data_intraday_ttl_min

    def latest_quote(self, trading_symbol: str) -> dict[str, Any] | None:
        if self.public_data is not None:
            try:
                live = self.public_data.quote(trading_symbol)
            except Exception:
                live = None
            if live and live.get("ltp"):
                return {
                    "symbol": trading_symbol.upper(),
                    "timestamp": int(time.time()),
                    "ltp": float(live["ltp"]),
                    "open": _as_float(live.get("open")),
                    "high": _as_float(live.get("high")),
                    "low": _as_float(live.get("low")),
                    "volume": _as_float(live.get("volume") or 0) or 0,
                    "interval_minutes": 1,
                    "provider": "nse_or_google",
                    "freshness": "live",
                }
        for interval in (5, 15, 60, 1440):
            payload = self.safe_historical_candles(trading_symbol, interval, 3 if interval < 60 else 30)
            candles = payload.get("candles") or []
            if candles:
                last = candles[-1]
                return {
                    "symbol": trading_symbol.upper(),
                    "timestamp": int(last[0]),
                    "ltp": float(last[4]),
                    "open": float(last[1]),
                    "high": float(last[2]),
                    "low": float(last[3]),
                    "volume": float(last[5]) if len(last) >= 6 else 0,
                    "interval_minutes": interval,
                    "provider": payload.get("data_source"),
                    "freshness": payload.get("data_freshness"),
                }
        return None

    def _with_meta(
        self,
        payload: dict[str, Any],
        record: dict[str, Any],
        source: str,
        fallback_chain: list[dict[str, str]],
        stale: bool,
    ) -> dict[str, Any]:
        age_seconds = record.get("age_seconds") if isinstance(record, dict) else None
        provider = record.get("provider") or payload.get("source") or source
        freshness = "stale" if stale else "cached" if source == "cache" else "fresh"
        return {
            **payload,
            "source": payload.get("source") or provider,
            "data_source": provider,
            "data_freshness": freshness,
            "data_age_seconds": age_seconds,
            "normalized_symbol": payload.get("normalized_symbol") or record.get("normalized_symbol"),
            "fallback_chain": fallback_chain,
            "stale_cache_used": stale,
        }


_YAHOO_INTERVAL_MAP = {
    5: ("5m", 55),
    15: ("15m", 55),
    30: ("30m", 55),
    60: ("1h", 720),
    1440: ("1d", 3650),
}


class YahooProvider:
    name = "yahoo"

    def supports_interval(self, interval_minutes: int) -> bool:
        return interval_minutes in _YAHOO_INTERVAL_MAP

    def historical_candles(self, request: MarketDataRequest) -> dict[str, Any]:
        symbol = _yahoo_symbol(request.symbol)
        interval, max_lookback_days = _YAHOO_INTERVAL_MAP[request.interval_minutes]
        lookback = min(request.lookback_days, max_lookback_days)
        period1 = int((datetime.now(timezone.utc) - timedelta(days=lookback)).timestamp())
        period2 = int(datetime.now(timezone.utc).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        response = requests.get(
            url,
            params={"period1": period1, "period2": period2, "interval": interval, "events": "history", "includeAdjustedClose": "true"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise ValueError("Yahoo returned no chart result.")
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
        candles = []
        for index, timestamp in enumerate(timestamps):
            row = [
                int(timestamp),
                _num_at(quote.get("open"), index),
                _num_at(quote.get("high"), index),
                _num_at(quote.get("low"), index),
                _num_at(quote.get("close"), index),
                _num_at(quote.get("volume"), index) or 0,
            ]
            if all(value is not None for value in row[1:5]):
                candles.append(row)
        return {"candles": candles, "source": self.name, "normalized_symbol": symbol}


class AlphaVantageProvider:
    name = "alpha_vantage"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    def supports_interval(self, interval_minutes: int) -> bool:
        return bool(self.api_key) and interval_minutes >= 1440

    def historical_candles(self, request: MarketDataRequest) -> dict[str, Any]:
        symbol = _alpha_symbol(request.symbol)
        response = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "full", "apikey": self.api_key},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        series = data.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise ValueError(data.get("Note") or data.get("Information") or "Alpha Vantage returned no daily series.")
        cutoff = datetime.now(timezone.utc) - timedelta(days=request.lookback_days)
        candles = []
        for date_text, values in sorted(series.items()):
            stamp = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if stamp < cutoff:
                continue
            candles.append(
                [
                    int(stamp.timestamp()),
                    float(values["1. open"]),
                    float(values["2. high"]),
                    float(values["3. low"]),
                    float(values["4. close"]),
                    float(values.get("5. volume") or 0),
                ]
            )
        return {"candles": candles, "source": self.name, "normalized_symbol": symbol}


class StooqProvider:
    name = "stooq"

    def supports_interval(self, interval_minutes: int) -> bool:
        return interval_minutes >= 1440

    def historical_candles(self, request: MarketDataRequest) -> dict[str, Any]:
        symbol = _stooq_symbol(request.symbol)
        response = requests.get(f"https://stooq.com/q/d/l/?s={symbol}&i=d", headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        response.raise_for_status()
        rows = list(csv.DictReader(StringIO(response.text)))
        cutoff = datetime.now(timezone.utc) - timedelta(days=request.lookback_days)
        candles = []
        for row in rows:
            if not row.get("Date") or row.get("Close") in {"", "N/D"}:
                continue
            stamp = datetime.strptime(row["Date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if stamp < cutoff:
                continue
            candles.append(
                [
                    int(stamp.timestamp()),
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row.get("Volume") or 0),
                ]
            )
        return {"candles": candles, "source": self.name, "normalized_symbol": symbol}


class GrowwMarketFallbackProvider:
    """Disabled by policy. Groww is account-only; left in as a no-op so legacy
    env flags do not silently re-enable market-data calls against the broker.
    """

    name = "groww_fallback"

    def __init__(self, groww_data: GrowwDataService) -> None:
        self.groww_data = groww_data

    def supports_interval(self, interval_minutes: int) -> bool:
        return False

    def historical_candles(self, request: MarketDataRequest) -> dict[str, Any]:
        raise RuntimeError("Groww is account-only by policy. Use NSE/Yahoo/Google sources.")


def _is_fresh(record: dict[str, Any], ttl_minutes: int) -> bool:
    age = record.get("age_seconds")
    return age is not None and age <= ttl_minutes * 60


def _cache_bucket(interval_minutes: int) -> str:
    now = datetime.now()
    if interval_minutes >= 1440:
        return now.strftime("%Y-%m-%d")
    if interval_minutes >= 60:
        return now.strftime("%Y-%m-%d-%H")
    bucket_size = max(interval_minutes, 5)
    minute = (now.minute // bucket_size) * bucket_size
    return now.strftime("%Y-%m-%d-%H-") + f"{minute:02d}"


def _yahoo_symbol(symbol: str) -> str:
    clean = symbol.upper().replace("NSE_", "")
    if clean in {"NIFTY", "NIFTY50", "NSEI"}:
        return "^NSEI"
    if clean.startswith("^"):
        return clean
    if clean.endswith(".NS") or clean.endswith(".BO"):
        return clean
    return f"{clean}.NS"


def _alpha_symbol(symbol: str) -> str:
    clean = symbol.upper().replace("NSE_", "")
    if clean in {"NIFTY", "NIFTY50", "NSEI"}:
        return "NIFTY50.INDX"
    return clean if "." in clean else f"{clean}.BSE"


def _stooq_symbol(symbol: str) -> str:
    clean = symbol.lower().replace("nse_", "")
    if clean in {"nifty", "nifty50", "nsei"}:
        return "^nsei"
    return clean if "." in clean else f"{clean}.in"


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _num_at(values: list[Any] | None, index: int) -> float | None:
    if not values or index >= len(values) or values[index] is None:
        return None
    return float(values[index])


def _fallback_instruments(search: str | None, limit: int) -> list[dict[str, str]]:
    common = [
        ("RELIANCE", "Reliance Industries"),
        ("TCS", "TCS"),
        ("INFY", "Infosys"),
        ("HDFCBANK", "HDFC Bank"),
        ("ICICIBANK", "ICICI Bank"),
        ("SBIN", "State Bank of India"),
        ("LT", "Larsen & Toubro"),
        ("AXISBANK", "Axis Bank"),
        ("ITC", "ITC"),
        ("BHARTIARTL", "Bharti Airtel"),
        ("KOTAKBANK", "Kotak Mahindra Bank"),
        ("HINDUNILVR", "Hindustan Unilever"),
        ("BAJFINANCE", "Bajaj Finance"),
        ("MARUTI", "Maruti Suzuki"),
        ("SUNPHARMA", "Sun Pharma"),
        ("TITAN", "Titan"),
        ("ULTRACEMCO", "UltraTech Cement"),
        ("ASIANPAINT", "Asian Paint"),
        ("WIPRO", "Wipro"),
        ("POWERGRID", "Power Grid Corporation"),
    ]
    query = (search or "").upper()
    rows = [
        {
            "exchange": "NSE",
            "trading_symbol": symbol,
            "groww_symbol": f"NSE-{symbol}",
            "name": name,
            "instrument_type": "EQ",
            "segment": "CASH",
            "series": "EQ",
        }
        for symbol, name in common
        if not query or query in symbol or query in name.upper()
    ]
    return rows[:limit]
