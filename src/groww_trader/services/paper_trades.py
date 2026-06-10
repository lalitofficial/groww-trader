from __future__ import annotations

from typing import Any

from groww_trader.settings import AppSettings

from .market_data import MarketDataRouter
from .storage import Storage


class PaperTradeService:
    """Paper trading ledger with slippage + STT/CTT modeling."""

    def __init__(self, storage: Storage, market_data: MarketDataRouter, settings: AppSettings) -> None:
        self.storage = storage
        self.market_data = market_data
        self.settings = settings

    def open(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = payload["symbol"].upper()
        product = (payload.get("product") or "intraday").lower()
        side = (payload.get("side") or "BUY").upper()
        requested_price = float(payload["entry_price"])
        quantity = float(payload["quantity"])
        slipped_price = _apply_slippage(requested_price, side, self.settings.paper_slippage_bps)
        brokerage = self.settings.paper_brokerage_per_trade
        stt_pct = self.settings.paper_stt_pct_intraday if product == "intraday" else self.settings.paper_stt_pct_delivery
        entry_fees = brokerage + (slipped_price * quantity * (stt_pct / 100))
        opened = self.storage.open_paper_trade(
            {
                "symbol": symbol,
                "side": side,
                "product": product,
                "quantity": quantity,
                "entry_price": slipped_price,
                "stop_loss": payload.get("stop_loss"),
                "target": payload.get("target"),
                "fees": entry_fees,
                "strategy_id": payload.get("strategy_id"),
                "timeframe": payload.get("timeframe"),
                "grade": payload.get("grade"),
                "notes": payload.get("notes"),
                "metadata": {
                    **(payload.get("metadata") or {}),
                    "requested_price": requested_price,
                    "slippage_bps": self.settings.paper_slippage_bps,
                },
            }
        )
        return opened

    def close(self, trade_id: int, exit_price: float, notes: str | None = None) -> dict[str, Any] | None:
        trade = self.storage.paper_trade(trade_id)
        if not trade or trade["status"] != "open":
            return trade
        side = trade["side"]
        # Exiting BUY = SELL at exit (slip down); Exiting SELL = BUY-to-cover (slip up).
        exit_side = "SELL" if side == "BUY" else "BUY"
        slipped_exit = _apply_slippage(exit_price, exit_side, self.settings.paper_slippage_bps)
        product = (trade.get("product") or "intraday").lower()
        stt_pct = self.settings.paper_stt_pct_intraday if product == "intraday" else self.settings.paper_stt_pct_delivery
        exit_fees = self.settings.paper_brokerage_per_trade + (slipped_exit * trade["quantity"] * (stt_pct / 100))
        return self.storage.close_paper_trade(trade_id, slipped_exit, fees=exit_fees, notes=notes)

    def list_trades(self, status: str | None = None, symbol: str | None = None, limit: int = 100) -> dict[str, Any]:
        items = self.storage.list_paper_trades(status=status, symbol=symbol, limit=limit)
        # Mark-to-market for open trades.
        for trade in items:
            if trade["status"] == "open":
                quote = self.market_data.latest_quote(trade["symbol"])
                if quote:
                    sign = 1 if trade["side"] == "BUY" else -1
                    mtm = sign * (quote["ltp"] - trade["entry_price"]) * trade["quantity"] - (trade["fees"] or 0)
                    trade["live_price"] = quote["ltp"]
                    trade["mtm_pnl"] = round(mtm, 2)
        return {"items": items, "count": len(items)}

    def summary(self) -> dict[str, Any]:
        return self.storage.paper_trade_summary()

    def auto_open_from_signal(
        self,
        symbol: str,
        signal: dict[str, Any],
        analysis: dict[str, Any],
        timeframe: str,
    ) -> dict[str, Any] | None:
        """Open a paper trade from a deterministic intraday/scanner signal if not already open."""
        existing = self.storage.list_paper_trades(status="open", symbol=symbol)
        if existing:
            return None
        entry = signal.get("entry") or analysis.get("last_price")
        stop = signal.get("stop") or (analysis.get("trade_plan") or {}).get("stop_loss")
        if not entry or not stop:
            return None
        side = "BUY" if signal.get("direction") == "long" else "SELL"
        risk_per_share = abs(entry - stop)
        if risk_per_share <= 0:
            return None
        leverage = self.settings.intraday_leverage if timeframe != "daily" else 1.0
        risk_budget = self.settings.paper_capital * (self.settings.risk_per_trade_pct / 100)
        max_position_value = self.settings.paper_capital * (self.settings.intraday_max_position_pct / 100) * leverage
        quantity_by_risk = max(1, int(risk_budget / risk_per_share))
        quantity_by_cap = max(1, int(max_position_value / entry)) if entry else quantity_by_risk
        quantity = min(quantity_by_risk, quantity_by_cap)
        return self.open(
            {
                "symbol": symbol,
                "side": side,
                "product": "intraday" if timeframe != "daily" else "delivery",
                "quantity": quantity,
                "entry_price": entry,
                "stop_loss": stop,
                "target": _first_target(analysis),
                "strategy_id": signal.get("id") or signal.get("name"),
                "timeframe": timeframe,
                "grade": (analysis.get("trade_plan") or {}).get("grade"),
                "notes": signal.get("trigger"),
                "metadata": {"auto": True, "signal": signal.get("name")},
            }
        )


def _apply_slippage(price: float, side: str, bps: float) -> float:
    factor = bps / 10000
    return round(price * (1 + factor) if side == "BUY" else price * (1 - factor), 2)


def _first_target(analysis: dict[str, Any]) -> float | None:
    plan = analysis.get("trade_plan") or {}
    targets = plan.get("targets") or []
    if not targets:
        return None
    first = targets[0]
    if isinstance(first, dict):
        try:
            return float(first.get("price"))
        except (TypeError, ValueError):
            return None
    return None
