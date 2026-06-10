from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from .config import load_settings
from .groww_client import GrowwConfigError, create_groww_client, groww_constant
from .settings import load_app_settings


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = run(args)
    except GrowwConfigError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")

    if result is not None:
        print(json.dumps(_jsonable(result), indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="groww-trader",
        description="Small Groww Trading API helper for intraday workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("profile", help="Fetch the authenticated Groww user profile.")

    quote = subparsers.add_parser("quote", help="Fetch a real-time quote.")
    quote.add_argument("trading_symbol", help="Exchange trading symbol, e.g. RELIANCE.")
    add_market_defaults(quote)

    ltp = subparsers.add_parser("ltp", help="Fetch last traded price for up to 50 symbols.")
    ltp.add_argument("exchange_trading_symbols", nargs="+", help="Symbols like NSE_NIFTY NSE_RELIANCE.")
    ltp.add_argument("--segment", help="Segment such as CASH or FNO.")

    instrument = subparsers.add_parser("instrument", help="Look up an instrument by Groww symbol.")
    instrument.add_argument("groww_symbol", help="Groww symbol, e.g. NSE-RELIANCE.")

    candles = subparsers.add_parser("candles", help="Fetch historical candles.")
    candles.add_argument("trading_symbol", help="Exchange trading symbol, e.g. RELIANCE.")
    candles.add_argument("--start-time", required=True, help="YYYY-MM-DD HH:mm:ss or epoch milliseconds.")
    candles.add_argument("--end-time", required=True, help="YYYY-MM-DD HH:mm:ss or epoch milliseconds.")
    candles.add_argument("--interval", type=int, default=5, help="Interval in minutes. Default: 5.")
    add_market_defaults(candles)

    dashboard = subparsers.add_parser("dashboard", help="Run the FastAPI backend and Next.js dashboard.")
    dashboard.add_argument("--api-only", action="store_true", help="Only run the FastAPI backend.")
    dashboard.add_argument("--frontend-only", action="store_true", help="Only run the Next.js frontend.")

    return parser


def add_market_defaults(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exchange", help="Exchange such as NSE or BSE.")
    parser.add_argument("--segment", help="Segment such as CASH or FNO.")


def run(args: argparse.Namespace) -> Any:
    if args.command == "dashboard":
        return run_dashboard(api_only=args.api_only, frontend_only=args.frontend_only)

    settings = load_settings()
    client = create_groww_client(settings)

    if args.command == "profile":
        return client.get_user_profile()

    if args.command == "quote":
        exchange = groww_constant(client, "EXCHANGE", args.exchange or settings.default_exchange)
        segment = groww_constant(client, "SEGMENT", args.segment or settings.default_segment)
        return client.get_quote(
            exchange=exchange,
            segment=segment,
            trading_symbol=args.trading_symbol.upper(),
        )

    if args.command == "ltp":
        segment = groww_constant(client, "SEGMENT", args.segment or settings.default_segment)
        symbols = tuple(symbol.upper() for symbol in args.exchange_trading_symbols)
        return client.get_ltp(
            segment=segment,
            exchange_trading_symbols=symbols[0] if len(symbols) == 1 else symbols,
        )

    if args.command == "instrument":
        return client.get_instrument_by_groww_symbol(groww_symbol=args.groww_symbol.upper())

    if args.command == "candles":
        exchange = groww_constant(client, "EXCHANGE", args.exchange or settings.default_exchange)
        segment = groww_constant(client, "SEGMENT", args.segment or settings.default_segment)
        return client.get_historical_candle_data(
            trading_symbol=args.trading_symbol.upper(),
            exchange=exchange,
            segment=segment,
            start_time=args.start_time,
            end_time=args.end_time,
            interval_in_minutes=args.interval,
        )

    raise GrowwConfigError(f"Unknown command: {args.command}")


def run_dashboard(api_only: bool = False, frontend_only: bool = False) -> None:
    app_settings = load_app_settings()
    processes: list[subprocess.Popen[str]] = []
    if not frontend_only:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "groww_trader.api.app:app",
                    "--host",
                    app_settings.api_host,
                    "--port",
                    str(app_settings.api_port),
                    "--reload",
                ],
            )
        )
    if not api_only:
        processes.append(
            subprocess.Popen(
                ["npm", "run", "dev", "--", "--port", str(app_settings.frontend_port)],
            )
        )
    print(f"Dashboard: http://localhost:{app_settings.frontend_port}")
    print(f"API: http://{app_settings.api_host}:{app_settings.api_port}/api/health")
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()
    return None


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict(orient="records")
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


if __name__ == "__main__":
    main()
