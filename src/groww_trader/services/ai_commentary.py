from __future__ import annotations

import time
from typing import Any

from .ai_settings import AiSettingsService
from .ai_threads import AiThreadService
from .public_data import PublicDataService
from .session_service import SessionService


# Verdict tags the commentary model must end on.
VERDICT_TAGS = ("HOLD", "TRAIL", "BOOK_PARTIAL", "EXIT_NOW", "WAIT")

DETERMINISTIC_TEMPLATES = {
    "near_stop": "Stop is within 0.4%. Re-check thesis; consider tightening or exiting at next confirmation. Verdict: WAIT.",
    "near_target": "Target within reach. Plan partial book at T1 to lock R. Verdict: BOOK_PARTIAL.",
    "level_break_up": "Level broken with momentum. Trail stop to the broken level. Verdict: TRAIL.",
    "level_break_down": "Support broken. Re-evaluate long thesis; consider exit or wait for retest. Verdict: WAIT.",
    "vol_spike": "Volume spike noted. Confirm direction on next bar before adding. Verdict: HOLD.",
    "vwap_cross_up": "VWAP reclaimed. Buyers in control intraday. Verdict: HOLD.",
    "vwap_cross_down": "Lost VWAP. Bias shifts bearish; tighten stop. Verdict: TRAIL.",
    "orb_break_up": "Opening range broken up. Continuation likely if VWAP confirms. Verdict: HOLD.",
    "orb_break_down": "Opening range breakdown. Short bias intraday. Verdict: WAIT.",
    "pnl_milestone": "Position moved one R. Mechanical: move stop to breakeven. Verdict: TRAIL.",
}


class AiCommentaryService:
    """Triggers AI commentary on cadence + chart events, gated by AiSettings.

    All Azure calls go through `ai_settings.gate_for_commentary()`. When the
    gate is closed, we fall back to a deterministic, rule-based comment so the
    UI is never empty (and we don't burn quota).
    """

    def __init__(
        self,
        ai_settings: AiSettingsService,
        ai_threads: AiThreadService,
        session_service: SessionService,
        public_data: PublicDataService,
    ) -> None:
        self.ai_settings = ai_settings
        self.ai_threads = ai_threads
        self.session_service = session_service
        self.public_data = public_data
        self._last_cadence_fire: dict[str, float] = {}

    def maybe_fire_cadence(self, symbol: str, paper_trade: dict[str, Any] | None) -> dict[str, Any] | None:
        if not paper_trade or paper_trade.get("status") != "open":
            return None
        cfg = self.ai_settings.settings()
        cadence = int(cfg.get("commentary_cadence_seconds") or 300)
        now = time.time()
        last = self._last_cadence_fire.get(symbol.upper(), 0)
        if now - last < cadence:
            return None
        self._last_cadence_fire[symbol.upper()] = now
        return self._comment(symbol, trigger_kind="cadence", paper_trade=paper_trade, event_payload=None)

    def fire_event(self, symbol: str, kind: str, payload: dict[str, Any], paper_trade: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.ai_settings.event_trigger_enabled(kind):
            return None
        return self._comment(symbol, trigger_kind=kind, paper_trade=paper_trade, event_payload=payload)

    def manual(self, symbol: str, paper_trade: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._comment(symbol, trigger_kind="manual", paper_trade=paper_trade, event_payload=None, force=True)

    # -------- Internals --------
    def _comment(self, symbol: str, trigger_kind: str, paper_trade: dict[str, Any] | None, event_payload: dict[str, Any] | None, force: bool = False) -> dict[str, Any]:
        symbol = symbol.upper()
        decision = self.ai_settings.gate_for_commentary()
        thread = self.ai_threads.ensure_thread(symbol=symbol, task_type="commentary", title=f"{symbol} commentary")

        if not decision.allowed and not force:
            content = self._deterministic(trigger_kind, paper_trade, event_payload)
            message = self.ai_threads.add_message(
                thread_id=thread["id"],
                role="assistant",
                content=content,
                tool_name=None,
                payload={"trigger": trigger_kind, "fallback": decision.reason},
                prompt_version="commentary_v1_fallback",
            )
            self.session_service.record_event("ai_comment", symbol=symbol, payload={"trigger": trigger_kind, "fallback": True, "verdict": _extract_verdict(content)})
            return {"message": message, "fallback": True, "reason": decision.reason}

        # Live path: persist trigger + lean payload. The actual model call happens
        # client-side via the existing /api/ai/chat endpoint, with the system prompt
        # forcing the verdict tag at the end. We expose this hook as the seed entry.
        content = self._deterministic(trigger_kind, paper_trade, event_payload)
        message = self.ai_threads.add_message(
            thread_id=thread["id"],
            role="assistant",
            content=content,
            tool_name=None,
            payload={"trigger": trigger_kind, "event": event_payload, "paper_trade": paper_trade, "deterministic_seed": True},
            prompt_version="commentary_v1",
        )
        self.session_service.record_event("ai_comment", symbol=symbol, payload={"trigger": trigger_kind, "verdict": _extract_verdict(content)})
        return {"message": message, "fallback": False, "reason": decision.reason}

    def _deterministic(self, trigger_kind: str, paper_trade: dict[str, Any] | None, event_payload: dict[str, Any] | None) -> str:
        template = DETERMINISTIC_TEMPLATES.get(trigger_kind)
        if template:
            return template
        if trigger_kind == "cadence":
            if paper_trade:
                qty = paper_trade.get("quantity")
                side = paper_trade.get("side") or "BUY"
                entry = paper_trade.get("entry_price")
                return f"Cadence check on {side} {qty} @ ₹{entry}. No event detected. Verdict: HOLD."
            return "Cadence ping. No open paper trade. Verdict: WAIT."
        if trigger_kind == "manual":
            return "Manual snapshot — no event. Verdict: HOLD."
        return f"Event {trigger_kind} fired. Verdict: HOLD."


def _extract_verdict(content: str) -> str | None:
    for tag in VERDICT_TAGS:
        if tag in content.upper():
            return tag
    return None
