from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from groww_trader.services.ai_settings import (
    AiSettingsService,
    REASON_DISABLED,
    REASON_NO_HEARTBEAT,
    REASON_OK,
)
from groww_trader.services.groww_data import (
    GROWW_ALLOWED_USES,
    GrowwUsageDeniedError,
    assert_groww_use,
)
from groww_trader.services.market_data import GrowwMarketFallbackProvider, MarketDataRequest
from groww_trader.services.session_service import SessionService, current_session_date
from groww_trader.services.storage import Storage


def _storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "db.sqlite3")


def test_current_session_date_rolls_at_6am_ist():
    ist = timezone(timedelta(hours=5, minutes=30))
    pre_roll = datetime(2026, 5, 21, 5, 0, tzinfo=ist).astimezone(timezone.utc)
    post_roll = datetime(2026, 5, 21, 7, 0, tzinfo=ist).astimezone(timezone.utc)
    assert current_session_date(pre_roll) == "2026-05-20"
    assert current_session_date(post_roll) == "2026-05-21"


def test_session_shortlist_dedupes_and_records_events(tmp_path: Path) -> None:
    service = SessionService(_storage(tmp_path))

    service.add_to_shortlist("RELIANCE", reason="trend uptick")
    service.add_to_shortlist("reliance", reason="already there")  # dedupe + uppercase
    service.add_to_shortlist("TCS", reason="strong sector")

    current = service.current()
    symbols = [item["symbol"] for item in current["shortlist"]]
    assert symbols == ["RELIANCE", "TCS"]

    service.remove_from_shortlist("RELIANCE")
    assert [item["symbol"] for item in service.current()["shortlist"]] == ["TCS"]

    events = service.events_since()
    kinds = [event["kind"] for event in events]
    assert "shortlist_added" in kinds
    assert "shortlist_removed" in kinds


def test_session_picks_overwrite_and_record_event(tmp_path: Path) -> None:
    service = SessionService(_storage(tmp_path))
    service.set_picks(
        [
            {"symbol": "RELIANCE", "direction": "long", "sized_qty": 5},
            {"symbol": "TCS", "direction": "short"},
            {"symbol": "TCS"},  # dedupe
        ]
    )
    picks = service.current()["picks"]
    assert [pick["symbol"] for pick in picks] == ["RELIANCE", "TCS"]
    assert picks[1]["direction"] == "short"

    service.remove_pick("RELIANCE")
    assert [pick["symbol"] for pick in service.current()["picks"]] == ["TCS"]


def test_ai_gate_disabled_by_user(tmp_path: Path) -> None:
    service = AiSettingsService(_storage(tmp_path))
    service.update(ai_enabled=False)
    decision = service.gate()
    assert decision.allowed is False
    assert decision.reason == REASON_DISABLED


def test_ai_gate_requires_recent_heartbeat(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    service = AiSettingsService(storage)

    # Default: heartbeat never recorded -> gate closed.
    decision = service.gate()
    assert decision.allowed is False
    assert decision.reason == REASON_NO_HEARTBEAT

    # Recording a fresh heartbeat opens the gate.
    service.heartbeat()
    assert service.gate().reason == REASON_OK

    # An expired heartbeat closes it again.
    storage.update_ai_settings(last_heartbeat_at=time.time() - 24 * 3600)
    assert service.gate().reason == REASON_NO_HEARTBEAT


def test_ai_circuit_breaker_opens_then_recovers(tmp_path: Path) -> None:
    service = AiSettingsService(_storage(tmp_path))
    service.heartbeat()

    for _ in range(AiSettingsService.CIRCUIT_FAILURE_THRESHOLD):
        service.record_failure()
    decision = service.gate()
    assert decision.allowed is False
    assert decision.reason == "circuit_open"
    assert decision.seconds_until_retry and decision.seconds_until_retry > 0

    # A success clears the breaker even before cooldown ends.
    service.record_success()
    assert service.gate().reason == REASON_OK


def test_event_trigger_toggle(tmp_path: Path) -> None:
    service = AiSettingsService(_storage(tmp_path))
    assert service.event_trigger_enabled("near_stop") is True
    service.update(event_triggers={"near_stop": False, "vol_spike": True})
    assert service.event_trigger_enabled("near_stop") is False
    assert service.event_trigger_enabled("vol_spike") is True


def test_groww_use_allowlist_blocks_market_data() -> None:
    for use in ("account", "positions", "orders", "instruments"):
        assert use in GROWW_ALLOWED_USES
        assert_groww_use(use)
    with pytest.raises(GrowwUsageDeniedError):
        assert_groww_use("candles")
    with pytest.raises(GrowwUsageDeniedError):
        assert_groww_use("ltp")
    with pytest.raises(GrowwUsageDeniedError):
        assert_groww_use("option_chain")


def test_groww_fallback_provider_refuses_market_data() -> None:
    class _DummyGroww:
        def client(self):
            raise AssertionError("Groww client should not be touched")

    provider = GrowwMarketFallbackProvider(_DummyGroww())
    assert provider.supports_interval(5) is False
    assert provider.supports_interval(1440) is False
    with pytest.raises(RuntimeError):
        provider.historical_candles(MarketDataRequest("RELIANCE", 5, 30))
