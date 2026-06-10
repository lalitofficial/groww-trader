from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from groww_trader.config import load_settings
from groww_trader.groww_client import GrowwConfigError, create_groww_client, groww_constant
from groww_trader.settings import AppSettings

from .request_budget import budget
from .storage import Storage


logger = logging.getLogger(__name__)


# Hard policy: Groww is reserved for live account state (positions/orders/holdings/margin).
# Quotes, candles, breadth, depth, fundamentals, and catalysts must come from
# free public sources (NSE/Yahoo/Google/Screener). The guard below makes that
# explicit so a stray import can't sneak Groww back into the market-data path.
GROWW_ALLOWED_USES = {
    "account",
    "positions",
    "orders",
    "holdings",
    "margin",
    "order_detail",
    "instruments",  # one-time bootstrap of the symbol master — heavy but rare
}


class GrowwUsageDeniedError(RuntimeError):
    """Raised when Groww is asked to do something outside the account allowlist."""


def assert_groww_use(use: str) -> None:
    if use not in GROWW_ALLOWED_USES:
        raise GrowwUsageDeniedError(
            f"Groww API is account-only. Refused use '{use}'. "
            f"Use PublicDataService (NSE/Yahoo/Google) for market data instead."
        )


class GrowwDataService:
    def __init__(self, storage: Storage, settings: AppSettings) -> None:
        self.storage = storage
        self.settings = settings

    def client(self) -> Any:
        return create_groww_client(load_settings())

    def load_instruments(self, refresh: bool = False, limit: int = 5000, search: str | None = None) -> list[dict[str, Any]]:
        cached = self.storage.list_instruments(search=search, limit=limit)
        if cached and not refresh:
            return cached
        assert_groww_use("instruments")
        budget().record("groww", "instruments")
        client = self.client()
        df = client.get_all_instruments()
        if isinstance(df, pd.DataFrame):
            records = df.fillna("").to_dict(orient="records")
        else:
            records = list(df or [])
        nse_cash = [
            record
            for record in records
            if str(record.get("exchange", "")).upper() == "NSE"
            and str(record.get("segment", "")).upper() == "CASH"
            and str(record.get("trading_symbol", "")).strip()
        ]
        self.storage.upsert_instruments(nse_cash)
        return self.storage.list_instruments(search=search, limit=limit)

    # ------------------------------------------------------------------
    # Market data methods now refuse to call Groww. They exist for backwards
    # compatibility with `MarketDataRouter`'s `GrowwMarketFallbackProvider`,
    # which is wired to be a no-op when this guard fires.
    # ------------------------------------------------------------------
    def historical_candles(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        logger.warning("Refused Groww historical_candles call; use PublicDataService instead.")
        return {"candles": [], "source": "groww_denied", "error": "Groww blocked for market data; use public sources."}

    def safe_historical_candles(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.historical_candles(*args, **kwargs)

    def ltp(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        logger.warning("Refused Groww ltp call; use PublicDataService.quote() instead.")
        return {"ltp": {}, "source": "groww_denied", "error": "Groww blocked for quotes; use public sources."}
