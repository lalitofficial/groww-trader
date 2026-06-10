from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


SUPPORTED_INTERVALS = (5, 15, 30, 60, 1440)
INTRADAY_INTERVALS = (5, 15, 30, 60)


@dataclass(frozen=True)
class AppSettings:
    database_path: Path
    account_capital: float
    risk_per_trade_pct: float
    benchmark_symbol: str
    scan_symbols: tuple[str, ...]
    api_host: str
    api_port: int
    frontend_port: int
    market_data_provider_order: tuple[str, ...]
    market_data_allow_groww_fallback: bool
    market_data_daily_ttl_min: int
    market_data_intraday_ttl_min: int
    alpha_vantage_api_key: str | None
    nifty50_symbols: tuple[str, ...] = ()
    sector_index_symbols: tuple[str, ...] = ()
    intraday_leverage: float = 5.0
    intraday_max_daily_loss_pct: float = 3.0
    intraday_max_position_pct: float = 20.0
    intraday_atr_stop_mult: float = 1.5
    intraday_default_timeframe: int = 15
    paper_capital: float = 500000.0
    paper_brokerage_per_trade: float = 20.0
    paper_stt_pct_intraday: float = 0.025
    paper_stt_pct_delivery: float = 0.1
    paper_slippage_bps: float = 5.0
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def load_app_settings() -> AppSettings:
    load_dotenv()
    return AppSettings(
        database_path=Path(os.getenv("GROWW_TRADER_DB", "data/groww_trader.sqlite3")),
        account_capital=float(os.getenv("SWING_ACCOUNT_CAPITAL", "500000")),
        risk_per_trade_pct=float(os.getenv("SWING_RISK_PER_TRADE_PCT", "1.0")),
        benchmark_symbol=os.getenv("SWING_BENCHMARK_SYMBOL", "NSE_NIFTY").strip().upper(),
        scan_symbols=_symbols(os.getenv("SWING_SCAN_SYMBOLS")),
        nifty50_symbols=_symbols(os.getenv("NIFTY50_SYMBOLS"), fallback=_DEFAULT_NIFTY50),
        sector_index_symbols=_symbols(os.getenv("SECTOR_INDEX_SYMBOLS"), fallback=_DEFAULT_SECTOR_INDICES),
        api_host=os.getenv("GROWW_API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("GROWW_API_PORT", "8000")),
        frontend_port=int(os.getenv("GROWW_FRONTEND_PORT", "3000")),
        market_data_provider_order=_symbols(os.getenv("MARKET_DATA_PROVIDER_ORDER") or "yahoo,stooq"),
        market_data_allow_groww_fallback=os.getenv("MARKET_DATA_ALLOW_GROWW_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"},
        market_data_daily_ttl_min=int(os.getenv("MARKET_DATA_DAILY_TTL_MIN", "360")),
        market_data_intraday_ttl_min=int(os.getenv("MARKET_DATA_INTRADAY_TTL_MIN", "5")),
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY") or None,
        intraday_leverage=float(os.getenv("INTRADAY_LEVERAGE", "5")),
        intraday_max_daily_loss_pct=float(os.getenv("INTRADAY_MAX_DAILY_LOSS_PCT", "3.0")),
        intraday_max_position_pct=float(os.getenv("INTRADAY_MAX_POSITION_PCT", "20.0")),
        intraday_atr_stop_mult=float(os.getenv("INTRADAY_ATR_STOP_MULT", "1.5")),
        intraday_default_timeframe=int(os.getenv("INTRADAY_DEFAULT_TIMEFRAME", "15")),
        paper_capital=float(os.getenv("PAPER_CAPITAL", "500000")),
        paper_brokerage_per_trade=float(os.getenv("PAPER_BROKERAGE_PER_TRADE", "20")),
        paper_stt_pct_intraday=float(os.getenv("PAPER_STT_PCT_INTRADAY", "0.025")),
        paper_stt_pct_delivery=float(os.getenv("PAPER_STT_PCT_DELIVERY", "0.1")),
        paper_slippage_bps=float(os.getenv("PAPER_SLIPPAGE_BPS", "5")),
        telegram_bot_token=_clean(os.getenv("TELEGRAM_BOT_TOKEN")),
        telegram_chat_id=_clean(os.getenv("TELEGRAM_CHAT_ID")),
    )


def _symbols(raw: str | None, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    if not raw:
        if fallback:
            return fallback
        raw = "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK"
    return tuple(symbol.strip().upper() for symbol in raw.split(",") if symbol.strip())


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


_DEFAULT_NIFTY50: tuple[str, ...] = (
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "BAJFINANCE", "KOTAKBANK", "LT", "AXISBANK", "MARUTI",
    "ASIANPAINT", "SUNPHARMA", "TITAN", "ULTRACEMCO", "BAJAJFINSV", "WIPRO",
    "NESTLEIND", "ONGC", "POWERGRID", "NTPC", "TATAMOTORS", "TATASTEEL", "JSWSTEEL",
    "HCLTECH", "TECHM", "M&M", "ADANIENT", "ADANIPORTS", "GRASIM", "CIPLA",
    "DRREDDY", "DIVISLAB", "BRITANNIA", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO",
    "COALINDIA", "BPCL", "IOC", "TATACONSUM", "INDUSINDBK", "HDFCLIFE", "SBILIFE",
    "APOLLOHOSP", "UPL", "HINDALCO",
)

_DEFAULT_SECTOR_INDICES: tuple[str, ...] = (
    "NSE_BANKNIFTY", "NSE_NIFTYIT", "NSE_NIFTYAUTO", "NSE_NIFTYFMCG",
    "NSE_NIFTYPHARMA", "NSE_NIFTYMETAL", "NSE_NIFTYENERGY", "NSE_NIFTYREALTY",
    "NSE_NIFTYPSUBANK", "NSE_NIFTYFINSERVICE",
)
