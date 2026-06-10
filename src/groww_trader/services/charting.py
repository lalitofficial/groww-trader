from __future__ import annotations

from typing import Any

from .indicators import (
    Candle,
    bollinger_bands,
    keltner_channels,
    macd,
    rsi_series,
    sma,
    stochastic_rsi,
    supertrend,
    vwap_series,
)


def build_chart_context(
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    analysis: dict[str, Any],
    data_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overlays = build_chart_overlays(candles, analysis)
    markers = build_chart_markers(candles, analysis)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": [candle.__dict__ for candle in candles],
        "overlays": overlays,
        "markers": markers,
        "panels": ["price_action", "volume", "momentum", "volatility", "levels"],
        "data_source": data_source or {},
    }


def build_chart_overlays(candles: list[Candle], analysis: dict[str, Any]) -> dict[str, Any]:
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    bb = bollinger_bands(closes)
    kc = keltner_channels(candles)
    st = supertrend(candles)
    vwap = vwap_series(candles)
    rsis = rsi_series(closes)
    stoch = stochastic_rsi(closes)
    macd_state = macd(closes)
    volume_avg20 = [_sma_at(volumes, index, 20) for index in range(len(volumes))]

    return {
        "ma20": _line(candles, [_sma_at(closes, index, 20) for index in range(len(candles))]),
        "ma50": _line(candles, [_sma_at(closes, index, 50) for index in range(len(candles))]),
        "ma200": _line(candles, [_sma_at(closes, index, 200) for index in range(len(candles))]),
        "vwap": _line(candles, vwap),
        "supertrend": _line(candles, [(item or {}).get("value") for item in st]),
        "bollinger": {
            "upper": _line(candles, [(item or {}).get("upper") for item in bb]),
            "middle": _line(candles, [(item or {}).get("middle") for item in bb]),
            "lower": _line(candles, [(item or {}).get("lower") for item in bb]),
        },
        "keltner": {
            "upper": _line(candles, [(item or {}).get("upper") for item in kc]),
            "middle": _line(candles, [(item or {}).get("middle") for item in kc]),
            "lower": _line(candles, [(item or {}).get("lower") for item in kc]),
        },
        "rsi": _line(candles, rsis),
        "stoch_rsi_k": _line(candles, [(item or {}).get("k") for item in stoch]),
        "stoch_rsi_d": _line(candles, [(item or {}).get("d") for item in stoch]),
        "volume_avg20": _line(candles, volume_avg20),
        "macd_state": macd_state,
        "levels": analysis.get("levels_v2") or analysis.get("levels") or [],
    }


def build_chart_markers(candles: list[Candle], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    volume_avg = analysis.get("volume_avg20")
    for candle in candles[-90:]:
        if volume_avg and candle.volume >= volume_avg * 1.8:
            markers.append({"time": candle.timestamp, "type": "volume_spike", "position": "belowBar", "color": "#6ea8fe", "text": "Vol"})
    for level in analysis.get("levels_v2") or []:
        state = level.get("breakout_state")
        if state in {"fresh_breakout", "fresh_breakdown"} and candles:
            markers.append(
                {
                    "time": candles[-1].timestamp,
                    "type": state,
                    "position": "aboveBar" if state == "fresh_breakout" else "belowBar",
                    "color": "#21c77a" if state == "fresh_breakout" else "#ff5c7a",
                    "text": "BO" if state == "fresh_breakout" else "BD",
                }
            )
    div = (analysis.get("indicators") or {}).get("divergence") or {}
    if candles and div.get("state") in {"bullish", "bearish"}:
        markers.append(
            {
                "time": candles[-1].timestamp,
                "type": "divergence",
                "position": "belowBar" if div["state"] == "bullish" else "aboveBar",
                "color": "#21c77a" if div["state"] == "bullish" else "#ff5c7a",
                "text": "Div",
            }
        )
    return markers


def _line(candles: list[Candle], values: list[Any]) -> list[dict[str, float]]:
    points = []
    for candle, value in zip(candles, values):
        if value is None:
            continue
        try:
            points.append({"time": candle.timestamp, "value": round(float(value), 4)})
        except (TypeError, ValueError):
            continue
    return points


def _sma_at(values: list[float], index: int, period: int) -> float | None:
    if index + 1 < period:
        return None
    return sma(values[: index + 1], period)
