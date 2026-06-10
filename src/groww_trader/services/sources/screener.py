from __future__ import annotations

import re
from typing import Any

import requests


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

_RATIO_RE = re.compile(
    r'<li[^>]*class="flex flex-space-between"[^>]*>\s*<span[^>]*>\s*<span[^>]*class="name"[^>]*>([^<]+)</span>'
    r'[\s\S]*?<span[^>]*class="number"[^>]*>([^<]+)</span>',
    re.IGNORECASE,
)
_DESCRIPTION_RE = re.compile(r'<div[^>]*class="company-info"[^>]*>([\s\S]+?)</div>', re.IGNORECASE)
_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


class ScreenerClient:
    """Scraper for the Screener.in company page (fundamentals)."""

    base = "https://www.screener.in/company"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fundamentals(self, symbol: str) -> dict[str, Any]:
        for suffix in ("", "/consolidated"):
            url = f"{self.base}/{symbol.upper()}/{suffix.lstrip('/')}".rstrip("/") + "/"
            try:
                response = requests.get(url, headers=_HEADERS, timeout=self.timeout)
            except requests.RequestException:
                continue
            if response.status_code == 200:
                ratios = _parse_ratios(response.text)
                return {
                    "symbol": symbol.upper(),
                    "url": url,
                    "ratios": ratios,
                    "snapshot": _summarize(ratios),
                }
        return {"symbol": symbol.upper(), "url": None, "ratios": {}, "snapshot": {}}


def _parse_ratios(html: str) -> dict[str, str]:
    ratios: dict[str, str] = {}
    for match in _RATIO_RE.finditer(html):
        label = re.sub(r"\s+", " ", match.group(1)).strip().rstrip(":")
        value = re.sub(r"\s+", " ", match.group(2)).strip()
        if label and value:
            ratios[label] = value
    return ratios


def _summarize(ratios: dict[str, str]) -> dict[str, Any]:
    return {
        "market_cap": ratios.get("Market Cap"),
        "current_price": _number(ratios.get("Current Price")),
        "high_low": ratios.get("High / Low"),
        "pe_ratio": _number(ratios.get("Stock P/E")),
        "book_value": _number(ratios.get("Book Value")),
        "dividend_yield": _percent(ratios.get("Dividend Yield")),
        "roce": _percent(ratios.get("ROCE")),
        "roe": _percent(ratios.get("ROE")),
        "face_value": _number(ratios.get("Face Value")),
        "industry_pe": _number(ratios.get("Industry P/E")),
        "debt_to_equity": _number(ratios.get("Debt to equity")),
        "promoter_holding": _percent(ratios.get("Promoter holding")),
    }


def _number(text: str | None) -> float | None:
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _percent(text: str | None) -> float | None:
    if not text:
        return None
    return _number(text.replace("%", ""))
