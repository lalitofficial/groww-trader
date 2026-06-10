from __future__ import annotations

from typing import Any

from groww_trader.settings import AppSettings

from .storage import Storage


class WatchlistService:
    DEFAULT_NAME = "Default"

    def __init__(self, storage: Storage, settings: AppSettings) -> None:
        self.storage = storage
        self.settings = settings

    def ensure_default(self) -> None:
        items = self.storage.list_watchlists()
        if any(item["name"] == self.DEFAULT_NAME for item in items):
            return
        self.storage.upsert_watchlist(
            name=self.DEFAULT_NAME,
            kind="swing",
            symbols=list(self.settings.scan_symbols),
        )
        self.storage.upsert_watchlist(
            name="Intraday",
            kind="intraday",
            symbols=list(self.settings.scan_symbols[:8]),
        )
        self.storage.upsert_watchlist(
            name="Nifty 50",
            kind="swing",
            symbols=list(self.settings.nifty50_symbols),
        )

    def list(self) -> list[dict[str, Any]]:
        self.ensure_default()
        return self.storage.list_watchlists()

    def save(self, name: str, kind: str, symbols: list[str]) -> dict[str, Any]:
        return self.storage.upsert_watchlist(name=name, kind=kind, symbols=symbols)

    def delete(self, name: str) -> bool:
        if name.strip().lower() == self.DEFAULT_NAME.lower():
            return False
        return self.storage.delete_watchlist(name)
