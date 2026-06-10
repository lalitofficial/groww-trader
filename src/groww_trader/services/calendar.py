from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}


class CalendarService:
    """Daily calendar: NSE results-today + F&O ban + corporate actions.

    NSE serves these as JSON; we cache for 30 minutes per session day.
    """

    CACHE_TTL_SECONDS = 30 * 60

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._expires_at = 0.0

    def snapshot(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if not refresh and time.time() < self._expires_at and self._cache:
                return self._cache
        snapshot = {
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fno_ban": self._fno_ban(),
            "results_today": self._results_today(),
            "corporate_actions": self._corporate_actions(),
        }
        with self._lock:
            self._cache = snapshot
            self._expires_at = time.time() + self.CACHE_TTL_SECONDS
        return snapshot

    def is_in_fno_ban(self, symbol: str) -> bool:
        symbol = symbol.upper()
        return symbol in {item.get("symbol") for item in self.snapshot().get("fno_ban") or []}

    def has_results_today(self, symbol: str) -> bool:
        symbol = symbol.upper()
        return symbol in {item.get("symbol") for item in self.snapshot().get("results_today") or []}

    def _fno_ban(self) -> list[dict[str, Any]]:
        url = "https://www.nseindia.com/api/fno-participant-wise-trading-data"
        # The "ban list" lives behind a different route on NSE; we fall back to the
        # CSV daily file which is also public.
        csv_url = "https://nsearchives.nseindia.com/content/fo/fo_secban.csv"
        try:
            response = requests.get(csv_url, headers=_HEADERS, timeout=8)
            if response.status_code == 200:
                lines = [line.strip() for line in response.text.splitlines() if line.strip()]
                rows = [
                    {"symbol": parts[1].upper(), "status": "banned"}
                    for line in lines[1:]
                    for parts in [line.split(",")]
                    if len(parts) >= 2
                ]
                return rows
        except Exception:
            pass
        return []

    def _results_today(self) -> list[dict[str, Any]]:
        url = "https://www.nseindia.com/api/corporates-financial-results"
        params = {"index": "equities", "from_date": _today(), "to_date": _today(), "period": "Quarterly"}
        try:
            response = requests.get(url, params=params, headers=_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data if isinstance(data, list) else (data.get("data") or [])
                return [
                    {
                        "symbol": item.get("symbol"),
                        "company": item.get("companyName") or item.get("company"),
                        "broadcast_at": item.get("broadCastDate") or item.get("date"),
                        "period": item.get("relatingTo"),
                    }
                    for item in items
                ]
        except Exception:
            pass
        return []

    def _corporate_actions(self) -> list[dict[str, Any]]:
        url = "https://www.nseindia.com/api/corporates-corporateActions"
        try:
            response = requests.get(url, params={"index": "equities"}, headers=_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data if isinstance(data, list) else (data.get("data") or [])
                return [
                    {
                        "symbol": item.get("symbol"),
                        "purpose": item.get("subject") or item.get("purpose"),
                        "ex_date": item.get("exDate"),
                        "record_date": item.get("recDate"),
                    }
                    for item in items[:40]
                ]
        except Exception:
            pass
        return []


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%d-%m-%Y")
