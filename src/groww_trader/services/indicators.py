from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Any

try:  # Optional audited TA dependency; local fallbacks below keep the API stable.
    import pandas as pd
    import pandas_ta_classic as ta
except Exception:  # pragma: no cover - exercised when optional deps are unavailable
    pd = None
    ta = None


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def normalize_candles(payload: dict[str, Any]) -> list[Candle]:
    candles = payload.get("candles") or []
    normalized: list[Candle] = []
    for item in candles:
        if len(item) >= 6:
            normalized.append(
                Candle(
                    timestamp=int(item[0]),
                    open=float(item[1]),
                    high=float(item[2]),
                    low=float(item[3]),
                    close=float(item[4]),
                    volume=_float_or_zero(item[5]),
                )
            )
    return normalized


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return mean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-period - 1 : -1], values[-period:]):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(values: list[float]) -> dict[str, float | None | str]:
    if len(values) < 35:
        return {"macd": None, "signal": None, "histogram": None, "state": "insufficient"}
    fast = ema_series(values, 12)
    slow = ema_series(values, 26)
    line = [f - s for f, s in zip(fast[-len(slow) :], slow)]
    signal_series = ema_series(line, 9)
    macd_value = line[-1]
    signal = signal_series[-1]
    histogram = macd_value - signal
    state = "bullish" if macd_value > signal and histogram > 0 else "bearish" if macd_value < signal else "neutral"
    return {
        "macd": round(macd_value, 2),
        "signal": round(signal, 2),
        "histogram": round(histogram, 2),
        "state": state,
    }


def support_resistance(candles: list[Candle], lookback: int = 60) -> dict[str, float | None]:
    if not candles:
        return {"support": None, "resistance": None}
    window = candles[-lookback:]
    last_close = window[-1].close
    lows = sorted({round(c.low, 2) for c in window if c.low <= last_close})
    highs = sorted({round(c.high, 2) for c in window if c.high >= last_close})
    return {
        "support": lows[-1] if lows else min(c.low for c in window),
        "resistance": highs[0] if highs else max(c.high for c in window),
    }


def support_resistance_levels(candles: list[Candle], lookback: int = 120, bucket_pct: float = 0.006) -> list[dict[str, Any]]:
    if not candles:
        return []
    window = candles[-lookback:]
    last_close = window[-1].close
    pivots: list[tuple[float, str, float]] = []
    for index in range(2, len(window) - 2):
        candle = window[index]
        before = window[index - 2 : index]
        after = window[index + 1 : index + 3]
        if candle.high >= max([c.high for c in before + after]):
            pivots.append((candle.high, "resistance", candle.volume))
        if candle.low <= min([c.low for c in before + after]):
            pivots.append((candle.low, "support", candle.volume))
    if not pivots:
        pivots = [(c.low, "support", c.volume) for c in window] + [(c.high, "resistance", c.volume) for c in window]

    clusters: list[dict[str, Any]] = []
    for price, pivot_type, volume in sorted(pivots, key=lambda item: item[0]):
        matched = None
        for cluster in clusters:
            if abs(price - cluster["level"]) / cluster["level"] <= bucket_pct:
                matched = cluster
                break
        if matched:
            matched["prices"].append(price)
            matched["touches"] += 1
            matched["volume"] += volume
            matched["level"] = mean(matched["prices"])
            matched["types"].append(pivot_type)
        else:
            clusters.append({"level": price, "prices": [price], "touches": 1, "volume": volume, "types": [pivot_type]})

    levels: list[dict[str, Any]] = []
    avg_volume = mean([c.volume for c in window]) or 1
    for cluster in clusters:
        level = round(cluster["level"], 2)
        level_type = "support" if level < last_close else "resistance"
        distance_pct = round(((level - last_close) / last_close) * 100, 2) if last_close else None
        last_touch_index = _last_touch_index(window, level, bucket_pct)
        recency_score = _recency_score(len(window), last_touch_index)
        volume_score = min(100, round((cluster["volume"] / avg_volume) * 10))
        strength = min(100, round((cluster["touches"] * 18) + ((cluster["volume"] / avg_volume) * 2)))
        levels.append(
            {
                "level": level,
                "type": level_type,
                "distance_pct": distance_pct,
                "touches": cluster["touches"],
                "strength": strength,
                "last_touch_at": window[last_touch_index].timestamp if last_touch_index is not None else None,
                "recency_score": recency_score,
                "volume_score": volume_score,
                "breakout_state": _breakout_state(window, level, level_type),
            }
        )
    nearby = sorted(levels, key=lambda item: (abs(item["distance_pct"] or 999), -item["strength"]))
    supports = sorted([item for item in nearby if item["type"] == "support"], key=lambda item: abs(item["distance_pct"] or 999))[:5]
    resistances = sorted([item for item in nearby if item["type"] == "resistance"], key=lambda item: abs(item["distance_pct"] or 999))[:5]
    return sorted(supports + resistances, key=lambda item: item["level"])


def analyze_candles(
    candles: list[Candle],
    benchmark_return_pct: float | None = None,
    timeframe: str = "daily",
    interval_minutes: int | None = None,
) -> dict[str, Any]:
    if not candles:
        return {"status": "empty"}
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    last = candles[-1]
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)
    ma200 = sma(closes, 200)
    levels = support_resistance(candles)
    level_list = support_resistance_levels(candles)
    supports_v2 = sorted([item for item in level_list if item["type"] == "support"], key=lambda item: abs(item.get("distance_pct") or 999))
    resistances_v2 = sorted([item for item in level_list if item["type"] == "resistance"], key=lambda item: abs(item.get("distance_pct") or 999))
    nearest_support = supports_v2[0] if supports_v2 else None
    nearest_resistance = resistances_v2[0] if resistances_v2 else None
    # Prefer V2 levels (pivots+clusters) for the scalar support/resistance used by
    # downstream consumers; fall back to the simple window levels only if V2 is empty.
    support_value = nearest_support["level"] if nearest_support else levels["support"]
    resistance_value = nearest_resistance["level"] if nearest_resistance else levels["resistance"]
    volume_avg20 = sma(volumes, 20)
    stock_return = _return_pct(closes, 20)
    relative_strength = None if benchmark_return_pct is None or stock_return is None else round(stock_return - benchmark_return_pct, 2)
    trend_state = classify_trend(last.close, ma20, ma50, ma200)
    rr = risk_reward(last.close, support_value, resistance_value)
    score = score_setup(trend_state, rsi(closes), macd(closes)["state"], volume_expansion(last.volume, volume_avg20), relative_strength, rr)
    predictive = predictive_profile(candles, benchmark_return_pct)
    strategies = strategy_signals(candles, {"support": support_value, "resistance": resistance_value}, ma20, ma50, ma200, rsi(closes), macd(closes), rr)
    alpha = alpha_factors(candles, benchmark_return_pct, volume_avg20)
    indicators = indicator_bundle(candles)
    result = {
        "status": "ok",
        "timeframe": timeframe,
        "interval_minutes": interval_minutes,
        "last_price": round(last.close, 2),
        "ma20": _round(ma20),
        "ma50": _round(ma50),
        "ma200": _round(ma200),
        "rsi": rsi(closes),
        "macd": macd(closes),
        "volume": round(last.volume, 2),
        "volume_avg20": _round(volume_avg20),
        "volume_expansion": volume_expansion(last.volume, volume_avg20),
        "support": support_value,
        "resistance": resistance_value,
        "levels": level_list,
        "levels_v2": level_list,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "major_supports": sorted(supports_v2, key=lambda item: item["strength"], reverse=True)[:3],
        "major_resistances": sorted(resistances_v2, key=lambda item: item["strength"], reverse=True)[:3],
        "risk_reward": rr,
        "trend_state": trend_state,
        "return_20d_pct": stock_return,
        "relative_strength": relative_strength,
        "technical_score": score,
        "predictive": predictive,
        "alpha_factors": alpha,
        "strategies": strategies,
        "regime": market_regime(candles, ma20, ma50, ma200),
        "indicators": indicators,
    }
    result["trade_plan"] = trade_plan(result, candles)
    result["setup_mode_summary"] = setup_mode_summary(result)
    return result


def indicator_bundle(candles: list[Candle]) -> dict[str, Any]:
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    atr_value = atr(candles)
    bb = bollinger_bands(closes)
    kc = keltner_channels(candles)
    squeeze = squeeze_state(bb, kc)
    st = supertrend(candles)
    vwap_values = vwap_series(candles)
    stoch = stochastic_rsi(closes)
    div = divergence_signals(candles, rsi_series(closes))

    return {
        "atr": atr_value,
        "atr_pct": round((atr_value / closes[-1]) * 100, 2) if atr_value and closes and closes[-1] else None,
        "supertrend": st[-1] if st else None,
        "bollinger_bands": bb[-1] if bb else None,
        "keltner_channel": kc[-1] if kc else None,
        "squeeze": squeeze[-1] if squeeze else None,
        "vwap": _round(vwap_values[-1]) if vwap_values else None,
        "stochastic_rsi": stoch[-1] if stoch else None,
        "divergence": div,
        "volume_zscore": _round(zscore(volumes[-60:], volumes[-1])) if volumes else None,
        "source": "pandas-ta-classic" if ta is not None else "fallback",
    }


def bollinger_bands(values: list[float], period: int = 20, deviations: float = 2.0) -> list[dict[str, float | None]]:
    if not values:
        return []
    if pd is not None and ta is not None and len(values) >= period:
        series = pd.Series(values)
        frame = ta.bbands(series, length=period, std=deviations)
        if frame is not None:
            cols = list(frame.columns)
            lower_col = next((c for c in cols if c.startswith("BBL_")), None)
            mid_col = next((c for c in cols if c.startswith("BBM_")), None)
            upper_col = next((c for c in cols if c.startswith("BBU_")), None)
            return [
                {"lower": _round(row[lower_col]) if lower_col else None, "middle": _round(row[mid_col]) if mid_col else None, "upper": _round(row[upper_col]) if upper_col else None}
                for _, row in frame.iterrows()
            ]
    result: list[dict[str, float | None]] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append({"lower": None, "middle": None, "upper": None})
            continue
        window = values[index + 1 - period : index + 1]
        mid = mean(window)
        dev = _stddev(window)
        result.append({"lower": _round(mid - deviations * dev), "middle": _round(mid), "upper": _round(mid + deviations * dev)})
    return result


def keltner_channels(candles: list[Candle], period: int = 20, multiplier: float = 1.5) -> list[dict[str, float | None]]:
    closes = [c.close for c in candles]
    ema_values = ema_series(closes, period)
    result: list[dict[str, float | None]] = []
    for index, candle in enumerate(candles):
        if index + 1 < period:
            result.append({"lower": None, "middle": None, "upper": None})
            continue
        atr_value = atr(candles[: index + 1], period)
        middle = ema_values[index]
        result.append({"lower": _round(middle - multiplier * (atr_value or 0)), "middle": _round(middle), "upper": _round(middle + multiplier * (atr_value or 0))})
    return result


def squeeze_state(bb: list[dict[str, float | None]], kc: list[dict[str, float | None]]) -> list[dict[str, Any]]:
    result = []
    for band, channel in zip(bb, kc):
        lower_bb, upper_bb = band.get("lower"), band.get("upper")
        lower_kc, upper_kc = channel.get("lower"), channel.get("upper")
        on = bool(lower_bb and upper_bb and lower_kc and upper_kc and lower_bb > lower_kc and upper_bb < upper_kc)
        result.append({"on": on, "state": "squeeze_on" if on else "released" if lower_bb and upper_bb else "insufficient"})
    return result


def supertrend(candles: list[Candle], period: int = 10, multiplier: float = 3.0) -> list[dict[str, Any]]:
    if len(candles) < period + 1:
        return []
    final_upper: list[float | None] = []
    final_lower: list[float | None] = []
    trend: list[dict[str, Any]] = []
    for index, candle in enumerate(candles):
        hl2 = (candle.high + candle.low) / 2
        atr_value = atr(candles[: index + 1], period)
        if atr_value is None:
            final_upper.append(None)
            final_lower.append(None)
            trend.append({"value": None, "direction": "insufficient"})
            continue
        basic_upper = hl2 + multiplier * atr_value
        basic_lower = hl2 - multiplier * atr_value
        prev_upper = final_upper[-1]
        prev_lower = final_lower[-1]
        prev_close = candles[index - 1].close if index > 0 else candle.close
        upper = basic_upper if prev_upper is None or basic_upper < prev_upper or prev_close > prev_upper else prev_upper
        lower = basic_lower if prev_lower is None or basic_lower > prev_lower or prev_close < prev_lower else prev_lower
        final_upper.append(upper)
        final_lower.append(lower)
        prev_trend = trend[-1] if trend else {"direction": "bullish", "value": lower}
        if prev_trend["direction"] == "bearish" and candle.close > upper:
            direction = "bullish"
        elif prev_trend["direction"] == "bullish" and candle.close < lower:
            direction = "bearish"
        else:
            direction = prev_trend["direction"] if prev_trend["direction"] != "insufficient" else "bullish"
        trend.append({"value": _round(lower if direction == "bullish" else upper), "direction": direction})
    return trend


def vwap_series(candles: list[Candle]) -> list[float]:
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    result = []
    for candle in candles:
        typical = (candle.high + candle.low + candle.close) / 3
        cumulative_price_volume += typical * candle.volume
        cumulative_volume += candle.volume
        result.append(cumulative_price_volume / cumulative_volume if cumulative_volume else typical)
    return result


def session_vwap_series(candles: list[Candle], interval_minutes: int | None = None) -> list[float]:
    """VWAP that resets each trading session (UTC date boundary)."""
    if not candles:
        return []
    if interval_minutes and interval_minutes >= 1440:
        return vwap_series(candles)
    from datetime import datetime, timezone

    result: list[float] = []
    current_session: str | None = None
    cum_pv = 0.0
    cum_vol = 0.0
    for candle in candles:
        session = datetime.fromtimestamp(candle.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
        if session != current_session:
            current_session = session
            cum_pv = 0.0
            cum_vol = 0.0
        typical = (candle.high + candle.low + candle.close) / 3
        cum_pv += typical * candle.volume
        cum_vol += candle.volume
        result.append(cum_pv / cum_vol if cum_vol else typical)
    return result


def opening_range(candles: list[Candle], bars: int = 3) -> dict[str, Any] | None:
    """Compute opening range from the first `bars` candles of the latest session."""
    if not candles:
        return None
    from datetime import datetime, timezone

    last_session = datetime.fromtimestamp(candles[-1].timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    session_candles = [
        candle
        for candle in candles
        if datetime.fromtimestamp(candle.timestamp, tz=timezone.utc).strftime("%Y-%m-%d") == last_session
    ]
    if not session_candles:
        return None
    or_bars = session_candles[:bars]
    if not or_bars:
        return None
    or_high = max(c.high for c in or_bars)
    or_low = min(c.low for c in or_bars)
    last_close = session_candles[-1].close
    state = "inside"
    if last_close > or_high:
        state = "broken_up"
    elif last_close < or_low:
        state = "broken_down"
    return {
        "session": last_session,
        "bars": len(or_bars),
        "or_high": round(or_high, 2),
        "or_low": round(or_low, 2),
        "range_pct": round(((or_high - or_low) / or_low) * 100, 2) if or_low else None,
        "last_close": round(last_close, 2),
        "state": state,
    }


def rsi_series(values: list[float], period: int = 14) -> list[float | None]:
    return [rsi(values[: index + 1], period) for index in range(len(values))]


def stochastic_rsi(values: list[float], rsi_period: int = 14, stoch_period: int = 14) -> list[dict[str, float | None]]:
    rsis = rsi_series(values, rsi_period)
    result: list[dict[str, float | None]] = []
    for index, current in enumerate(rsis):
        if current is None or index + 1 < rsi_period + stoch_period:
            result.append({"k": None, "d": None})
            continue
        window = [value for value in rsis[index + 1 - stoch_period : index + 1] if value is not None]
        low, high = min(window), max(window)
        k = 0 if high == low else ((current - low) / (high - low)) * 100
        recent_k = [item["k"] for item in result[-2:] if item["k"] is not None] + [k]
        result.append({"k": _round(k), "d": _round(mean(recent_k))})
    return result


def divergence_signals(candles: list[Candle], rsis: list[float | None]) -> dict[str, Any]:
    if len(candles) < 30:
        return {"state": "insufficient"}
    recent = candles[-30:]
    recent_rsi = rsis[-30:]
    lows = sorted(range(len(recent)), key=lambda idx: recent[idx].low)[:2]
    highs = sorted(range(len(recent)), key=lambda idx: recent[idx].high, reverse=True)[:2]
    bullish = False
    bearish = False
    if len(lows) == 2:
        a, b = sorted(lows)
        bullish = recent[b].low < recent[a].low and (recent_rsi[b] or 0) > (recent_rsi[a] or 100)
    if len(highs) == 2:
        a, b = sorted(highs)
        bearish = recent[b].high > recent[a].high and (recent_rsi[b] or 100) < (recent_rsi[a] or 0)
    return {"bullish": bullish, "bearish": bearish, "state": "bullish" if bullish else "bearish" if bearish else "none"}


def setup_mode_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    plan = analysis.get("trade_plan") or {}
    indicators = analysis.get("indicators") or {}
    levels = analysis.get("levels_v2") or []
    alerts = []
    if indicators.get("squeeze", {}).get("state") == "squeeze_on":
        alerts.append("Volatility squeeze active")
    if indicators.get("supertrend", {}).get("direction") == "bullish":
        alerts.append("Supertrend bullish")
    if analysis.get("volume_expansion") and analysis["volume_expansion"] >= 1.5:
        alerts.append("Volume expansion")
    return {
        "mode": "Swing Desk",
        "primary_action": plan.get("action"),
        "setup_quality": plan.get("grade"),
        "focus": "Wait for confirmation near marked levels; size from deterministic stop.",
        "alerts_ready": bool(alerts),
        "alerts": alerts,
        "levels_count": len(levels),
    }


def classify_trend(price: float, ma20: float | None, ma50: float | None, ma200: float | None) -> str:
    if ma20 and ma50 and ma200 and price > ma20 > ma50 > ma200:
        return "strong uptrend"
    if ma20 and ma50 and price > ma20 > ma50:
        return "uptrend"
    if ma20 and ma50 and price < ma20 < ma50:
        return "downtrend"
    return "sideways"


def risk_reward(price: float, support: float | None, resistance: float | None) -> float | None:
    if not support or not resistance or price <= support:
        return None
    risk = price - support
    reward = resistance - price
    if risk <= 0:
        return None
    return round(reward / risk, 2)


def volume_expansion(volume: float, avg: float | None) -> float | None:
    if not avg:
        return None
    return round(volume / avg, 2)


def predictive_profile(candles: list[Candle], benchmark_return_pct: float | None) -> dict[str, Any]:
    closes = [c.close for c in candles]
    returns = _daily_returns(closes)
    if len(returns) < 20:
        return {"status": "insufficient"}
    win_rate_20 = sum(1 for value in returns[-20:] if value > 0) / 20
    avg_return_5 = _return_pct(closes, 5)
    avg_return_20 = _return_pct(closes, 20)
    volatility_20 = _stddev(returns[-20:]) * math.sqrt(252) * 100
    atr_value = atr(candles)
    downside = [value for value in returns[-60:] if value < 0]
    upside = [value for value in returns[-60:] if value > 0]
    skew_hint = "upside skew" if sum(upside) > abs(sum(downside)) else "downside skew"
    probability_bias = round(min(max(50 + ((avg_return_20 or 0) * 2) + ((benchmark_return_pct or 0) * 0.4), 5), 95), 1)
    return {
        "status": "ok",
        "five_day_return_pct": avg_return_5,
        "twenty_day_return_pct": avg_return_20,
        "twenty_day_win_rate_pct": round(win_rate_20 * 100, 1),
        "annualized_volatility_pct": round(volatility_20, 2),
        "atr": atr_value,
        "atr_pct": round((atr_value / closes[-1]) * 100, 2) if atr_value and closes[-1] else None,
        "skew_hint": skew_hint,
        "directional_probability_bias_pct": probability_bias,
    }


def alpha_factors(candles: list[Candle], benchmark_return_pct: float | None, volume_avg20: float | None) -> dict[str, Any]:
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    last = candles[-1]
    high_52 = max(highs[-252:]) if len(highs) >= 30 else max(highs)
    low_52 = min(lows[-252:]) if len(lows) >= 30 else min(lows)
    range_position = ((last.close - low_52) / (high_52 - low_52)) * 100 if high_52 != low_52 else None
    volume_z = zscore(volumes[-60:], last.volume)
    momentum_63 = _return_pct(closes, 63)
    momentum_126 = _return_pct(closes, 126)
    rs = None if benchmark_return_pct is None or _return_pct(closes, 20) is None else round((_return_pct(closes, 20) or 0) - benchmark_return_pct, 2)
    return {
        "range_position_52w_pct": _round(range_position),
        "distance_from_52w_high_pct": _round(((last.close - high_52) / high_52) * 100 if high_52 else None),
        "distance_from_52w_low_pct": _round(((last.close - low_52) / low_52) * 100 if low_52 else None),
        "momentum_3m_pct": momentum_63,
        "momentum_6m_pct": momentum_126,
        "relative_strength_20d_pct": rs,
        "volume_zscore": _round(volume_z),
        "liquidity_signal": "expanding" if volume_avg20 and last.volume > volume_avg20 * 1.2 else "normal",
    }


def strategy_signals(
    candles: list[Candle],
    levels: dict[str, float | None],
    ma20: float | None,
    ma50: float | None,
    ma200: float | None,
    rsi_value: float | None,
    macd_value: dict[str, Any],
    rr: float | None,
) -> list[dict[str, Any]]:
    last = candles[-1]
    signals = [
        {
            "name": "Trend continuation",
            "direction": "bullish",
            "active": bool(ma20 and ma50 and last.close > ma20 > ma50),
            "quality": _signal_quality([ma20 and ma50 and last.close > ma20 > ma50, rsi_value and 50 <= rsi_value <= 70, macd_value.get("state") == "bullish", rr and rr >= 1.5]),
            "trigger": "Close holds above 20/50 DMA with RSI 50-70 and bullish MACD.",
        },
        {
            "name": "Support bounce",
            "direction": "bullish",
            "active": bool(levels["support"] and last.close <= levels["support"] * 1.02 and last.close > levels["support"]),
            "quality": _signal_quality([levels["support"] and last.close > levels["support"], rsi_value and rsi_value >= 35, rr and rr >= 1.5]),
            "trigger": "Price is near support with enough room to resistance.",
        },
        {
            "name": "Breakout watch",
            "direction": "bullish",
            "active": bool(levels["resistance"] and last.close >= levels["resistance"] * 0.99),
            "quality": _signal_quality([levels["resistance"] and last.close >= levels["resistance"] * 0.99, macd_value.get("state") == "bullish", rsi_value and rsi_value < 75]),
            "trigger": "Close above resistance with volume expansion confirms breakout.",
        },
        {
            "name": "Mean reversion risk",
            "direction": "caution",
            "active": bool(rsi_value and rsi_value > 75),
            "quality": _signal_quality([rsi_value and rsi_value > 75, ma20 and last.close > ma20 * 1.08]),
            "trigger": "Overextended move may need consolidation before entry.",
        },
    ]
    return signals


def market_regime(candles: list[Candle], ma20: float | None, ma50: float | None, ma200: float | None) -> dict[str, Any]:
    last = candles[-1]
    atr_value = atr(candles)
    atr_pct = (atr_value / last.close) * 100 if atr_value and last.close else None
    if ma20 and ma50 and ma200 and last.close > ma20 > ma50 > ma200:
        trend = "markup"
    elif ma20 and ma50 and last.close < ma20 < ma50:
        trend = "markdown"
    else:
        trend = "range / transition"
    volatility = "high" if atr_pct and atr_pct > 4 else "medium" if atr_pct and atr_pct > 2 else "low"
    return {"trend_regime": trend, "volatility_regime": volatility, "atr_pct": _round(atr_pct)}


def atr(candles: list[Candle], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    true_ranges = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        true_ranges.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    return round(mean(true_ranges), 2)


def trade_plan(analysis: dict[str, Any], candles: list[Candle]) -> dict[str, Any]:
    price = analysis.get("last_price")
    support = analysis.get("support")
    resistance = analysis.get("resistance")
    rr = analysis.get("risk_reward")
    trend = analysis.get("trend_state")
    rsi_value = analysis.get("rsi")
    macd_state = (analysis.get("macd") or {}).get("state")
    relative_strength = analysis.get("relative_strength")
    volume_ratio = analysis.get("volume_expansion")
    atr_value = atr(candles)
    score = int(analysis.get("technical_score") or 0)
    timeframe = (analysis.get("timeframe") or "daily").lower()
    is_intraday = timeframe not in {"daily", "weekly"}
    atr_mult = 1.5 if is_intraday else 1.0

    checklist = [
        _check("Trend alignment", trend in {"uptrend", "strong uptrend"}, f"Trend is {trend}."),
        _check("Momentum quality", rsi_value is not None and 45 <= rsi_value <= 72 and macd_state == "bullish", f"RSI {rsi_value}, MACD {macd_state}."),
        _check("Relative strength", relative_strength is not None and relative_strength > 0, f"20-period relative strength {relative_strength}%."),
        _check("Volume confirmation", volume_ratio is not None and volume_ratio >= 1.1, f"Volume is {volume_ratio}x 20-period average."),
        _check("Risk/reward", rr is not None and rr >= 1.5, f"Current R:R is {rr}."),
    ]
    passed = sum(1 for item in checklist if item["status"] == "pass")
    blockers = [item["label"] for item in checklist if item["status"] == "fail"]

    if passed >= 4 and score >= 65:
        action = "Actionable long watch"
        grade = "A" if passed == 5 and score >= 78 else "B"
        bias = "bullish"
    elif passed >= 3 and score >= 45:
        action = "Developing setup"
        grade = "C"
        bias = "constructive"
    elif support and price and price <= support * 1.02 and rsi_value and rsi_value < 40:
        action = "Reversal watch only"
        grade = "C-"
        bias = "counter-trend"
    else:
        action = "Wait / avoid"
        grade = "D"
        bias = "neutral-to-weak"

    structure_stop = support
    atr_stop = round(price - (atr_value * atr_mult), 2) if price and atr_value else None
    if structure_stop and atr_stop:
        stop_loss = round(min(structure_stop, atr_stop), 2)
    else:
        stop_loss = atr_stop or (round(structure_stop - ((atr_value or 0) * 0.25), 2) if structure_stop else None)

    entry_low = support if support and price and support < price else price
    entry_high = price
    if resistance and price and resistance <= price * 1.02:
        setup_type = "breakout / resistance test"
        entry_low = resistance
        entry_high = round(resistance * 1.01, 2)
    elif support and price and price <= support * 1.04:
        setup_type = "support bounce"
        entry_high = round(support * 1.025, 2)
    elif trend in {"uptrend", "strong uptrend"}:
        setup_type = "trend pullback"
        entry_low = analysis.get("ma20") or support or price
    else:
        setup_type = "no clean directional setup"

    targets = []
    if resistance:
        targets.append({"label": "T1 resistance", "price": resistance})
    if price and stop_loss and price > stop_loss:
        risk = price - stop_loss
        targets.append({"label": "T2 2R", "price": round(price + (2 * risk), 2)})
        targets.append({"label": "T3 3R", "price": round(price + (3 * risk), 2)})

    return {
        "grade": grade,
        "action": action,
        "bias": bias,
        "setup_type": setup_type,
        "score": score,
        "entry_zone": {"low": _round(entry_low), "high": _round(entry_high)},
        "stop_loss": stop_loss,
        "stop_type": "atr+structure" if atr_stop and structure_stop else ("atr" if atr_stop else "structure"),
        "atr": _round(atr_value),
        "atr_mult": atr_mult,
        "targets": targets[:3],
        "invalidation": _invalidation_text(stop_loss, support, trend),
        "checklist": checklist,
        "strengths": [item["label"] for item in checklist if item["status"] == "pass"],
        "blockers": blockers,
        "analyst_note": _analyst_note(action, setup_type, blockers),
        "timeframe": timeframe,
    }


def score_setup(
    trend: str,
    rsi_value: float | None,
    macd_state: str,
    volume_ratio: float | None,
    relative_strength: float | None,
    rr: float | None,
) -> int:
    score = 0
    score += {"strong uptrend": 34, "uptrend": 24, "sideways": 8, "downtrend": -15}.get(trend, 0)
    if rsi_value is not None:
        score += 18 if 50 <= rsi_value <= 68 else 8 if 40 <= rsi_value < 50 or 68 < rsi_value <= 75 else -2
    score += 15 if macd_state == "bullish" else -8 if macd_state == "bearish" else 0
    if volume_ratio is not None:
        score += 12 if volume_ratio >= 1.5 else 6 if volume_ratio >= 1.1 else 0
    if relative_strength is not None:
        score += 15 if relative_strength > 3 else 8 if relative_strength > 0 else -8
    if rr is not None:
        score += 12 if rr >= 2 else 5 if rr >= 1.2 else -8
    return max(0, min(100, score))


def _check(label: str, condition: bool, detail: str) -> dict[str, str]:
    return {"label": label, "status": "pass" if condition else "fail", "detail": detail}


def _invalidation_text(stop_loss: float | None, support: float | None, trend: str | None) -> str:
    if stop_loss:
        return f"Close below {stop_loss} invalidates the current long thesis."
    if support:
        return f"Sustained trade below support {support} invalidates the setup."
    return f"No clean invalidation level yet; trend state is {trend}."


def _analyst_note(action: str, setup_type: str, blockers: list[str]) -> str:
    if action == "Actionable long watch":
        return f"Setup is usable as a {setup_type}, provided price confirms and risk is sized from the stop."
    if action == "Developing setup":
        return f"Setup is forming, but wait for confirmation. Main gaps: {', '.join(blockers) or 'confirmation'}."
    if action == "Reversal watch only":
        return "Price is near a possible reversal area, but this is not a trend-following long yet."
    return f"No professional-grade long setup yet. Blockers: {', '.join(blockers) or 'insufficient confirmation'}."


def _return_pct(values: list[float], period: int) -> float | None:
    if len(values) <= period or values[-period - 1] == 0:
        return None
    return round(((values[-1] - values[-period - 1]) / values[-period - 1]) * 100, 2)


def _daily_returns(values: list[float]) -> list[float]:
    return [((current - previous) / previous) for previous, current in zip(values, values[1:]) if previous]


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def zscore(values: list[float], current: float) -> float | None:
    if len(values) < 10:
        return None
    deviation = _stddev(values)
    if deviation == 0:
        return None
    return (current - mean(values)) / deviation


def _signal_quality(checks: list[object]) -> int:
    valid = sum(1 for check in checks if bool(check))
    return round((valid / len(checks)) * 100) if checks else 0


def _last_touch_index(candles: list[Candle], level: float, tolerance_pct: float) -> int | None:
    for index in range(len(candles) - 1, -1, -1):
        candle = candles[index]
        if candle.low <= level * (1 + tolerance_pct) and candle.high >= level * (1 - tolerance_pct):
            return index
    return None


def _recency_score(total: int, index: int | None) -> int:
    if index is None or total <= 1:
        return 0
    bars_ago = total - 1 - index
    return max(0, min(100, round(100 - (bars_ago / total) * 100)))


def _breakout_state(candles: list[Candle], level: float, level_type: str) -> str:
    if len(candles) < 3:
        return "insufficient"
    closes = [c.close for c in candles[-3:]]
    if level_type == "resistance":
        if closes[-1] > level and closes[-2] <= level:
            return "fresh_breakout"
        if closes[-1] > level:
            return "holding_above"
        if closes[-1] >= level * 0.99:
            return "testing"
    if level_type == "support":
        if closes[-1] < level and closes[-2] >= level:
            return "fresh_breakdown"
        if closes[-1] < level:
            return "below"
        if closes[-1] <= level * 1.01:
            return "testing"
    return "watch"


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _float_or_zero(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)
