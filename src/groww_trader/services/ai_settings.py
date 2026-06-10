from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .storage import Storage


# Reasons returned by check_can_run. Frontend uses these to render the AI status pill.
REASON_OK = "ok"
REASON_DISABLED = "disabled_by_user"
REASON_NO_HEARTBEAT = "no_heartbeat"
REASON_CIRCUIT_OPEN = "circuit_open"


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    seconds_until_retry: float | None = None


class AiSettingsService:
    """Single chokepoint for all AI calls.

    Every Azure OpenAI call goes through `gate()`. If it returns `allowed=False`
    callers should silently skip (no error to user) and surface a deterministic
    fallback. This way the kill-switch and heartbeat protect us when the
    frontend isn't actively in use.

    The frontend pings POST /api/ai/heartbeat every 60s while any AI-relevant
    page is mounted. If the gap between now and `last_heartbeat_at` exceeds
    `heartbeat_grace_seconds` (default 600 = 10 minutes), AI auto-mutes.
    """

    CIRCUIT_FAILURE_THRESHOLD = 5
    CIRCUIT_COOLDOWN_SECONDS = 300

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    # ---- Reads ----
    def settings(self) -> dict[str, Any]:
        return self.storage.ai_settings()

    def status(self) -> dict[str, Any]:
        decision = self.gate()
        cfg = self.settings()
        return {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "ai_enabled": cfg["ai_enabled"],
            "commentary_enabled": cfg["commentary_enabled"],
            "commentary_cadence_seconds": cfg["commentary_cadence_seconds"],
            "require_heartbeat": cfg["require_heartbeat"],
            "heartbeat_grace_seconds": cfg["heartbeat_grace_seconds"],
            "last_heartbeat_at": cfg["last_heartbeat_at"],
            "seconds_since_heartbeat": (time.time() - cfg["last_heartbeat_at"]) if cfg["last_heartbeat_at"] else None,
            "circuit_open_until": cfg["circuit_open_until"],
            "consecutive_failures": cfg["consecutive_failures"],
            "event_triggers": cfg["event_triggers"],
        }

    # ---- Gate ----
    def gate(self) -> GateDecision:
        cfg = self.settings()
        if not cfg["ai_enabled"]:
            return GateDecision(False, REASON_DISABLED)
        now = time.time()
        if cfg["circuit_open_until"] and cfg["circuit_open_until"] > now:
            return GateDecision(False, REASON_CIRCUIT_OPEN, seconds_until_retry=cfg["circuit_open_until"] - now)
        if cfg["require_heartbeat"]:
            last = cfg["last_heartbeat_at"]
            grace = cfg["heartbeat_grace_seconds"]
            if not last or (now - last) > grace:
                return GateDecision(False, REASON_NO_HEARTBEAT)
        return GateDecision(True, REASON_OK)

    def gate_for_commentary(self) -> GateDecision:
        base = self.gate()
        if not base.allowed:
            return base
        cfg = self.settings()
        if not cfg["commentary_enabled"]:
            return GateDecision(False, REASON_DISABLED)
        return base

    def event_trigger_enabled(self, kind: str) -> bool:
        triggers = self.settings().get("event_triggers") or {}
        return bool(triggers.get(kind, False))

    # ---- Writes ----
    def update(self, **fields: Any) -> dict[str, Any]:
        if "commentary_cadence_seconds" in fields:
            fields["commentary_cadence_seconds"] = max(60, int(fields["commentary_cadence_seconds"]))
        if "heartbeat_grace_seconds" in fields:
            fields["heartbeat_grace_seconds"] = max(60, int(fields["heartbeat_grace_seconds"]))
        return self.storage.update_ai_settings(**fields)

    def heartbeat(self) -> dict[str, Any]:
        return self.storage.update_ai_settings(last_heartbeat_at=time.time())

    def disable_now(self) -> dict[str, Any]:
        return self.storage.update_ai_settings(ai_enabled=False)

    def enable_now(self) -> dict[str, Any]:
        # Re-enabling clears the circuit breaker and seeds the heartbeat so the
        # next call doesn't immediately re-mute.
        return self.storage.update_ai_settings(
            ai_enabled=True,
            consecutive_failures=0,
            circuit_open_until=0,
            last_heartbeat_at=time.time(),
        )

    # ---- Circuit breaker ----
    def record_success(self) -> None:
        cfg = self.settings()
        if cfg["consecutive_failures"] != 0 or cfg["circuit_open_until"]:
            self.storage.update_ai_settings(consecutive_failures=0, circuit_open_until=0)

    def record_failure(self) -> None:
        cfg = self.settings()
        count = cfg["consecutive_failures"] + 1
        if count >= self.CIRCUIT_FAILURE_THRESHOLD:
            self.storage.update_ai_settings(
                consecutive_failures=count,
                circuit_open_until=time.time() + self.CIRCUIT_COOLDOWN_SECONDS,
            )
        else:
            self.storage.update_ai_settings(consecutive_failures=count)
