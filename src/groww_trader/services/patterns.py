from __future__ import annotations

from typing import Any

from .indicators import Candle, atr


PATTERN_DETECTORS = (
    "double_bottom",
    "double_top",
    "bull_flag",
    "bear_flag",
    "ascending_triangle",
    "descending_triangle",
    "head_shoulders",
    "inverse_head_shoulders",
    "breakout_high_volume",
    "breakdown_high_volume",
)


def detect_patterns(candles: list[Candle], lookback: int = 60) -> dict[str, Any]:
    """Light-weight pattern detector. Returns one entry per detector with a 0-100 score.

    These are deliberately simple heuristics: they look for the structural footprint of
    each pattern over the last `lookback` bars. Pattern scoring is then fed into the
    Factor pipeline (long+short variants) — not used to take trades directly.
    """
    if len(candles) < 30:
        return {"status": "insufficient", "long": [], "short": []}
    window = candles[-min(lookback, len(candles)) :]
    highs = [c.high for c in window]
    lows = [c.low for c in window]
    closes = [c.close for c in window]
    volumes = [c.volume for c in window]

    detections: list[dict[str, Any]] = []
    detections.extend(_double_bottom(window, highs, lows, closes))
    detections.extend(_double_top(window, highs, lows, closes))
    detections.extend(_flag(window, closes, "bull"))
    detections.extend(_flag(window, closes, "bear"))
    detections.extend(_triangle(window, highs, lows, closes, "ascending"))
    detections.extend(_triangle(window, highs, lows, closes, "descending"))
    detections.extend(_head_shoulders(window, highs, lows, closes, inverted=False))
    detections.extend(_head_shoulders(window, highs, lows, closes, inverted=True))
    detections.extend(_breakout(window, highs, lows, closes, volumes, "up"))
    detections.extend(_breakout(window, highs, lows, closes, volumes, "down"))

    long_score = _aggregate(detections, side="long")
    short_score = _aggregate(detections, side="short")
    return {
        "status": "ok",
        "long_score": long_score,
        "short_score": short_score,
        "detections": detections,
    }


def _aggregate(detections: list[dict[str, Any]], side: str) -> int:
    matched = [det for det in detections if det.get("side") == side]
    if not matched:
        return 0
    best = max(det.get("score", 0) for det in matched)
    return int(min(100, best))


def _double_bottom(window: list[Candle], highs: list[float], lows: list[float], closes: list[float]) -> list[dict[str, Any]]:
    if len(window) < 25:
        return []
    half = len(window) // 2
    left_low = min(lows[:half])
    right_low = min(lows[half:])
    pivot_high = max(highs[:half] + highs[half:])
    if not left_low or not right_low:
        return []
    proximity = abs(left_low - right_low) / max(left_low, 1)
    if proximity > 0.02:
        return []
    if closes[-1] <= pivot_high * 0.97:
        return []
    score = int(max(0, 95 - proximity * 4000))
    return [{"name": "double_bottom", "side": "long", "score": score, "neckline": pivot_high}]


def _double_top(window: list[Candle], highs: list[float], lows: list[float], closes: list[float]) -> list[dict[str, Any]]:
    if len(window) < 25:
        return []
    half = len(window) // 2
    left_high = max(highs[:half])
    right_high = max(highs[half:])
    pivot_low = min(lows[:half] + lows[half:])
    proximity = abs(left_high - right_high) / max(left_high, 1)
    if proximity > 0.02:
        return []
    if closes[-1] >= pivot_low * 1.03:
        return []
    score = int(max(0, 95 - proximity * 4000))
    return [{"name": "double_top", "side": "short", "score": score, "neckline": pivot_low}]


def _flag(window: list[Candle], closes: list[float], direction: str) -> list[dict[str, Any]]:
    if len(window) < 20:
        return []
    pole = closes[-20:-10]
    flag = closes[-10:]
    pole_move = (pole[-1] - pole[0]) / max(pole[0], 1)
    flag_range = (max(flag) - min(flag)) / max(flag[0], 1)
    if direction == "bull" and pole_move > 0.05 and flag_range < 0.04 and closes[-1] >= flag[0]:
        return [{"name": "bull_flag", "side": "long", "score": int(min(100, 60 + pole_move * 200))}]
    if direction == "bear" and pole_move < -0.05 and flag_range < 0.04 and closes[-1] <= flag[0]:
        return [{"name": "bear_flag", "side": "short", "score": int(min(100, 60 + abs(pole_move) * 200))}]
    return []


def _triangle(window: list[Candle], highs: list[float], lows: list[float], closes: list[float], kind: str) -> list[dict[str, Any]]:
    if len(window) < 20:
        return []
    recent = window[-20:]
    recent_highs = [c.high for c in recent]
    recent_lows = [c.low for c in recent]
    high_slope = recent_highs[-1] - recent_highs[0]
    low_slope = recent_lows[-1] - recent_lows[0]
    ceiling = max(recent_highs)
    floor = min(recent_lows)
    if kind == "ascending" and abs(high_slope) / max(ceiling, 1) < 0.01 and low_slope > 0:
        return [{"name": "ascending_triangle", "side": "long", "score": 70, "ceiling": ceiling}]
    if kind == "descending" and high_slope < 0 and abs(low_slope) / max(floor, 1) < 0.01:
        return [{"name": "descending_triangle", "side": "short", "score": 70, "floor": floor}]
    return []


def _head_shoulders(window: list[Candle], highs: list[float], lows: list[float], closes: list[float], inverted: bool) -> list[dict[str, Any]]:
    if len(window) < 21:
        return []
    third = len(window) // 3
    left = window[:third]
    mid = window[third : third * 2]
    right = window[third * 2 :]
    if inverted:
        left_pt = min(c.low for c in left)
        mid_pt = min(c.low for c in mid)
        right_pt = min(c.low for c in right)
        if mid_pt < left_pt and mid_pt < right_pt and abs(left_pt - right_pt) / max(left_pt, 1) < 0.02:
            return [{"name": "inverse_head_shoulders", "side": "long", "score": 78}]
    else:
        left_pt = max(c.high for c in left)
        mid_pt = max(c.high for c in mid)
        right_pt = max(c.high for c in right)
        if mid_pt > left_pt and mid_pt > right_pt and abs(left_pt - right_pt) / max(left_pt, 1) < 0.02:
            return [{"name": "head_shoulders", "side": "short", "score": 78}]
    return []


def _breakout(window: list[Candle], highs: list[float], lows: list[float], closes: list[float], volumes: list[float], direction: str) -> list[dict[str, Any]]:
    if len(window) < 25:
        return []
    base = window[-25:-5]
    recent = window[-5:]
    base_high = max(c.high for c in base)
    base_low = min(c.low for c in base)
    avg_vol = sum(c.volume for c in base) / len(base)
    last_vol = recent[-1].volume
    if direction == "up" and closes[-1] > base_high and last_vol > avg_vol * 1.3:
        return [{"name": "breakout_high_volume", "side": "long", "score": int(min(100, 65 + (last_vol / avg_vol) * 5))}]
    if direction == "down" and closes[-1] < base_low and last_vol > avg_vol * 1.3:
        return [{"name": "breakdown_high_volume", "side": "short", "score": int(min(100, 65 + (last_vol / avg_vol) * 5))}]
    return []
