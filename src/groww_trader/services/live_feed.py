from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

from .events import EventDetector
from .indicators import normalize_candles, opening_range
from .public_data import PublicDataService
from .market_data import MarketDataRouter
from .request_budget import budget
from .session_service import SessionService


# Cadence in seconds for each refresh tier.
ROSTER_CADENCE = 15  # all picks via NSE quote
FOCUS_CADENCE = 5  # the symbol the user has expanded
CANDLES_CADENCE = 60  # Yahoo 1m bars for chart + VWAP
RATE_LIMIT_QUOTES_PER_MIN = 30
RATE_LIMIT_YAHOO_PER_MIN = 60


class TokenBucket:
    """Simple per-minute token bucket so a degraded provider doesn't stop the loop."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_at = time.time() + 60
        self.lock = threading.Lock()

    def take(self, amount: int = 1) -> bool:
        with self.lock:
            now = time.time()
            if now >= self.refill_at:
                self.tokens = self.capacity
                self.refill_at = now + 60
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


class LiveFeed:
    """Background polling loop that powers the Live Desk SSE stream.

    Owned process-wide; consumers connect by calling `subscribe()` and reading
    the asyncio.Queue. The loop self-degrades when rate-limited and pushes a
    `market` event so the UI can show the cooled state.
    """

    def __init__(self, market_data: MarketDataRouter, public_data: PublicDataService, session_service: SessionService) -> None:
        self.market_data = market_data
        self.public_data = public_data
        self.session_service = session_service
        self.event_detector = EventDetector()
        self.subscribers: list[asyncio.Queue[str]] = []
        self.subscribers_lock = threading.Lock()
        self.task: asyncio.Task[None] | None = None
        self.focused_symbol: str | None = None
        self._symbol_last_quote_at: dict[str, float] = {}
        self._symbol_last_candle_at: dict[str, float] = {}
        self._quote_bucket = TokenBucket(RATE_LIMIT_QUOTES_PER_MIN)
        self._yahoo_bucket = TokenBucket(RATE_LIMIT_YAHOO_PER_MIN)
        self._degraded_pushed_at = 0.0

    # -------- subscribers --------
    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        with self.subscribers_lock:
            self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        with self.subscribers_lock:
            try:
                self.subscribers.remove(queue)
            except ValueError:
                pass

    def _broadcast(self, event_name: str, data: dict[str, Any]) -> None:
        message = _sse_format(event_name, data)
        with self.subscribers_lock:
            for queue in list(self.subscribers):
                if queue.full():
                    continue
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    continue

    # -------- focus --------
    def focus(self, symbol: str | None) -> None:
        self.focused_symbol = symbol.upper() if symbol else None

    # -------- lifecycle --------
    async def ensure_running(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        try:
            while True:
                await self._tick()
                await asyncio.sleep(1)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            return
        except Exception:  # pragma: no cover - keep loop alive
            await asyncio.sleep(5)

    async def _tick(self) -> None:
        session = self.session_service.current()
        picks = session.get("picks") or []
        roster = [item["symbol"].upper() for item in picks if item.get("symbol")]
        if not roster:
            return
        now = time.time()
        for symbol in roster:
            await self._refresh_quote(symbol, now)
            await self._refresh_candles(symbol, now)
        if self.focused_symbol and self.focused_symbol in roster:
            await self._refresh_depth(self.focused_symbol)

    async def _refresh_quote(self, symbol: str, now: float) -> None:
        cadence = FOCUS_CADENCE if symbol == self.focused_symbol else ROSTER_CADENCE
        last = self._symbol_last_quote_at.get(symbol, 0)
        if now - last < cadence:
            return
        if not self._quote_bucket.take():
            self._maybe_emit_degraded("quote_rate_limit")
            return
        try:
            quote = self.public_data.quote(symbol)
        except Exception as exc:  # pragma: no cover - defensive
            self._broadcast("market", {"kind": "quote_error", "symbol": symbol, "error": str(exc)})
            return
        if not quote:
            return
        self._symbol_last_quote_at[symbol] = now
        budget().record("live_feed", "quote")
        payload = {
            "symbol": symbol,
            "ltp": quote.get("ltp"),
            "change_pct": quote.get("change_pct"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "vwap": quote.get("vwap"),
            "ts": now,
        }
        self._broadcast("quote", payload)
        await self._maybe_detect_events(symbol, quote)

    async def _refresh_candles(self, symbol: str, now: float) -> None:
        last = self._symbol_last_candle_at.get(symbol, 0)
        if now - last < CANDLES_CADENCE:
            return
        if not self._yahoo_bucket.take():
            self._maybe_emit_degraded("candle_rate_limit")
            return
        try:
            payload = self.market_data.safe_historical_candles(symbol, interval_minutes=5, lookback_days=2, refresh=True)
        except Exception:  # pragma: no cover
            return
        candles = normalize_candles(payload)
        if not candles:
            return
        self._symbol_last_candle_at[symbol] = now
        last_candle = candles[-1]
        self._broadcast(
            "candle_1m",
            {
                "symbol": symbol,
                "ts": last_candle.timestamp,
                "ohlcv": [last_candle.open, last_candle.high, last_candle.low, last_candle.close, last_candle.volume],
            },
        )

    async def _refresh_depth(self, symbol: str) -> None:
        try:
            data = self.public_data.option_chain(symbol)  # option_chain payload contains depth for index/futures
        except Exception:
            data = None
        try:
            raw_quote = self.public_data.nse.quote(symbol)
            depth = (raw_quote.get("raw") or {}).get("marketDeptOrderBook") or {}
        except Exception:
            depth = {}
        if not depth:
            return
        bids = ((depth.get("bid") or [])[:5])
        asks = ((depth.get("ask") or [])[:5])
        total_bid_qty = depth.get("totalBuyQuantity") or 0
        total_ask_qty = depth.get("totalSellQuantity") or 0
        imbalance = None
        if total_ask_qty:
            imbalance = round(total_bid_qty / total_ask_qty, 3)
        self._broadcast(
            "depth",
            {
                "symbol": symbol,
                "bids": [{"price": row.get("price"), "qty": row.get("quantity")} for row in bids],
                "asks": [{"price": row.get("price"), "qty": row.get("quantity")} for row in asks],
                "total_bid_qty": total_bid_qty,
                "total_ask_qty": total_ask_qty,
                "imbalance": imbalance,
            },
        )

    async def _maybe_detect_events(self, symbol: str, quote: dict[str, Any]) -> None:
        try:
            payload = self.market_data.safe_historical_candles(symbol, interval_minutes=5, lookback_days=2, refresh=False)
        except Exception:
            return
        candles = normalize_candles(payload)
        if len(candles) < 5:
            return
        orb = opening_range(candles, bars=3)
        events = self.event_detector.update(symbol=symbol, candles=candles, quote=quote, orb=orb)
        for event in events:
            self.session_service.record_event(event["kind"], symbol=event["symbol"], payload=event["payload"])
            self._broadcast("signal", event)

    def _maybe_emit_degraded(self, kind: str) -> None:
        if time.time() - self._degraded_pushed_at < 60:
            return
        self._degraded_pushed_at = time.time()
        self._broadcast("market", {"kind": kind, "message": "Live feed throttled — rate-limited"})


def _sse_format(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
