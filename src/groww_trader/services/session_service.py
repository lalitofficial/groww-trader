from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .storage import Storage


IST = timezone(timedelta(hours=5, minutes=30))


def current_session_date(now: datetime | None = None) -> str:
    """Return the active session date in IST.

    A trading session rolls over at 06:00 IST. So calling this at 04:30 IST
    still resolves to the *previous* calendar day, while 06:01 IST belongs to
    the new day. This matches our "AI Open Desk goes live at 08:00" workflow.
    """
    moment = (now or datetime.now(timezone.utc)).astimezone(IST)
    if moment.hour < 6:
        moment = moment - timedelta(days=1)
    return moment.strftime("%Y-%m-%d")


class SessionService:
    """Owns the day's trading session: shortlist, picks, macro context, events."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def current(self) -> dict[str, Any]:
        return self.storage.get_or_create_session(current_session_date())

    def update_notes(self, notes: str) -> dict[str, Any]:
        return self.storage.update_session(current_session_date(), notes=notes)

    def set_macro(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self.storage.update_session(current_session_date(), macro_snapshot=snapshot)

    # -------- Shortlist --------
    def add_to_shortlist(self, symbol: str, reason: str | None = None, factors: dict[str, Any] | None = None) -> dict[str, Any]:
        symbol = symbol.upper()
        session = self.current()
        items = session["shortlist"]
        if any(item.get("symbol") == symbol for item in items):
            return session
        items.append(
            {
                "symbol": symbol,
                "reason": reason or "",
                "factors": factors or {},
                "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        updated = self.storage.update_session(session["session_date"], shortlist=items)
        self.storage.record_session_event(session["session_date"], "shortlist_added", symbol, {"reason": reason})
        return updated

    def remove_from_shortlist(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        session = self.current()
        items = [item for item in session["shortlist"] if item.get("symbol") != symbol]
        if len(items) == len(session["shortlist"]):
            return session
        updated = self.storage.update_session(session["session_date"], shortlist=items)
        self.storage.record_session_event(session["session_date"], "shortlist_removed", symbol)
        return updated

    def clear_shortlist(self) -> dict[str, Any]:
        session = self.current()
        if not session["shortlist"]:
            return session
        updated = self.storage.update_session(session["session_date"], shortlist=[])
        self.storage.record_session_event(session["session_date"], "shortlist_cleared")
        return updated

    # -------- Picks --------
    def set_picks(self, picks: list[dict[str, Any]]) -> dict[str, Any]:
        clean: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pick in picks:
            symbol = str(pick.get("symbol") or "").upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            clean.append(
                {
                    "symbol": symbol,
                    "direction": pick.get("direction") or "long",
                    "plan": pick.get("plan") or {},
                    "sized_qty": pick.get("sized_qty"),
                    "notes": pick.get("notes") or "",
                    "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
        session = self.current()
        updated = self.storage.update_session(session["session_date"], picks=clean)
        self.storage.record_session_event(session["session_date"], "picks_set", payload={"count": len(clean), "symbols": [item["symbol"] for item in clean]})
        return updated

    def remove_pick(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        session = self.current()
        picks = [item for item in session["picks"] if item.get("symbol") != symbol]
        if len(picks) == len(session["picks"]):
            return session
        updated = self.storage.update_session(session["session_date"], picks=picks)
        self.storage.record_session_event(session["session_date"], "pick_removed", symbol)
        return updated

    # -------- Events --------
    def record_event(self, kind: str, symbol: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.storage.record_session_event(current_session_date(), kind, symbol, payload)

    def events_since(self, since_id: int = 0, limit: int = 200, kinds: list[str] | None = None) -> list[dict[str, Any]]:
        return self.storage.list_session_events(current_session_date(), since_id=since_id, limit=limit, kinds=kinds)

    # -------- Close / list --------
    def close(self) -> dict[str, Any]:
        session = self.current()
        if session["status"] == "closed":
            return session
        updated = self.storage.update_session(session["session_date"], status="closed")
        self.storage.record_session_event(session["session_date"], "session_closed")
        return updated

    def history(self, limit: int = 30) -> list[dict[str, Any]]:
        return self.storage.list_sessions(limit=limit)
