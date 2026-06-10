from __future__ import annotations

import re
from typing import Any

import requests


_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}


class GoogleFinanceClient:
    """Lightweight HTML scraper for Google Finance quote pages."""

    base = "https://www.google.com/finance/quote"

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def quote(self, symbol: str, exchange: str = "NSE") -> dict[str, Any]:
        url = f"{self.base}/{symbol.upper()}:{exchange.upper()}"
        response = requests.get(url, headers=_HEADERS, timeout=self.timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"Google Finance returned {response.status_code} for {symbol}")
        html = response.text

        ltp = _extract_currency(html, marker="P6K39c")
        previous_close = _extract_label_value(html, "Previous close")
        day_range = _extract_label_value(html, "Day range")
        year_range = _extract_label_value(html, "Year range")
        market_cap = _extract_label_value(html, "Market cap")
        pe = _extract_label_value(html, "P/E ratio")
        dividend = _extract_label_value(html, "Dividend yield")
        primary_exchange = _extract_label_value(html, "Primary exchange")
        change_pct = _extract_currency(html, marker="JwB6zf")

        return {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "ltp": _to_number(ltp),
            "change_pct": _to_number(change_pct),
            "previous_close": _to_number(previous_close),
            "day_range": day_range,
            "year_range": year_range,
            "market_cap": market_cap,
            "pe_ratio": _to_number(pe),
            "dividend_yield": _to_number(dividend),
            "primary_exchange": primary_exchange,
            "url": url,
        }


def _extract_currency(html: str, marker: str) -> str | None:
    pattern = re.compile(
        rf'class="[^"]*{re.escape(marker)}[^"]*"[^>]*>([^<]+)<',
        re.IGNORECASE,
    )
    match = pattern.search(html)
    return match.group(1).strip() if match else None


def _extract_label_value(html: str, label: str) -> str | None:
    pattern = re.compile(
        rf'>{re.escape(label)}<[^<]*</div>\s*<div[^>]*>([^<]+)<',
        re.IGNORECASE,
    )
    match = pattern.search(html)
    if not match:
        # Sometimes label/value are split across multiple divs; fall back to a wider window.
        loose = re.search(rf'{re.escape(label)}[^<]*</div>[^<]*<div[^>]*>([^<]+)<', html, re.IGNORECASE)
        return loose.group(1).strip() if loose else None
    return match.group(1).strip()


def _to_number(text: str | None) -> float | None:
    if text is None:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None
