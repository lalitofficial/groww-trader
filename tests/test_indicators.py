from groww_trader.services.indicators import Candle, analyze_candles, normalize_candles, rsi, support_resistance, support_resistance_levels


def test_rsi_returns_value_for_sufficient_data():
    values = [100, 101, 102, 101, 103, 104, 105, 104, 106, 107, 108, 109, 108, 110, 111, 112]
    assert rsi(values) is not None


def test_support_resistance_uses_recent_levels():
    candles = [
        Candle(timestamp=i, open=100 + i, high=104 + i, low=98 + i, close=102 + i, volume=1000)
        for i in range(80)
    ]
    levels = support_resistance(candles)
    assert levels["support"] is not None
    assert levels["resistance"] is not None


def test_analyze_candles_scores_uptrend():
    candles = [
        Candle(timestamp=i, open=100 + i, high=102 + i, low=99 + i, close=101 + i, volume=1000 + (i * 10))
        for i in range(220)
    ]
    analysis = analyze_candles(candles, benchmark_return_pct=2)
    assert analysis["status"] == "ok"
    assert analysis["technical_score"] > 50
    assert analysis["trade_plan"]["action"]
    assert analysis["trade_plan"]["entry_zone"]
    assert analysis["trade_plan"]["checklist"]


def test_normalize_candles_accepts_missing_volume():
    payload = {"candles": [[1779249000, 100, 105, 99, 104, None]]}
    candles = normalize_candles(payload)
    assert candles[0].volume == 0


def test_support_resistance_levels_returns_clustered_levels():
    candles = [
        Candle(timestamp=i, open=100 + (i % 5), high=110 + (i % 3), low=95 - (i % 2), close=102 + (i % 4), volume=1000 + i)
        for i in range(140)
    ]
    levels = support_resistance_levels(candles)
    assert levels
    assert {item["type"] for item in levels} <= {"support", "resistance"}
