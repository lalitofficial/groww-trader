from __future__ import annotations

import math
from statistics import mean
from typing import Any

from groww_trader.settings import AppSettings

from ..indicators import Candle, atr, ema_series, rsi_series, session_vwap_series, sma, stochastic_rsi, supertrend
from .spec import StrategySpec


class StrategyEngine:
    """Interprets a StrategySpec on candles and produces trades + metrics.

    The engine intentionally re-uses indicator helpers we already have in
    services.indicators so any GitHub-imported strategy automatically benefits
    from the same calculations that drive the rest of the dashboard.
    """

    def __init__(self, spec: StrategySpec, settings: AppSettings | None = None) -> None:
        self.spec = spec
        self.settings = settings
        self.slippage_bps = settings.paper_slippage_bps if settings else 5
        self.brokerage = settings.paper_brokerage_per_trade if settings else 20
        self.stt_intraday = settings.paper_stt_pct_intraday if settings else 0.025
        self.stt_delivery = settings.paper_stt_pct_delivery if settings else 0.1
        self.initial_equity = settings.account_capital if settings else 100000
        self.risk_pct = settings.risk_per_trade_pct if settings else 1.0

    def run(self, candles: list[Candle], timeframe: str = "daily") -> dict[str, Any]:
        if len(candles) < 60:
            return {
                "strategy_id": self.spec.id,
                "strategy_name": self.spec.name,
                "engine": "strategy-spec",
                "timeframe": timeframe,
                "metrics": {},
                "trades": [],
                "equity_curve": [],
                "warnings": ["Insufficient candles for a reliable run."],
                "source_url": self.spec.source_url,
            }
        is_intraday = timeframe not in {"daily", "weekly"}
        series = self._compute_indicators(candles, timeframe)
        trades = self._simulate(candles, series, is_intraday)
        equity_curve = self._equity_curve(trades)
        metrics = self._metrics(trades, equity_curve)
        return {
            "strategy_id": self.spec.id,
            "strategy_name": self.spec.name,
            "engine": "strategy-spec",
            "timeframe": timeframe,
            "metrics": metrics,
            "trades": trades[-50:],
            "equity_curve": equity_curve,
            "warnings": [f"Cost model: slippage {self.slippage_bps}bps, brokerage Rs {self.brokerage}/trade."],
            "source_url": self.spec.source_url,
            "author": self.spec.author,
            "tags": self.spec.tags,
        }

    # -------- Indicator pre-compute --------
    def _compute_indicators(self, candles: list[Candle], timeframe: str) -> dict[str, list[Any]]:
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        series: dict[str, list[Any]] = {
            "close": closes,
            "high": highs,
            "low": lows,
            "open": [c.open for c in candles],
            "volume": [c.volume for c in candles],
        }
        for label, definition in self.spec.indicators.items():
            kind = str(definition[0])
            args = definition[1:]
            if kind == "sma":
                period = int(args[0])
                series[label] = [_sma_at(closes, idx, period) for idx in range(len(candles))]
            elif kind == "ema":
                period = int(args[0])
                values = ema_series(closes, period)
                series[label] = [None if idx + 1 < period else values[idx] for idx in range(len(candles))]
            elif kind == "rsi":
                period = int(args[0]) if args else 14
                series[label] = rsi_series(closes, period)
            elif kind == "atr":
                period = int(args[0]) if args else 14
                series[label] = [atr(candles[: idx + 1], period) for idx in range(len(candles))]
            elif kind == "macd_histogram":
                fast, slow, signal = (int(args[i]) if i < len(args) else default for i, default in enumerate([12, 26, 9]))
                series[label] = _macd_histogram(closes, fast, slow, signal)
            elif kind == "vwap":
                series[label] = session_vwap_series(candles, None if timeframe == "daily" else 15)
            elif kind == "stoch_rsi":
                period = int(args[0]) if args else 14
                stoch = stochastic_rsi(closes, period, period)
                series[label] = [(item.get("k") if item else None) for item in stoch]
            elif kind == "donchian":
                period = int(args[0]) if args else 20
                series[label + "_high"] = _donchian_high(highs, period)
                series[label + "_low"] = _donchian_low(lows, period)
            elif kind == "supertrend":
                period = int(args[0]) if args else 10
                mult = float(args[1]) if len(args) > 1 else 3.0
                st_series = supertrend(candles, period=period, multiplier=mult)
                series[label] = [(item.get("direction") if item else None) for item in st_series]
            elif kind == "bollinger":
                period = int(args[0]) if args else 20
                series[label + "_upper"], series[label + "_lower"], series[label + "_middle"] = _bollinger(closes, period)
        return series

    # -------- Rule evaluation --------
    def _evaluate(self, rule: dict[str, Any], series: dict[str, list[Any]], index: int) -> bool:
        op = rule.get("op")
        a = self._value(rule.get("a"), series, index)
        b = self._value(rule.get("b"), series, index)
        if op == "gt":
            return _both(a, b) and a > b
        if op == "lt":
            return _both(a, b) and a < b
        if op == "gte":
            return _both(a, b) and a >= b
        if op == "lte":
            return _both(a, b) and a <= b
        if op == "eq":
            return _both(a, b) and a == b
        if op == "between":
            lo = self._value(rule.get("low"), series, index)
            hi = self._value(rule.get("high"), series, index)
            return _both(a, lo) and _both(a, hi) and lo <= a <= hi
        if op == "crosses_above":
            prev_a = self._value(rule.get("a"), series, index - 1)
            prev_b = self._value(rule.get("b"), series, index - 1)
            return _both(a, b) and _both(prev_a, prev_b) and prev_a <= prev_b and a > b
        if op == "crosses_below":
            prev_a = self._value(rule.get("a"), series, index - 1)
            prev_b = self._value(rule.get("b"), series, index - 1)
            return _both(a, b) and _both(prev_a, prev_b) and prev_a >= prev_b and a < b
        if op == "above":
            return _both(a, b) and a > b
        if op == "below":
            return _both(a, b) and a < b
        if op == "consec_bars_above":
            bars = int(rule.get("bars") or 3)
            return all(
                _both(self._value(rule.get("a"), series, index - offset), self._value(rule.get("b"), series, index - offset))
                and self._value(rule.get("a"), series, index - offset) > self._value(rule.get("b"), series, index - offset)
                for offset in range(bars)
            )
        if op == "consec_bars_below":
            bars = int(rule.get("bars") or 3)
            return all(
                _both(self._value(rule.get("a"), series, index - offset), self._value(rule.get("b"), series, index - offset))
                and self._value(rule.get("a"), series, index - offset) < self._value(rule.get("b"), series, index - offset)
                for offset in range(bars)
            )
        return False

    def _value(self, token: Any, series: dict[str, list[Any]], index: int) -> Any:
        if index < 0:
            return None
        if isinstance(token, (int, float)):
            return float(token)
        if isinstance(token, str):
            if token in series and index < len(series[token]):
                return series[token][index]
            try:
                return float(token)
            except ValueError:
                return None
        return token

    # -------- Simulation --------
    def _simulate(self, candles: list[Candle], series: dict[str, list[Any]], is_intraday: bool) -> list[dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        position: dict[str, Any] | None = None
        warmup = 30
        for index in range(warmup, len(candles) - 1):
            candle = candles[index]
            next_candle = candles[index + 1]
            stt_pct = self.stt_intraday if is_intraday else self.stt_delivery

            if position is None:
                long_signal = self._all_rules(self.spec.entry_long, series, index) if self.spec.direction in {"long_only", "both"} else False
                short_signal = self._all_rules(self.spec.entry_short, series, index) if self.spec.direction in {"short_only", "both"} else False
                if long_signal or short_signal:
                    direction = "long" if long_signal else "short"
                    entry_side = "BUY" if direction == "long" else "SELL"
                    fill = _slip(next_candle.open, entry_side, self.slippage_bps)
                    stop = self._initial_stop(candles, series, index, direction)
                    risk = abs(fill - stop) if stop else fill * 0.01
                    quantity = max(1, int((self.initial_equity * (self.risk_pct / 100)) / max(risk, 0.01)))
                    entry_fees = self.brokerage + (fill * quantity * (stt_pct / 100))
                    position = {
                        "entry_time": next_candle.timestamp,
                        "entry_index": index + 1,
                        "entry": round(fill, 2),
                        "stop": stop,
                        "direction": direction,
                        "quantity": quantity,
                        "entry_fees": entry_fees,
                    }
                continue
            # Exit logic
            reason = self._exit_reason(candles, series, index, position, is_intraday)
            if reason:
                exit_side = "SELL" if position["direction"] == "long" else "BUY"
                exit_price = _slip(next_candle.open, exit_side, self.slippage_bps)
                exit_fees = self.brokerage + (exit_price * position["quantity"] * (stt_pct / 100))
                sign = 1 if position["direction"] == "long" else -1
                gross = sign * (exit_price - position["entry"]) * position["quantity"]
                pnl = gross - position["entry_fees"] - exit_fees
                trades.append(
                    {
                        **position,
                        "exit_time": next_candle.timestamp,
                        "exit": round(exit_price, 2),
                        "pnl": round(pnl, 2),
                        "fees": round(position["entry_fees"] + exit_fees, 2),
                        "return_pct": round(sign * (exit_price - position["entry"]) / position["entry"] * 100, 2),
                        "exit_reason": reason,
                    }
                )
                position = None
        return trades

    def _all_rules(self, rules: list[dict[str, Any]], series: dict[str, list[Any]], index: int) -> bool:
        if not rules:
            return False
        return all(self._evaluate(rule, series, index) for rule in rules)

    def _initial_stop(self, candles: list[Candle], series: dict[str, list[Any]], index: int, direction: str) -> float | None:
        stop_rule = (self.spec.risk or {}).get("stop") or {}
        kind = stop_rule.get("type")
        candle = candles[index]
        if kind == "atr_trail":
            atr_label = stop_rule.get("atr") or self._find_atr_label()
            atr_value = series.get(atr_label or "", [None])[index] if atr_label else atr(candles[: index + 1])
            mult = float(stop_rule.get("mult") or 1.5)
            if atr_value is None:
                return None
            return round(candle.close - atr_value * mult, 2) if direction == "long" else round(candle.close + atr_value * mult, 2)
        if kind == "fixed_pct":
            pct = float(stop_rule.get("value") or 1.5)
            return round(candle.close * (1 - pct / 100), 2) if direction == "long" else round(candle.close * (1 + pct / 100), 2)
        # Default: 1.5x ATR(14)
        atr_value = atr(candles[: index + 1])
        if atr_value is None:
            return None
        return round(candle.close - atr_value * 1.5, 2) if direction == "long" else round(candle.close + atr_value * 1.5, 2)

    def _find_atr_label(self) -> str | None:
        for label, definition in self.spec.indicators.items():
            if definition and definition[0] == "atr":
                return label
        return None

    def _exit_reason(self, candles: list[Candle], series: dict[str, list[Any]], index: int, position: dict[str, Any], is_intraday: bool) -> str | None:
        candle = candles[index]
        direction = position["direction"]
        stop = position["stop"]
        entry = position["entry"]
        risk = abs(entry - stop) if stop else entry * 0.01

        if direction == "long" and stop and candle.low <= stop:
            return "stop"
        if direction == "short" and stop and candle.high >= stop:
            return "stop"

        target_rule = (self.spec.risk or {}).get("target") or {}
        if target_rule.get("type") == "r_multiple":
            r = float(target_rule.get("value") or 2.0)
            if direction == "long" and candle.high >= entry + (r * risk):
                return f"target_{int(r)}r"
            if direction == "short" and candle.low <= entry - (r * risk):
                return f"target_{int(r)}r"

        opposite_rules = self.spec.exit_long if direction == "long" else self.spec.exit_short
        if opposite_rules and self._all_rules(opposite_rules, series, index):
            return "opposite_signal"

        max_bars = int((self.spec.risk or {}).get("max_bars") or 0)
        if max_bars and index - position["entry_index"] >= max_bars:
            return "time_stop"
        if is_intraday and candle.timestamp - position["entry_time"] >= 6 * 3600:
            return "eod_square_off"
        return None

    # -------- Metrics --------
    def _equity_curve(self, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
        equity = self.initial_equity
        curve = [{"index": 0, "equity": round(equity, 2)}]
        for index, trade in enumerate(trades, start=1):
            equity += trade["pnl"]
            curve.append({"index": index, "time": trade["exit_time"], "equity": round(equity, 2)})
        return curve

    def _metrics(self, trades: list[dict[str, Any]], equity_curve: list[dict[str, Any]]) -> dict[str, Any]:
        if not trades:
            return {"sample_size": 0, "win_rate": 0, "total_return_pct": 0, "max_drawdown_pct": 0, "profit_factor": None, "expectancy": 0, "sharpe": None}
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        final_equity = equity_curve[-1]["equity"]
        peak = self.initial_equity
        max_drawdown = 0.0
        returns: list[float] = []
        prev_equity = self.initial_equity
        for point in equity_curve[1:]:
            eq = point["equity"]
            returns.append((eq - prev_equity) / prev_equity if prev_equity else 0)
            prev_equity = eq
            peak = max(peak, eq)
            max_drawdown = max(max_drawdown, ((peak - eq) / peak) * 100 if peak else 0)
        sharpe = None
        if len(returns) >= 5:
            avg = mean(returns)
            std = math.sqrt(sum((r - avg) ** 2 for r in returns) / (len(returns) - 1))
            if std > 0:
                sharpe = round((avg / std) * math.sqrt(252), 2)
        return {
            "sample_size": len(trades),
            "win_rate": round((len(wins) / len(trades)) * 100, 2),
            "average_return_pct": round(sum(t["return_pct"] for t in trades) / len(trades), 2),
            "total_return_pct": round(((final_equity - self.initial_equity) / self.initial_equity) * 100, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
            "expectancy": round(sum(t["pnl"] for t in trades) / len(trades), 2),
            "sharpe": sharpe,
            "total_fees": round(sum(t.get("fees", 0) for t in trades), 2),
        }


def run_strategy(spec: StrategySpec, candles: list[Candle], timeframe: str = "daily", settings: AppSettings | None = None) -> dict[str, Any]:
    return StrategyEngine(spec, settings).run(candles, timeframe)


# -------- Indicator helpers (lightweight wrappers around services.indicators) --------

def _sma_at(values: list[float], index: int, period: int) -> float | None:
    if index + 1 < period:
        return None
    return sma(values[: index + 1], period)


def _macd_histogram(values: list[float], fast: int, slow: int, signal: int) -> list[float | None]:
    if len(values) < slow + signal:
        return [None] * len(values)
    fast_series = ema_series(values, fast)
    slow_series = ema_series(values, slow)
    line = [f - s for f, s in zip(fast_series, slow_series)]
    sig_series = ema_series(line, signal)
    histogram = [None] * (len(values) - len(sig_series)) + [line[i] - sig_series[i] for i in range(len(sig_series))]
    return histogram[: len(values)]


def _donchian_high(highs: list[float], period: int) -> list[float | None]:
    return [None if idx + 1 < period else max(highs[idx + 1 - period : idx + 1]) for idx in range(len(highs))]


def _donchian_low(lows: list[float], period: int) -> list[float | None]:
    return [None if idx + 1 < period else min(lows[idx + 1 - period : idx + 1]) for idx in range(len(lows))]


def _bollinger(values: list[float], period: int) -> tuple[list[float | None], list[float | None], list[float | None]]:
    upper: list[float | None] = []
    lower: list[float | None] = []
    middle: list[float | None] = []
    for idx in range(len(values)):
        if idx + 1 < period:
            upper.append(None)
            lower.append(None)
            middle.append(None)
            continue
        window = values[idx + 1 - period : idx + 1]
        m = mean(window)
        std = math.sqrt(sum((v - m) ** 2 for v in window) / (len(window) - 1))
        upper.append(m + 2 * std)
        lower.append(m - 2 * std)
        middle.append(m)
    return upper, lower, middle


def _both(a: Any, b: Any) -> bool:
    return a is not None and b is not None


def _slip(price: float, side: str, bps: float) -> float:
    factor = bps / 10000
    return price * (1 + factor) if side == "BUY" else price * (1 - factor)
