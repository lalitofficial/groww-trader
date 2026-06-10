from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .request_budget import budget
from .sources import GoogleFinanceClient, NSEIndiaClient, ScreenerClient


class _TtlCache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, ttl: float) -> Any | None:
        with self.lock:
            entry = self.data.get(key)
            if not entry:
                return None
            timestamp, value = entry
            if time.time() - timestamp > ttl:
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self.lock:
            self.data[key] = (time.time(), value)


class PublicDataService:
    """Aggregates free public market sources behind a TTL cache.

    This is what consumers should use instead of hitting Groww for things like
    quotes, breadth, FII/DII, corporate filings, fundamentals, and option chains.
    """

    def __init__(
        self,
        nse: NSEIndiaClient | None = None,
        google: GoogleFinanceClient | None = None,
        screener: ScreenerClient | None = None,
    ) -> None:
        self.nse = nse or NSEIndiaClient()
        self.google = google or GoogleFinanceClient()
        self.screener = screener or ScreenerClient()
        self._cache = _TtlCache()
        self._ttls = {
            "quote": 30,
            "trade_info": 60,
            "fundamentals": 6 * 3600,
            "market_status": 30,
            "breadth": 60,
            "fii_dii": 6 * 3600,
            "announcements": 15 * 60,
            "option_chain": 120,
        }

    # -------- Quotes (NSE -> Google) --------
    def quote(self, symbol: str) -> dict[str, Any] | None:
        return self._cached_chain(
            cache_key=f"quote:{symbol.upper()}",
            ttl=self._ttls["quote"],
            providers=[
                ("nse", lambda: self.nse.quote(symbol)),
                ("google_finance", lambda: self.google.quote(symbol)),
            ],
        )

    def trade_info(self, symbol: str) -> dict[str, Any] | None:
        return self._cached_chain(
            cache_key=f"trade_info:{symbol.upper()}",
            ttl=self._ttls["trade_info"],
            providers=[("nse", lambda: self.nse.trade_info(symbol))],
        )

    # -------- Breadth & flows --------
    def market_status(self) -> dict[str, Any] | None:
        return self._cached_chain(
            cache_key="market_status",
            ttl=self._ttls["market_status"],
            providers=[("nse", self.nse.market_status)],
        )

    def breadth(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for index in ("gainers", "losers", "mostActive"):
            payload = self._cached_chain(
                cache_key=f"breadth:{index}",
                ttl=self._ttls["breadth"],
                providers=[("nse", lambda idx=index: self.nse.variations(idx))],
            )
            result[index] = payload or []
        return result

    def fii_dii(self) -> list[dict[str, Any]]:
        return (
            self._cached_chain(
                cache_key="fii_dii",
                ttl=self._ttls["fii_dii"],
                providers=[("nse", self.nse.fii_dii)],
            )
            or []
        )

    # -------- Filings --------
    def corporate_announcements(self, symbol: str | None = None) -> list[dict[str, Any]]:
        key = f"announcements:{(symbol or '_all').upper()}"
        return (
            self._cached_chain(
                cache_key=key,
                ttl=self._ttls["announcements"],
                providers=[("nse", lambda: self.nse.corporate_announcements(symbol=symbol))],
            )
            or []
        )

    # -------- Fundamentals --------
    def fundamentals(self, symbol: str) -> dict[str, Any] | None:
        return self._cached_chain(
            cache_key=f"fundamentals:{symbol.upper()}",
            ttl=self._ttls["fundamentals"],
            providers=[("screener", lambda: self.screener.fundamentals(symbol))],
        )

    # -------- Option chain --------
    def option_chain(self, symbol: str) -> dict[str, Any] | None:
        return self._cached_chain(
            cache_key=f"option_chain:{symbol.upper()}",
            ttl=self._ttls["option_chain"],
            providers=[("nse", lambda: self.nse.option_chain(symbol))],
        )

    # -------- Health --------
    def usage(self) -> dict[str, Any]:
        return budget().snapshot()

    # -------- Internals --------
    def _cached_chain(
        self,
        cache_key: str,
        ttl: float,
        providers: list[tuple[str, Callable[[], Any]]],
    ) -> Any | None:
        cached = self._cache.get(cache_key, ttl)
        if cached is not None:
            budget().record("cache", cache_key.split(":", 1)[0])
            return cached
        last_error: Exception | None = None
        for provider_name, fn in providers:
            try:
                budget().record(provider_name, cache_key.split(":", 1)[0])
                value = fn()
                if value:
                    self._cache.set(cache_key, value)
                    return value
            except Exception as exc:  # pragma: no cover - defensive scrape failure
                last_error = exc
        if last_error:
            return None
        return None
