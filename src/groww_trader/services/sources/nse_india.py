from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import quote

import requests


NSE_BASE = "https://www.nseindia.com"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": f"{NSE_BASE}/",
    "Connection": "keep-alive",
}


class NSEIndiaClient:
    """Thin direct client over the NSE India public website JSON endpoints.

    NSE requires a real browser cookie set to be obtained from the homepage before
    its API endpoints will respond with JSON. We bootstrap the session once per
    process and refresh on stale cookies.
    """

    def __init__(self, timeout: float = 8.0, cookie_ttl_seconds: int = 1800) -> None:
        self.session = requests.Session()
        self.session.headers.update(_BROWSER_HEADERS)
        self.timeout = timeout
        self.cookie_ttl_seconds = cookie_ttl_seconds
        self._cookie_refreshed_at = 0.0
        self._lock = threading.Lock()

    # -------- Public quote / OHLC --------
    def quote(self, symbol: str) -> dict[str, Any]:
        data = self._get_json(f"/api/quote-equity?symbol={quote(symbol.upper())}")
        info = data.get("info") or {}
        price = data.get("priceInfo") or {}
        prepop = data.get("preOpenMarket") or {}
        meta = data.get("metadata") or {}
        return {
            "symbol": info.get("symbol") or symbol.upper(),
            "company": info.get("companyName"),
            "industry": info.get("industry"),
            "isin": info.get("isin"),
            "ltp": price.get("lastPrice"),
            "open": price.get("open"),
            "close": price.get("close"),
            "previous_close": price.get("previousClose"),
            "high": (price.get("intraDayHighLow") or {}).get("max"),
            "low": (price.get("intraDayHighLow") or {}).get("min"),
            "vwap": price.get("vwap"),
            "lower_circuit": price.get("lowerCP"),
            "upper_circuit": price.get("upperCP"),
            "change_pct": price.get("pChange"),
            "change_abs": price.get("change"),
            "week52_high": (price.get("weekHighLow") or {}).get("max"),
            "week52_low": (price.get("weekHighLow") or {}).get("min"),
            "listing_date": meta.get("listingDate"),
            "face_value": (data.get("securityInfo") or {}).get("faceValue"),
            "pre_open_price": prepop.get("finalPrice"),
            "raw": data,
        }

    def trade_info(self, symbol: str) -> dict[str, Any]:
        data = self._get_json(f"/api/quote-equity?symbol={quote(symbol.upper())}&section=trade_info")
        market = data.get("marketDeptOrderBook") or {}
        delivery = data.get("securityWiseDP") or {}
        return {
            "symbol": symbol.upper(),
            "total_traded_value": (market.get("tradeInfo") or {}).get("totalTradedValue"),
            "total_traded_volume": (market.get("tradeInfo") or {}).get("totalTradedVolume"),
            "delivery_quantity": delivery.get("deliveryQuantity"),
            "delivery_pct": delivery.get("deliveryToTradedQuantity"),
            "raw": data,
        }

    # -------- Breadth / market state --------
    def market_status(self) -> dict[str, Any]:
        return self._get_json("/api/marketStatus")

    def variations(self, index: str = "gainers") -> list[dict[str, Any]]:
        # index in {gainers, losers, mostActive, volume_gainers, ...}
        data = self._get_json(f"/api/live-analysis-variations?index={quote(index)}")
        for key in ("NIFTY", "NIFTY50", "BANKNIFTY", "data"):
            value = data.get(key)
            if isinstance(value, dict) and isinstance(value.get("data"), list):
                return [_compact_breadth_row(item) for item in value["data"]]
            if isinstance(value, list):
                return [_compact_breadth_row(item) for item in value]
        return []

    def fii_dii(self) -> list[dict[str, Any]]:
        data = self._get_json("/api/fiidiiTradeReact")
        if isinstance(data, list):
            return data
        return data.get("data") or []

    # -------- Corporate filings --------
    def corporate_announcements(self, symbol: str | None = None, lookback_days: int = 15) -> list[dict[str, Any]]:
        endpoint = "/api/corporate-announcements?index=equities"
        if symbol:
            endpoint += f"&symbol={quote(symbol.upper())}"
        data = self._get_json(endpoint)
        items = data if isinstance(data, list) else (data.get("data") or [])
        rows = []
        for item in items[:50]:
            rows.append(
                {
                    "symbol": item.get("symbol") or symbol,
                    "subject": item.get("desc") or item.get("subject"),
                    "details": item.get("attchmntText") or item.get("smIndustry"),
                    "broadcast_at": item.get("an_dt") or item.get("sort_date"),
                    "file_url": item.get("attchmntFile"),
                    "exchange": "NSE",
                }
            )
        return rows

    # -------- Option chain --------
    def option_chain(self, symbol: str) -> dict[str, Any]:
        data = self._get_json(f"/api/option-chain-equities?symbol={quote(symbol.upper())}")
        records = (data.get("records") or {}).get("data") or []
        if not records:
            return {"symbol": symbol.upper(), "strikes": [], "summary": {}}
        underlying = (data.get("records") or {}).get("underlyingValue")
        ce_oi = 0
        pe_oi = 0
        max_pain_strike = None
        max_oi_strike_ce = None
        max_oi_ce = 0
        max_oi_strike_pe = None
        max_oi_pe = 0
        strikes: list[dict[str, Any]] = []
        for row in records:
            strike = row.get("strikePrice")
            ce = row.get("CE") or {}
            pe = row.get("PE") or {}
            ce_oi_value = ce.get("openInterest") or 0
            pe_oi_value = pe.get("openInterest") or 0
            ce_oi += ce_oi_value
            pe_oi += pe_oi_value
            if ce_oi_value > max_oi_ce:
                max_oi_ce = ce_oi_value
                max_oi_strike_ce = strike
            if pe_oi_value > max_oi_pe:
                max_oi_pe = pe_oi_value
                max_oi_strike_pe = strike
            strikes.append(
                {
                    "strike": strike,
                    "ce_oi": ce_oi_value,
                    "ce_oi_change": ce.get("changeinOpenInterest"),
                    "ce_iv": ce.get("impliedVolatility"),
                    "ce_ltp": ce.get("lastPrice"),
                    "pe_oi": pe_oi_value,
                    "pe_oi_change": pe.get("changeinOpenInterest"),
                    "pe_iv": pe.get("impliedVolatility"),
                    "pe_ltp": pe.get("lastPrice"),
                }
            )
        pcr = round(pe_oi / ce_oi, 3) if ce_oi else None
        return {
            "symbol": symbol.upper(),
            "underlying": underlying,
            "strikes": strikes,
            "summary": {
                "total_ce_oi": ce_oi,
                "total_pe_oi": pe_oi,
                "pcr": pcr,
                "max_ce_oi_strike": max_oi_strike_ce,
                "max_pe_oi_strike": max_oi_strike_pe,
            },
        }

    # -------- Internals --------
    def _get_json(self, path: str) -> Any:
        url = f"{NSE_BASE}{path}"
        for attempt in range(2):
            self._ensure_session(force=attempt == 1)
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    text = response.text.strip()
                    if not text:
                        return {}
                    return response.json()
                if response.status_code in {401, 403, 419}:
                    # session expired
                    continue
                response.raise_for_status()
            except (requests.RequestException, ValueError) as exc:
                if attempt == 1:
                    raise
                continue
        return {}

    def _ensure_session(self, force: bool = False) -> None:
        with self._lock:
            if not force and (time.time() - self._cookie_refreshed_at) < self.cookie_ttl_seconds:
                return
            try:
                self.session.get(NSE_BASE + "/", timeout=self.timeout)
                self.session.get(NSE_BASE + "/option-chain", timeout=self.timeout)
                self._cookie_refreshed_at = time.time()
            except requests.RequestException:
                # leave cookie state as is; subsequent retries will hit this again
                self._cookie_refreshed_at = 0.0


def _compact_breadth_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": item.get("symbol"),
        "ltp": item.get("ltp") or item.get("lastPrice"),
        "change_pct": item.get("perChange") or item.get("netPrice"),
        "change_abs": item.get("netPrice") or item.get("change"),
        "volume": item.get("tradedQuantity") or item.get("totalTradedVolume"),
        "value": item.get("turnover") or item.get("totalTradedValue"),
    }
