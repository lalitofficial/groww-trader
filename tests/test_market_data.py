from pathlib import Path

from groww_trader.services.market_data import MarketDataRouter, YahooProvider, _alpha_symbol, _yahoo_symbol
from groww_trader.services.storage import Storage
from groww_trader.settings import AppSettings


class ExplodingGroww:
    def client(self):
        raise AssertionError("Groww market data should not be called")

    def load_instruments(self, *args, **kwargs):
        raise AssertionError("Groww instruments should not be called")


class InstrumentGroww:
    def __init__(self) -> None:
        self.calls = 0

    def load_instruments(self, *args, **kwargs):
        self.calls += 1
        return [
            {
                "exchange": "NSE",
                "trading_symbol": "TCS",
                "groww_symbol": "NSE-TCS",
                "name": "TCS",
                "segment": "CASH",
            }
        ]


def settings(tmp_path: Path, allow_groww: bool = False) -> AppSettings:
    return AppSettings(
        database_path=tmp_path / "db.sqlite3",
        account_capital=500000,
        risk_per_trade_pct=1,
        benchmark_symbol="NSE_NIFTY",
        scan_symbols=("RELIANCE",),
        api_host="127.0.0.1",
        api_port=8000,
        frontend_port=3000,
        market_data_provider_order=("groww",),
        market_data_allow_groww_fallback=allow_groww,
        market_data_daily_ttl_min=360,
        market_data_intraday_ttl_min=15,
        alpha_vantage_api_key=None,
    )


def test_symbol_mapping() -> None:
    assert _yahoo_symbol("RELIANCE") == "RELIANCE.NS"
    assert _yahoo_symbol("NSE_NIFTY") == "^NSEI"
    assert _alpha_symbol("RELIANCE") == "RELIANCE.BSE"


def test_groww_market_data_disabled_by_default(tmp_path: Path) -> None:
    router = MarketDataRouter(Storage(tmp_path / "db.sqlite3"), settings(tmp_path), ExplodingGroww())
    payload = router.safe_historical_candles("RELIANCE", 1440, 30, refresh=True)

    assert payload["candles"] == []
    assert payload["data_source"] == "none"
    assert payload["fallback_chain"] == [{"provider": "groww", "status": "disabled"}]


def test_router_uses_fresh_cache_before_provider(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "db.sqlite3")
    router = MarketDataRouter(storage, settings(tmp_path), ExplodingGroww())
    metadata = {
        "trading_symbol": "RELIANCE",
        "exchange": "NSE",
        "segment": "CASH",
        "interval_minutes": 1440,
        "start_time": "2026-01-01 00:00:00",
        "end_time": "2026-01-02 00:00:00",
        "provider": "yahoo",
        "normalized_symbol": "RELIANCE.NS",
    }
    key = "RELIANCE|NSE|CASH|1440|30d|2026-05-20"
    storage.set_candles(key, metadata, {"candles": [[1, 2, 3, 1, 2, 100]], "source": "yahoo", "normalized_symbol": "RELIANCE.NS"})
    router._cache_key = lambda request: key  # type: ignore[method-assign]

    payload = router.safe_historical_candles("RELIANCE", 1440, 30, refresh=False)

    assert payload["candles"]
    assert payload["data_source"] == "yahoo"
    assert payload["data_freshness"] == "cached"


def test_load_instruments_refresh_uses_groww_service(tmp_path: Path) -> None:
    groww = InstrumentGroww()
    router = MarketDataRouter(Storage(tmp_path / "db.sqlite3"), settings(tmp_path), groww)

    items = router.load_instruments(refresh=True, search="TCS", limit=5)

    assert groww.calls == 1
    assert items[0]["trading_symbol"] == "TCS"
