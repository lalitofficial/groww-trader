from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .indicators import (
    Candle,
    atr,
    macd,
    opening_range,
    rsi,
    session_vwap_series,
    sma,
)


def intraday_analysis(
    candles: list[Candle],
    interval_minutes: int,
    benchmark_return_pct: float | None = None,
) -> dict[str, Any]:
    """Build an intraday view: VWAP state, opening range, ORB triggers, intraday strategies."""
    if not candles:
        return {"status": "empty"}

    closes = [c.close for c in candles]
    last = candles[-1]
    vwap_values = session_vwap_series(candles, interval_minutes)
    vwap = vwap_values[-1] if vwap_values else None
    distance_to_vwap_pct = ((last.close - vwap) / vwap * 100) if vwap else None
    or_bars_count = 3 if interval_minutes <= 5 else (2 if interval_minutes <= 15 else 1)
    orb = opening_range(candles, bars=or_bars_count)
    atr_value = atr(candles)
    atr_pct = (atr_value / last.close) * 100 if atr_value and last.close else None
    ma20 = sma(closes, 20)
    rsi_value = rsi(closes)
    macd_state = macd(closes).get("state")

    strategies = intraday_strategies(candles, vwap, orb, ma20, atr_value, rsi_value, macd_state)

    return {
        "status": "ok",
        "interval_minutes": interval_minutes,
        "session": datetime.fromtimestamp(last.timestamp, tz=timezone.utc).strftime("%Y-%m-%d"),
        "last_price": round(last.close, 2),
        "vwap": round(vwap, 2) if vwap else None,
        "distance_to_vwap_pct": round(distance_to_vwap_pct, 2) if distance_to_vwap_pct is not None else None,
        "vwap_state": _vwap_state(last.close, vwap),
        "opening_range": orb,
        "atr": atr_value,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "ma20": round(ma20, 2) if ma20 else None,
        "rsi": rsi_value,
        "macd_state": macd_state,
        "strategies": strategies,
        "primary_signal": _primary_signal(strategies),
    }


def intraday_strategies(
    candles: list[Candle],
    vwap: float | None,
    orb: dict[str, Any] | None,
    ma20: float | None,
    atr_value: float | None,
    rsi_value: float | None,
    macd_state: str | None,
) -> list[dict[str, Any]]:
    last = candles[-1]
    prev = candles[-2] if len(candles) >= 2 else last
    signals: list[dict[str, Any]] = []

    # Opening Range Breakout / Breakdown
    if orb:
        if orb["state"] == "broken_up" and orb.get("range_pct") and orb["range_pct"] <= 3:
            signals.append({
                "id": "orb_long",
                "name": "Opening Range Breakout",
                "direction": "long",
                "active": True,
                "quality": _quality([
                    vwap and last.close > vwap,
                    macd_state == "bullish",
                    rsi_value and 50 <= rsi_value <= 75,
                ]),
                "trigger": f"Close {last.close} above OR high {orb['or_high']}. Stop OR low {orb['or_low']}.",
                "entry": orb["or_high"],
                "stop": orb["or_low"],
            })
        if orb["state"] == "broken_down" and orb.get("range_pct") and orb["range_pct"] <= 3:
            signals.append({
                "id": "orb_short",
                "name": "Opening Range Breakdown",
                "direction": "short",
                "active": True,
                "quality": _quality([
                    vwap and last.close < vwap,
                    macd_state == "bearish",
                    rsi_value and 25 <= rsi_value <= 50,
                ]),
                "trigger": f"Close {last.close} below OR low {orb['or_low']}. Stop OR high {orb['or_high']}.",
                "entry": orb["or_low"],
                "stop": orb["or_high"],
            })

    # VWAP Reclaim (long): previous bar closed below VWAP, current bar closes above
    if vwap and len(candles) >= 2 and prev.close < vwap <= last.close:
        signals.append({
            "id": "vwap_reclaim_long",
            "name": "VWAP Reclaim Long",
            "direction": "long",
            "active": True,
            "quality": _quality([
                macd_state == "bullish",
                rsi_value and rsi_value > 50,
                ma20 and last.close > ma20,
            ]),
            "trigger": f"Reclaimed VWAP {round(vwap, 2)}; stop {round(min(last.low, prev.low), 2)}.",
            "entry": round(last.close, 2),
            "stop": round(min(last.low, prev.low), 2),
        })

    # VWAP Rejection Short
    if vwap and len(candles) >= 2 and prev.close > vwap >= last.close:
        signals.append({
            "id": "vwap_reject_short",
            "name": "VWAP Rejection Short",
            "direction": "short",
            "active": True,
            "quality": _quality([
                macd_state == "bearish",
                rsi_value and rsi_value < 50,
                ma20 and last.close < ma20,
            ]),
            "trigger": f"Rejected from VWAP {round(vwap, 2)}; stop {round(max(last.high, prev.high), 2)}.",
            "entry": round(last.close, 2),
            "stop": round(max(last.high, prev.high), 2),
        })

    # Trend-day pullback to VWAP
    if vwap and ma20 and last.close > ma20 and abs(last.close - vwap) / vwap <= 0.003 and macd_state == "bullish":
        signals.append({
            "id": "vwap_pullback_long",
            "name": "Pullback to VWAP",
            "direction": "long",
            "active": True,
            "quality": _quality([rsi_value and 45 <= rsi_value <= 65, atr_value is not None]),
            "trigger": f"Price testing VWAP {round(vwap, 2)} in an uptrend.",
            "entry": round(last.close, 2),
            "stop": round(last.close - (atr_value or 0) * 1.5, 2) if atr_value else None,
        })

    return signals


def _vwap_state(price: float, vwap: float | None) -> str:
    if vwap is None:
        return "unknown"
    if price > vwap * 1.002:
        return "above"
    if price < vwap * 0.998:
        return "below"
    return "at"


def _quality(checks: list[Any]) -> int:
    if not checks:
        return 0
    valid = sum(1 for check in checks if bool(check))
    return round((valid / len(checks)) * 100)


def _primary_signal(signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    actionable = [signal for signal in signals if signal.get("active")]
    if not actionable:
        return None
    return max(actionable, key=lambda item: item.get("quality") or 0)
