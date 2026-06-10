from __future__ import annotations

import hashlib
import time
from typing import Any

from groww_trader.config import load_settings
from groww_trader.groww_client import create_groww_client, groww_constant

from .scanner import ScannerService
from .storage import Storage


class AccountService:
    def __init__(self, storage: Storage, scanner: ScannerService) -> None:
        self.storage = storage
        self.scanner = scanner
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ttl_seconds = 30

    def client(self) -> Any:
        return create_groww_client(load_settings())

    def summary(self) -> dict[str, Any]:
        margin = self._safe_call("margin", lambda client: client.get_available_margin_details())
        positions = self.positions()
        holdings = self.holdings()
        orders = self.orders(page_size=10)
        return {
            "margin": margin,
            "positions_count": len(positions["items"]),
            "holdings_count": len(holdings["items"]),
            "orders_count": len(orders["items"]),
            "errors": _collect_errors(margin, positions, holdings, orders),
            "read_only": True,
        }

    def holdings(self) -> dict[str, Any]:
        payload = self._safe_call("holdings", lambda client: client.get_holdings_for_user())
        return _items_response(payload, normalize_holding)

    def positions(self) -> dict[str, Any]:
        payload = self._safe_call(
            "positions",
            lambda client: client.get_positions_for_user(segment=groww_constant(client, "SEGMENT", "CASH")),
        )
        return _items_response(payload, normalize_position)

    def orders(self, page: int = 0, page_size: int = 25) -> dict[str, Any]:
        payload = self._safe_call(
            "orders",
            lambda client: client.get_order_list(
                page=page,
                page_size=page_size,
                segment=groww_constant(client, "SEGMENT", "CASH"),
            ),
        )
        response = _items_response(payload, normalize_order)
        self.storage.upsert_order_statuses(response["items"])
        return response

    def order_detail(self, order_id: str, segment: str = "CASH") -> dict[str, Any]:
        detail = self._safe_call(
            "order_detail",
            lambda client: client.get_order_detail(
                segment=groww_constant(client, "SEGMENT", segment),
                groww_order_id=order_id,
            ),
        )
        status = self._safe_call(
            "order_status",
            lambda client: client.get_order_status(
                segment=groww_constant(client, "SEGMENT", segment),
                groww_order_id=order_id,
            ),
        )
        trades = self._safe_call(
            "order_trades",
            lambda client: client.get_trade_list_for_order(
                groww_order_id=order_id,
                segment=groww_constant(client, "SEGMENT", segment),
                page=0,
                page_size=25,
            ),
        )
        return {"detail": detail, "status": status, "trades": trades}

    def evaluate_alerts(self, symbol: str | None = None) -> dict[str, Any]:
        positions = self.positions()["items"]
        holdings = self.holdings()["items"]
        live_rows = positions + holdings
        if symbol:
            live_rows = [row for row in live_rows if row.get("symbol") == symbol.upper()]
        events: list[dict[str, Any]] = []
        for row in live_rows:
            row_symbol = row.get("symbol")
            if not row_symbol:
                continue
            try:
                analysis = self.scanner.detail(row_symbol)
            except Exception:
                continue
            events.extend(evaluate_symbol_alerts(row, analysis))
        self.storage.upsert_alert_events(events)
        return {"items": events, "count": len(events)}

    def alerts(self, symbol: str | None = None) -> dict[str, Any]:
        items = self.storage.list_alert_events(symbol=symbol)
        return {"items": items, "count": len(items)}

    def position_context(self, symbol: str, analysis: dict[str, Any] | None = None) -> dict[str, Any] | None:
        symbol = symbol.upper()
        rows = self.positions()["items"] + self.holdings()["items"]
        match = next((row for row in rows if row.get("symbol") == symbol), None)
        if not match:
            return None
        analysis = analysis or self.scanner.detail(symbol)
        daily = analysis.get("daily_analysis", {})
        price = daily.get("last_price") or match.get("current_price")
        support = daily.get("support")
        resistance = daily.get("resistance")
        return {
            **match,
            "current_price": price,
            "nearest_support": support,
            "nearest_resistance": resistance,
            "distance_to_support_pct": _pct_distance(price, support),
            "distance_to_resistance_pct": _pct_distance(price, resistance),
            "risk_reward": daily.get("risk_reward"),
        }

    def _safe_call(self, source: str, fn: Any) -> dict[str, Any]:
        cached = self._cache.get(source)
        if cached and time.time() - cached[0] <= self._ttl_seconds:
            return cached[1]
        try:
            payload = {"source": source, "ok": True, "raw": fn(self.client())}
        except Exception as exc:
            payload = {"source": source, "ok": False, "error": str(exc), "raw": {}}
        self._cache[source] = (time.time(), payload)
        return payload


def normalize_holding(row: dict[str, Any]) -> dict[str, Any]:
    symbol = _symbol(row)
    quantity = _num(row, "quantity", "qty", "holding_qty", "total_quantity", "free_quantity")
    average_price = _num(row, "average_price", "avg_price", "avg_buy_price", "average_buy_price")
    current_price = _num(row, "ltp", "last_price", "current_price")
    return {
        "kind": "holding",
        "symbol": symbol,
        "company": row.get("company_name") or row.get("name") or symbol,
        "quantity": quantity,
        "average_price": average_price,
        "current_price": current_price,
        "day_pnl": _num(row, "day_pnl", "dayProfitAndLoss", "today_pnl"),
        "unrealized_pnl": _num(row, "unrealized_pnl", "profit_and_loss", "pnl"),
        "raw": row,
    }


def normalize_position(row: dict[str, Any]) -> dict[str, Any]:
    symbol = _symbol(row)
    quantity = _num(row, "net_quantity", "quantity", "qty", "position_quantity")
    average_price = _num(row, "average_price", "avg_price", "buy_average_price", "average_buy_price")
    current_price = _num(row, "ltp", "last_price", "current_price")
    return {
        "kind": "position",
        "symbol": symbol,
        "company": row.get("company_name") or row.get("name") or symbol,
        "quantity": quantity,
        "average_price": average_price,
        "current_price": current_price,
        "day_pnl": _num(row, "day_pnl", "dayProfitAndLoss", "today_pnl"),
        "unrealized_pnl": _num(row, "unrealized_pnl", "profit_and_loss", "pnl"),
        "product": row.get("product") or row.get("product_type"),
        "raw": row,
    }


def normalize_order(row: dict[str, Any]) -> dict[str, Any]:
    order_id = str(row.get("groww_order_id") or row.get("order_id") or row.get("id") or "")
    return {
        "order_id": order_id,
        "symbol": _symbol(row),
        "status": row.get("status") or row.get("order_status"),
        "transaction_type": row.get("transaction_type") or row.get("side"),
        "order_type": row.get("order_type"),
        "product": row.get("product") or row.get("product_type"),
        "quantity": _num(row, "quantity", "qty", "ordered_quantity"),
        "filled_quantity": _num(row, "filled_quantity", "traded_quantity"),
        "price": _num(row, "price", "order_price"),
        "created_at": row.get("created_at") or row.get("created_time") or row.get("order_time"),
        "raw": row,
    }


def evaluate_symbol_alerts(position: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    daily = analysis.get("daily_analysis", {})
    symbol = position.get("symbol") or analysis.get("symbol")
    price = _as_float(daily.get("last_price") or position.get("current_price"))
    support = _as_float(daily.get("support"))
    resistance = _as_float(daily.get("resistance"))
    volume_expansion = _as_float(daily.get("volume_expansion"))
    rr = _as_float(daily.get("risk_reward"))
    events: list[dict[str, Any]] = []
    if not symbol or not price:
        return events
    if support:
        distance = ((price - support) / price) * 100
        if 0 <= distance <= 2:
            events.append(_event(symbol, "warning", "Near support", f"{symbol} is {distance:.2f}% above support {support}.", 2, price, support))
        if price < support:
            events.append(_event(symbol, "critical", "Support break", f"{symbol} is trading below support {support}.", support, price, support))
    if resistance:
        distance = ((resistance - price) / price) * 100
        if 0 <= distance <= 2:
            events.append(_event(symbol, "info", "Near resistance", f"{symbol} is {distance:.2f}% below resistance {resistance}.", 2, price, resistance))
        if price > resistance:
            events.append(_event(symbol, "info", "Resistance breakout", f"{symbol} is trading above resistance {resistance}.", resistance, price, resistance))
    if volume_expansion and volume_expansion >= 1.8:
        events.append(_event(symbol, "info", "Abnormal volume", f"{symbol} volume is {volume_expansion}x its 20-period average.", 1.8, volume_expansion, None))
    if rr is not None and rr < 1:
        events.append(_event(symbol, "warning", "Risk/reward deteriorated", f"{symbol} current risk/reward is {rr}.", 1, rr, None))
    return events


def _event(symbol: str, severity: str, title: str, message: str, trigger: float, current: float, level: float | None) -> dict[str, Any]:
    key_src = f"{symbol}|{title}|{round(current, 2)}|{round(level or 0, 2)}"
    return {
        "event_key": hashlib.sha1(key_src.encode()).hexdigest(),
        "symbol": symbol,
        "severity": severity,
        "title": title,
        "message": message,
        "trigger_value": trigger,
        "current_value": current,
        "related_level": level,
    }


def _items_response(payload: dict[str, Any], normalizer: Any) -> dict[str, Any]:
    if not payload.get("ok"):
        return {"items": [], "count": 0, "error": payload.get("error"), "raw": payload.get("raw", {})}
    raw = payload.get("raw") or {}
    items = _extract_items(raw)
    normalized = [normalizer(item) for item in items if isinstance(item, dict)]
    return {"items": normalized, "count": len(normalized), "raw": raw}


def _extract_items(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    for key in ("items", "data", "orders", "holdings", "positions", "trades", "results"):
        value = raw.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return []


def _symbol(row: dict[str, Any]) -> str:
    symbol = row.get("trading_symbol") or row.get("symbol") or row.get("groww_symbol") or row.get("exchange_trading_symbol") or ""
    symbol = str(symbol).upper()
    return symbol.replace("NSE-", "").replace("NSE_", "")


def _num(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_distance(price: Any, level: Any) -> float | None:
    price_value = _as_float(price)
    level_value = _as_float(level)
    if not price_value or not level_value:
        return None
    return round(((level_value - price_value) / price_value) * 100, 2)


def _collect_errors(*responses: dict[str, Any]) -> list[str]:
    return [response["error"] for response in responses if response.get("error")]
