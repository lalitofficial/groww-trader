from __future__ import annotations

from .spec import StrategySpec


def _build() -> list[StrategySpec]:
    return [
        StrategySpec.from_dict(
            {
                "id": "golden_cross_50_200",
                "name": "Golden Cross 50/200",
                "author": "community",
                "source_url": "https://github.com/topics/golden-cross",
                "description": "Classic long-only swing strategy: enter when 50-SMA crosses above 200-SMA and RSI is healthy. Exit on death cross.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "sma_50": ["sma", 50],
                    "sma_200": ["sma", 200],
                    "rsi": ["rsi", 14],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "crosses_above", "a": "sma_50", "b": "sma_200"},
                    {"op": "gt", "a": "rsi", "b": 50},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "sma_50", "b": "sma_200"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                    "target": {"type": "r_multiple", "value": 3},
                },
                "tags": ["swing", "trend"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "donchian_turtle_breakout",
                "name": "Donchian Channel Breakout (Turtle)",
                "author": "Richard Dennis (canonical)",
                "source_url": "https://github.com/topics/turtle-trading",
                "description": "Long when close breaks 20-bar high; exit when close breaks 10-bar low. ATR-sized stop.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "dc20": ["donchian", 20],
                    "dc10": ["donchian", 10],
                    "atr": ["atr", 20],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "dc20_high"},
                ],
                "exit_long": [
                    {"op": "lt", "a": "close", "b": "dc10_low"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                    "target": {"type": "r_multiple", "value": 4},
                },
                "tags": ["swing", "breakout", "trend"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "rsi2_connors",
                "name": "RSI(2) Mean Reversion (Connors)",
                "author": "Larry Connors",
                "source_url": "https://github.com/topics/mean-reversion",
                "description": "Buy when RSI(2) is extreme oversold above the 200-SMA; exit when RSI lifts above 75.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "sma_200": ["sma", 200],
                    "rsi2": ["rsi", 2],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "sma_200"},
                    {"op": "lt", "a": "rsi2", "b": 10},
                ],
                "exit_long": [
                    {"op": "gt", "a": "rsi2", "b": 75},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.5},
                    "max_bars": 8,
                },
                "tags": ["swing", "mean-reversion"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "triple_ema",
                "name": "Triple EMA Trend (5/20/50)",
                "author": "community",
                "source_url": "https://github.com/topics/ema-crossover",
                "description": "Long when 5-EMA > 20-EMA > 50-EMA and price > 5-EMA. Exit on opposite stack.",
                "timeframes": ["daily", "hourly"],
                "direction": "long_only",
                "indicators": {
                    "ema_5": ["ema", 5],
                    "ema_20": ["ema", 20],
                    "ema_50": ["ema", 50],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "gt", "a": "ema_5", "b": "ema_20"},
                    {"op": "gt", "a": "ema_20", "b": "ema_50"},
                    {"op": "gt", "a": "close", "b": "ema_5"},
                ],
                "exit_long": [
                    {"op": "lt", "a": "ema_5", "b": "ema_20"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 1.8},
                    "target": {"type": "r_multiple", "value": 3},
                },
                "tags": ["swing", "trend"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "macd_histogram_flip",
                "name": "MACD Histogram Flip",
                "author": "community",
                "source_url": "https://github.com/topics/macd",
                "description": "Long when MACD histogram crosses above zero and price is above 50-EMA.",
                "timeframes": ["daily", "hourly"],
                "direction": "long_only",
                "indicators": {
                    "ema_50": ["ema", 50],
                    "macd_hist": ["macd_histogram", 12, 26, 9],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "crosses_above", "a": "macd_hist", "b": 0},
                    {"op": "gt", "a": "close", "b": "ema_50"},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "macd_hist", "b": 0},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                    "target": {"type": "r_multiple", "value": 2.5},
                },
                "tags": ["swing", "momentum"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "supertrend_follow",
                "name": "Supertrend Trend-Follow",
                "author": "community",
                "source_url": "https://github.com/topics/supertrend",
                "description": "Long when Supertrend flips bullish; exit when it flips bearish.",
                "timeframes": ["daily", "hourly"],
                "direction": "long_only",
                "indicators": {
                    "st_dir": ["supertrend", 10, 3.0],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "eq", "a": "st_dir", "b": "bullish"},
                ],
                "exit_long": [
                    {"op": "eq", "a": "st_dir", "b": "bearish"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                },
                "tags": ["swing", "trend"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "bb_squeeze_breakout",
                "name": "Bollinger Squeeze Breakout",
                "author": "John Bollinger / community",
                "source_url": "https://github.com/topics/bollinger-bands",
                "description": "Buy a close above the upper Bollinger band after a tight squeeze.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "bb": ["bollinger", 20],
                    "rsi": ["rsi", 14],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "crosses_above", "a": "close", "b": "bb_upper"},
                    {"op": "between", "a": "rsi", "low": 50, "high": 70},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "close", "b": "bb_middle"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 1.5},
                    "target": {"type": "r_multiple", "value": 2.5},
                },
                "tags": ["swing", "breakout"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "orb_15m",
                "name": "Opening Range Breakout (15m)",
                "author": "community",
                "source_url": "https://github.com/topics/opening-range-breakout",
                "description": "Intraday: enter long on a 15m close above the opening range high; ATR stop, square off EOD.",
                "timeframes": ["15m", "30m"],
                "direction": "both",
                "indicators": {
                    "dc20": ["donchian", 20],
                    "atr": ["atr", 14],
                    "vwap": ["vwap"],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "dc20_high"},
                    {"op": "gt", "a": "close", "b": "vwap"},
                ],
                "entry_short": [
                    {"op": "lt", "a": "close", "b": "dc20_low"},
                    {"op": "lt", "a": "close", "b": "vwap"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 1.5},
                    "target": {"type": "r_multiple", "value": 2},
                    "max_bars": 24,
                },
                "tags": ["intraday", "breakout"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "vwap_reclaim_intraday",
                "name": "VWAP Reclaim Intraday",
                "author": "community",
                "source_url": "https://github.com/topics/vwap",
                "description": "Intraday: enter long when price reclaims VWAP after dipping below; exit on opposite reclaim.",
                "timeframes": ["5m", "15m"],
                "direction": "both",
                "indicators": {
                    "vwap": ["vwap"],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "crosses_above", "a": "close", "b": "vwap"},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "close", "b": "vwap"},
                ],
                "entry_short": [
                    {"op": "crosses_below", "a": "close", "b": "vwap"},
                ],
                "exit_short": [
                    {"op": "crosses_above", "a": "close", "b": "vwap"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 1.2},
                    "target": {"type": "r_multiple", "value": 2},
                    "max_bars": 24,
                },
                "tags": ["intraday", "mean-reversion"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "pullback_to_ma20",
                "name": "Pullback to 20-EMA in Uptrend",
                "author": "community",
                "source_url": "https://github.com/topics/pullback-strategy",
                "description": "In an uptrend (close > 50-EMA), enter long after a 3-bar pullback that holds the 20-EMA.",
                "timeframes": ["daily", "hourly"],
                "direction": "long_only",
                "indicators": {
                    "ema_20": ["ema", 20],
                    "ema_50": ["ema", 50],
                    "rsi": ["rsi", 14],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "ema_50"},
                    {"op": "consec_bars_below", "a": "close", "b": "ema_20", "bars": 3},
                    {"op": "crosses_above", "a": "close", "b": "ema_20"},
                    {"op": "between", "a": "rsi", "low": 40, "high": 65},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "close", "b": "ema_20"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 1.5},
                    "target": {"type": "r_multiple", "value": 2.5},
                },
                "tags": ["swing", "pullback"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "heikin_ashi_trend",
                "name": "Heikin Ashi Trend Continuation (proxy)",
                "author": "community",
                "source_url": "https://github.com/topics/heikin-ashi",
                "description": "Proxy implementation: long when close > 20-EMA, 5-EMA > 20-EMA, and ATR rising.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "ema_5": ["ema", 5],
                    "ema_20": ["ema", 20],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "ema_20"},
                    {"op": "gt", "a": "ema_5", "b": "ema_20"},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "ema_5", "b": "ema_20"},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                },
                "tags": ["swing", "trend"],
            }
        ),
        StrategySpec.from_dict(
            {
                "id": "stoch_rsi_reversal",
                "name": "Stochastic RSI Reversal",
                "author": "community",
                "source_url": "https://github.com/topics/stochastic-rsi",
                "description": "Long when Stochastic RSI exits oversold above the 200-SMA.",
                "timeframes": ["daily"],
                "direction": "long_only",
                "indicators": {
                    "sma_200": ["sma", 200],
                    "stoch_rsi": ["stoch_rsi", 14],
                    "atr": ["atr", 14],
                },
                "entry_long": [
                    {"op": "gt", "a": "close", "b": "sma_200"},
                    {"op": "crosses_above", "a": "stoch_rsi", "b": 20},
                ],
                "exit_long": [
                    {"op": "crosses_below", "a": "stoch_rsi", "b": 80},
                ],
                "risk": {
                    "stop": {"type": "atr_trail", "atr": "atr", "mult": 2.0},
                    "max_bars": 15,
                },
                "tags": ["swing", "mean-reversion"],
            }
        ),
    ]


BUILTIN_STRATEGIES: dict[str, StrategySpec] = {spec.id: spec for spec in _build()}


def get_builtin_strategy(strategy_id: str) -> StrategySpec | None:
    return BUILTIN_STRATEGIES.get(strategy_id)
