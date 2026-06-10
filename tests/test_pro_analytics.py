from groww_trader.services.backtests import run_backtest
from groww_trader.services.charting import build_chart_context
from groww_trader.services.indicators import Candle, analyze_candles, indicator_bundle


def _candles(count: int = 220) -> list[Candle]:
    return [
        Candle(
            timestamp=1_700_000_000 + i * 86_400,
            open=100 + (i * 0.45),
            high=103 + (i * 0.45) + (i % 4),
            low=98 + (i * 0.43) - (i % 3),
            close=101 + (i * 0.47),
            volume=1000 + (i * 15) + ((i % 13) * 40),
        )
        for i in range(count)
    ]


def test_indicator_bundle_includes_v1_pro_fields():
    indicators = indicator_bundle(_candles())
    assert indicators["atr"] is not None
    assert indicators["supertrend"]["direction"] in {"bullish", "bearish"}
    assert indicators["bollinger_bands"]["upper"] is not None
    assert indicators["keltner_channel"]["upper"] is not None
    assert indicators["stochastic_rsi"]["k"] is not None


def test_analysis_returns_enriched_levels_and_mode_summary():
    analysis = analyze_candles(_candles())
    assert analysis["levels_v2"]
    assert "last_touch_at" in analysis["levels_v2"][0]
    assert "breakout_state" in analysis["levels_v2"][0]
    assert analysis["setup_mode_summary"]["mode"] == "Swing Desk"


def test_chart_context_returns_overlays_and_markers():
    candles = _candles()
    analysis = analyze_candles(candles)
    context = build_chart_context("TEST", "daily", candles, analysis, {"provider": "fixture"})
    assert context["overlays"]["ma20"]
    assert "levels" in context["overlays"]
    assert context["panels"] == ["price_action", "volume", "momentum", "volatility", "levels"]


def test_backtest_returns_metrics_shape():
    result = run_backtest(_candles(), "ma_trend_pullback")
    assert result["strategy_id"] == "ma_trend_pullback"
    assert "win_rate" in result["metrics"]
    assert isinstance(result["trades"], list)
