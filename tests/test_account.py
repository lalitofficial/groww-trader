from groww_trader.services.account import evaluate_symbol_alerts, normalize_holding, normalize_order, normalize_position


def test_normalize_holding_maps_common_fields():
    row = {
        "trading_symbol": "RELIANCE",
        "company_name": "Reliance Industries",
        "quantity": "10",
        "average_price": "1200.5",
        "ltp": "1325",
        "pnl": "1245",
    }
    holding = normalize_holding(row)
    assert holding["symbol"] == "RELIANCE"
    assert holding["quantity"] == 10
    assert holding["average_price"] == 1200.5
    assert holding["unrealized_pnl"] == 1245


def test_normalize_position_maps_common_fields():
    row = {
        "groww_symbol": "NSE-INFY",
        "net_quantity": 5,
        "buy_average_price": 1400,
        "last_price": 1450,
        "day_pnl": 50,
    }
    position = normalize_position(row)
    assert position["symbol"] == "INFY"
    assert position["quantity"] == 5
    assert position["average_price"] == 1400
    assert position["current_price"] == 1450


def test_normalize_order_is_read_only_shape():
    row = {
        "groww_order_id": "abc",
        "trading_symbol": "TCS",
        "order_status": "COMPLETED",
        "transaction_type": "BUY",
        "quantity": 2,
    }
    order = normalize_order(row)
    assert order["order_id"] == "abc"
    assert order["symbol"] == "TCS"
    assert order["status"] == "COMPLETED"


def test_evaluate_symbol_alerts_flags_near_support_and_bad_rr():
    position = {"symbol": "RELIANCE", "current_price": 100}
    analysis = {
        "daily_analysis": {
            "last_price": 100,
            "support": 99,
            "resistance": 104,
            "volume_expansion": 1.0,
            "risk_reward": 0.7,
        }
    }
    events = evaluate_symbol_alerts(position, analysis)
    titles = {event["title"] for event in events}
    assert "Near support" in titles
    assert "Risk/reward deteriorated" in titles
