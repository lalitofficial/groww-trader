from __future__ import annotations

import math
from statistics import mean
from typing import Any

from groww_trader.settings import AppSettings

from .indicators import Candle, atr, opening_range, rsi, session_vwap_series, sma, supertrend

try:
    import backtesting as backtesting_engine
except Exception:  # pragma: no cover
    backtesting_engine = None


STRATEGIES = {
    "ma_trend_pullback": "MA trend pullback",
    "supertrend_follow": "Supertrend trend-follow",
    "rsi_mean_reversion": "RSI mean-reversion",
    "breakout_retest": "Breakout / retest",
    "orb_intraday": "Opening range breakout (intraday)",
    "vwap_reclaim_intraday": "VWAP reclaim (intraday)",
}


def run_backtest(
    candles: list[Candle],
    strategy_id: str,
    params: dict[str, Any] | None = None,
    timeframe: str = "daily",
    settings: AppSettings | None = None,
) -> dict[str, Any]:
    params = params or {}
    if len(candles) < 60:
        return {
            "strategy_id": strategy_id,
            "metrics": {},
            "trades": [],
            "equity_curve": [],
            "warnings": ["Insufficient candles for a reliable backtest."],
        }
    if strategy_id not in STRATEGIES:
        strategy_id = "ma_trend_pullback"

    initial_equity = float(params.get("initial_equity") or (settings.account_capital if settings else 100000))
    risk_pct = float(params.get("risk_pct") or (settings.risk_per_trade_pct if settings else 1.0))
    is_intraday = timeframe not in {"daily", "weekly"} or strategy_id in {"orb_intraday", "vwap_reclaim_intraday"}

    slippage_bps = float(params.get("slippage_bps") or (settings.paper_slippage_bps if settings else 5))
    brokerage = float(params.get("brokerage") or (settings.paper_brokerage_per_trade if settings else 20))
    stt_pct = float(
        params.get("stt_pct")
        or (settings.paper_stt_pct_intraday if is_intraday and settings else (settings.paper_stt_pct_delivery if settings else 0.1))
    )

    trades = _simulate(candles, strategy_id, initial_equity, risk_pct, slippage_bps, brokerage, stt_pct, is_intraday)
    equity_curve = _equity_curve(initial_equity, trades)
    metrics = _metrics(initial_equity, trades, equity_curve)
    warnings = [
        f"Cost model: slippage {slippage_bps}bps, brokerage ₹{brokerage}/trade, STT {stt_pct}% per side.",
        "Educational backtest. Past performance ≠ future results.",
    ]
    return {
        "strategy_id": strategy_id,
        "strategy_name": STRATEGIES[strategy_id],
        "engine": "internal-cost-aware",
        "timeframe": timeframe,
        "metrics": metrics,
        "trades": trades[-50:],
        "equity_curve": equity_curve,
        "warnings": warnings,
    }


def _simulate(
    candles: list[Candle],
    strategy_id: str,
    initial_equity: float,
    risk_pct: float,
    slippage_bps: float,
    brokerage: float,
    stt_pct: float,
    is_intraday: bool,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None
    st = supertrend(candles) if strategy_id == "supertrend_follow" else []
    vwap_values = session_vwap_series(candles) if strategy_id in {"vwap_reclaim_intraday", "orb_intraday"} else []
    or_state = _build_or_states(candles) if strategy_id == "orb_intraday" else {}

    for index in range(50, len(candles) - 1):
        candle = candles[index]
        next_candle = candles[index + 1]
        entry_signal = _entry_signal(candles, index, strategy_id, st, vwap_values, or_state)
        if position is None and entry_signal:
            direction = entry_signal.get("direction", "long")
            stop = _stop(candles, index, direction, strategy_id, or_state)
            slip_entry = _apply_slip(next_candle.open, "BUY" if direction == "long" else "SELL", slippage_bps)
            risk = abs(slip_entry - stop) or candle.close * 0.01
            quantity = max(1, int((initial_equity * (risk_pct / 100)) / risk))
            entry_fees = brokerage + (slip_entry * quantity * (stt_pct / 100))
            position = {
                "entry_time": next_candle.timestamp,
                "entry": round(slip_entry, 2),
                "stop": stop,
                "quantity": quantity,
                "direction": direction,
                "strategy": strategy_id,
                "entry_fees": entry_fees,
            }
            continue
        if position:
            exit_reason = _exit_signal(candles, index, strategy_id, st, position, is_intraday)
            if exit_reason:
                exit_side = "SELL" if position["direction"] == "long" else "BUY"
                exit_price = _apply_slip(next_candle.open, exit_side, slippage_bps)
                exit_fees = brokerage + (exit_price * position["quantity"] * (stt_pct / 100))
                sign = 1 if position["direction"] == "long" else -1
                gross = sign * (exit_price - position["entry"]) * position["quantity"]
                pnl = gross - position["entry_fees"] - exit_fees
                ret = ((exit_price - position["entry"]) / position["entry"]) * 100 * sign
                trades.append(
                    {
                        **position,
                        "exit_time": next_candle.timestamp,
                        "exit": round(exit_price, 2),
                        "gross_pnl": round(gross, 2),
                        "fees": round(position["entry_fees"] + exit_fees, 2),
                        "pnl": round(pnl, 2),
                        "return_pct": round(ret, 2),
                        "exit_reason": exit_reason,
                    }
                )
                position = None
    return trades


def _entry_signal(
    candles: list[Candle],
    index: int,
    strategy_id: str,
    st: list[dict[str, Any]],
    vwap_values: list[float],
    or_state: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    closes = [c.close for c in candles[: index + 1]]
    candle = candles[index]
    previous = candles[index - 1]

    if strategy_id == "ma_trend_pullback":
        ma20 = sma(closes, 20)
        ma50 = sma(closes, 50)
        if ma20 and ma50 and candle.close > ma50 and previous.close < ma20 <= candle.close:
            return {"direction": "long"}
    if strategy_id == "supertrend_follow":
        if st and st[index].get("direction") == "bullish" and st[index - 1].get("direction") == "bearish":
            return {"direction": "long"}
    if strategy_id == "rsi_mean_reversion":
        rsi_value = rsi(closes)
        prev_rsi = rsi(closes[:-1])
        if prev_rsi and rsi_value and prev_rsi < 35 <= rsi_value:
            return {"direction": "long"}
    if strategy_id == "breakout_retest":
        high20 = max(c.high for c in candles[index - 20 : index])
        avg_vol = sum(c.volume for c in candles[index - 20 : index]) / 20
        if candle.close > high20 and candle.volume > avg_vol * 1.2:
            return {"direction": "long"}
    if strategy_id == "vwap_reclaim_intraday":
        if vwap_values and index >= 1:
            vwap_now = vwap_values[index]
            if previous.close < vwap_now <= candle.close:
                return {"direction": "long"}
    if strategy_id == "orb_intraday":
        state = or_state.get(index)
        if state and state.get("just_broken") == "up":
            return {"direction": "long"}
        if state and state.get("just_broken") == "down":
            return {"direction": "short"}
    return None


def _exit_signal(
    candles: list[Candle],
    index: int,
    strategy_id: str,
    st: list[dict[str, Any]],
    position: dict[str, Any],
    is_intraday: bool,
) -> str | None:
    candle = candles[index]
    direction = position["direction"]
    stop = position["stop"]
    entry = position["entry"]
    risk = abs(entry - stop)

    if direction == "long" and candle.low <= stop:
        return "stop"
    if direction == "short" and candle.high >= stop:
        return "stop"

    if direction == "long" and candle.high >= entry + (2 * risk):
        return "target_2r"
    if direction == "short" and candle.low <= entry - (2 * risk):
        return "target_2r"

    if strategy_id == "supertrend_follow" and st and st[index].get("direction") == "bearish":
        return "supertrend_flip"

    if is_intraday:
        # Square off at the end of session (~6.25 hours = 22500s from session open guess).
        if candle.timestamp - position["entry_time"] >= 6 * 3600:
            return "eod_square_off"
    else:
        if candle.timestamp - position["entry_time"] > 30 * 86400:
            return "time_exit"
    return None


def _stop(candles: list[Candle], index: int, direction: str, strategy_id: str, or_state: dict[int, dict[str, Any]]) -> float:
    atr_value = atr(candles[: index + 1]) or 0
    swing_low = min(c.low for c in candles[max(0, index - 10) : index + 1])
    swing_high = max(c.high for c in candles[max(0, index - 10) : index + 1])
    if strategy_id == "orb_intraday":
        state = or_state.get(index) or {}
        if direction == "long" and state.get("or_low") is not None:
            return round(state["or_low"] - atr_value * 0.25, 2)
        if direction == "short" and state.get("or_high") is not None:
            return round(state["or_high"] + atr_value * 0.25, 2)
    if direction == "long":
        return round(min(swing_low, candles[index].close - atr_value * 1.5), 2)
    return round(max(swing_high, candles[index].close + atr_value * 1.5), 2)


def _build_or_states(candles: list[Candle]) -> dict[int, dict[str, Any]]:
    from datetime import datetime, timezone

    states: dict[int, dict[str, Any]] = {}
    session_id: str | None = None
    session_first_idx = 0
    current_or_high: float | None = None
    current_or_low: float | None = None
    broken: str | None = None
    or_bars = 3
    for index, candle in enumerate(candles):
        candle_session = datetime.fromtimestamp(candle.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
        if candle_session != session_id:
            session_id = candle_session
            session_first_idx = index
            current_or_high = None
            current_or_low = None
            broken = None
        bars_in = index - session_first_idx + 1
        if bars_in <= or_bars:
            window = candles[session_first_idx : index + 1]
            current_or_high = max(c.high for c in window)
            current_or_low = min(c.low for c in window)
            states[index] = {"or_high": current_or_high, "or_low": current_or_low, "just_broken": None}
            continue
        just_broken: str | None = None
        if broken is None and current_or_high is not None and candle.close > current_or_high:
            just_broken = "up"
            broken = "up"
        elif broken is None and current_or_low is not None and candle.close < current_or_low:
            just_broken = "down"
            broken = "down"
        states[index] = {"or_high": current_or_high, "or_low": current_or_low, "just_broken": just_broken}
    return states


def _apply_slip(price: float, side: str, bps: float) -> float:
    factor = bps / 10000
    return price * (1 + factor) if side == "BUY" else price * (1 - factor)


def _equity_curve(initial_equity: float, trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equity = initial_equity
    curve = [{"index": 0, "equity": round(equity, 2)}]
    for index, trade in enumerate(trades, start=1):
        equity += trade["pnl"]
        curve.append({"index": index, "time": trade["exit_time"], "equity": round(equity, 2)})
    return curve


def _metrics(initial_equity: float, trades: list[dict[str, Any]], equity_curve: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"sample_size": 0, "win_rate": 0, "total_return_pct": 0, "max_drawdown_pct": 0, "profit_factor": None, "expectancy": 0, "sharpe": None}
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] <= 0]
    gross_profit = sum(trade["pnl"] for trade in wins)
    gross_loss = abs(sum(trade["pnl"] for trade in losses))
    final_equity = equity_curve[-1]["equity"]
    peak = initial_equity
    max_drawdown = 0.0
    returns: list[float] = []
    prev_equity = initial_equity
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
        "average_return_pct": round(sum(trade["return_pct"] for trade in trades) / len(trades), 2),
        "total_return_pct": round(((final_equity - initial_equity) / initial_equity) * 100, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "expectancy": round(sum(trade["pnl"] for trade in trades) / len(trades), 2),
        "sharpe": sharpe,
        "total_fees": round(sum(trade.get("fees", 0) for trade in trades), 2),
    }
