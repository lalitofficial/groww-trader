from __future__ import annotations

import time
from typing import Any

from .indicators import Candle, atr, normalize_candles, session_vwap_series, sma


EVENT_KINDS = (
    "near_stop",
    "near_target",
    "level_break_up",
    "level_break_down",
    "vol_spike",
    "supertrend_flip",
    "vwap_cross_up",
    "vwap_cross_down",
    "orb_break_up",
    "orb_break_down",
    "rsi_extreme",
    "pnl_milestone",
    "daily_loss_threshold",
)


# Cooldown windows so flapping LTP doesn't re-fire the same event repeatedly.
EVENT_COOLDOWN_SECONDS: dict[str, int] = {
    "near_stop": 60,
    "near_target": 60,
    "level_break_up": 180,
    "level_break_down": 180,
    "vol_spike": 60,
    "supertrend_flip": 300,
    "vwap_cross_up": 120,
    "vwap_cross_down": 120,
    "orb_break_up": 600,
    "orb_break_down": 600,
    "rsi_extreme": 600,
    "pnl_milestone": 60,
    "daily_loss_threshold": 600,
}


class EventDetector:
    """Stateful per-symbol event detector.

    `update(symbol, candles, quote, position)` returns a list of newly-fired
    events. Per-symbol per-kind cooldowns prevent duplicate notifications when
    a quote drifts back and forth across a level.
    """

    def __init__(self) -> None:
        self._last_fired: dict[tuple[str, str], float] = {}
        self._last_state: dict[str, dict[str, Any]] = {}

    def update(
        self,
        symbol: str,
        candles: list[Candle],
        quote: dict[str, Any],
        position: dict[str, Any] | None = None,
        levels: list[dict[str, Any]] | None = None,
        orb: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        symbol = symbol.upper()
        if not candles or not quote:
            return []
        last_close = float(quote.get("ltp") or candles[-1].close)
        previous_state = self._last_state.get(symbol) or {}
        events: list[dict[str, Any]] = []

        # --- Near stop / target ---
        if position and position.get("stop_loss"):
            stop = float(position["stop_loss"])
            distance = abs(last_close - stop) / max(last_close, 1)
            if distance <= 0.004:
                events.append(self._fire(symbol, "near_stop", {"price": last_close, "stop": stop, "distance_pct": distance * 100}))
        if position and position.get("target"):
            target = float(position["target"])
            distance = abs(target - last_close) / max(last_close, 1)
            if distance <= 0.004:
                events.append(self._fire(symbol, "near_target", {"price": last_close, "target": target, "distance_pct": distance * 100}))

        # --- Level break (V2 levels) ---
        prev_close = previous_state.get("close") or candles[-2].close if len(candles) >= 2 else last_close
        for level in levels or []:
            line = level.get("level")
            if not line:
                continue
            if prev_close <= line < last_close and level.get("type") == "resistance":
                events.append(self._fire(symbol, "level_break_up", {"price": last_close, "level": line}))
            if prev_close >= line > last_close and level.get("type") == "support":
                events.append(self._fire(symbol, "level_break_down", {"price": last_close, "level": line}))

        # --- Volume spike: last 1-min bar vs 20 avg ---
        if len(candles) >= 21:
            recent_vol = candles[-1].volume
            avg_vol = sum(c.volume for c in candles[-21:-1]) / 20
            if avg_vol and recent_vol >= avg_vol * 1.8:
                events.append(self._fire(symbol, "vol_spike", {"volume": recent_vol, "avg": avg_vol, "ratio": recent_vol / avg_vol}))

        # --- VWAP cross ---
        vwap_values = session_vwap_series(candles, interval_minutes=1)
        if vwap_values:
            vwap_now = vwap_values[-1]
            vwap_prev = vwap_values[-2] if len(vwap_values) >= 2 else vwap_now
            if prev_close < vwap_prev <= last_close:
                events.append(self._fire(symbol, "vwap_cross_up", {"price": last_close, "vwap": vwap_now}))
            if prev_close > vwap_prev >= last_close:
                events.append(self._fire(symbol, "vwap_cross_down", {"price": last_close, "vwap": vwap_now}))

        # --- Opening range break ---
        if orb:
            state = orb.get("state")
            previous_orb_state = previous_state.get("orb_state")
            if state == "broken_up" and previous_orb_state != "broken_up":
                events.append(self._fire(symbol, "orb_break_up", {"or_high": orb.get("or_high")}))
            if state == "broken_down" and previous_orb_state != "broken_down":
                events.append(self._fire(symbol, "orb_break_down", {"or_low": orb.get("or_low")}))

        # --- RSI extreme ---
        rsi_value = previous_state.get("rsi")
        if rsi_value is not None:
            if rsi_value > 75:
                events.append(self._fire(symbol, "rsi_extreme", {"rsi": rsi_value, "side": "overbought"}))
            elif rsi_value < 25:
                events.append(self._fire(symbol, "rsi_extreme", {"rsi": rsi_value, "side": "oversold"}))

        # --- P&L milestone ---
        if position and position.get("entry_price") and position.get("stop_loss"):
            entry = float(position["entry_price"])
            stop = float(position["stop_loss"])
            risk = abs(entry - stop) or entry * 0.01
            r_multiple = (last_close - entry) / risk if position.get("side", "BUY") == "BUY" else (entry - last_close) / risk
            last_milestone = previous_state.get("pnl_r") or 0
            milestone = None
            for level in (-0.5, 1, 2, 3):
                if r_multiple >= level > last_milestone or r_multiple <= level < last_milestone:
                    milestone = level
            if milestone is not None:
                events.append(self._fire(symbol, "pnl_milestone", {"r_multiple": round(r_multiple, 2), "milestone": milestone}))
            previous_state["pnl_r"] = r_multiple

        previous_state["close"] = last_close
        previous_state["orb_state"] = (orb or {}).get("state")
        self._last_state[symbol] = previous_state

        return [event for event in events if event]

    def _fire(self, symbol: str, kind: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        now = time.time()
        key = (symbol, kind)
        cooldown = EVENT_COOLDOWN_SECONDS.get(kind, 60)
        last = self._last_fired.get(key, 0)
        if now - last < cooldown:
            return None
        self._last_fired[key] = now
        return {
            "symbol": symbol,
            "kind": kind,
            "payload": payload,
            "at": now,
        }
