from __future__ import annotations

import threading
import time
from typing import Any

import requests


# Yahoo Finance symbols for the macro tape every Indian intraday trader watches.
GLOBAL_TICKERS: list[tuple[str, str, str]] = [
    ("YM=F", "Dow Futures", "us_futures"),
    ("NQ=F", "Nasdaq Futures", "us_futures"),
    ("^N225", "Nikkei", "asia"),
    ("^HSI", "Hang Seng", "asia"),
    ("000001.SS", "Shanghai", "asia"),
    ("CL=F", "Crude", "commodity"),
    ("GC=F", "Gold", "commodity"),
    ("INR=X", "USD/INR", "fx"),
    ("^NSEI", "Nifty 50", "india"),
    ("^NSEBANK", "Bank Nifty", "india"),
]


class GlobalCuesService:
    """Macro tape across overnight Asia + US futures + commodities + Nifty.

    All sourced from Yahoo's free chart endpoint. Cached 5 min in-process so
    repeated dashboard refreshes don't pound Yahoo.
    """

    CACHE_TTL_SECONDS = 5 * 60

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._expires_at = 0.0

    def snapshot(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if not refresh and time.time() < self._expires_at and self._cache:
                return self._cache
        rows: list[dict[str, Any]] = []
        for symbol, label, group in GLOBAL_TICKERS:
            row = _fetch_quote(symbol)
            row.update({"symbol": symbol, "label": label, "group": group})
            rows.append(row)
        snapshot = {
            "as_of": int(time.time()),
            "items": rows,
            "by_group": _group(rows),
        }
        with self._lock:
            self._cache = snapshot
            self._expires_at = time.time() + self.CACHE_TTL_SECONDS
        return snapshot


def _fetch_quote(symbol: str) -> dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        response = requests.get(
            url,
            params={"interval": "1d", "range": "5d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network defensive
        return {"error": str(exc)}
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        return {"error": "no_chart"}
    meta = result.get("meta") or {}
    quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
    closes = [value for value in (quote.get("close") or []) if value is not None]
    if not closes:
        return {"error": "no_close"}
    last = float(closes[-1])
    previous = float(closes[-2]) if len(closes) >= 2 else float(meta.get("previousClose") or last)
    change = last - previous
    pct = (change / previous * 100) if previous else 0
    return {
        "last": round(last, 4),
        "previous": round(previous, 4),
        "change": round(change, 4),
        "change_pct": round(pct, 2),
        "currency": meta.get("currency"),
    }


def _group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(row.get("group") or "other", []).append(row)
    return out
