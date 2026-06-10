from __future__ import annotations

import secrets
import time
from typing import Any


class ConfirmTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, tuple[str, float, dict[str, Any]]] = {}

    def issue(self, action: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        token = secrets.token_urlsafe(18)
        expires_at = time.time() + 60
        self._tokens[token] = (action, expires_at, details or {})
        return {"confirm_token": token, "action": action, "expires_at": expires_at}

    def consume(self, token: str, action: str) -> dict[str, Any]:
        record = self._tokens.pop(token, None)
        if not record:
            raise ValueError("Invalid or already used confirm token.")
        stored_action, expires_at, details = record
        if stored_action != action:
            raise ValueError("Confirm token action mismatch.")
        if time.time() > expires_at:
            raise ValueError("Confirm token expired.")
        return details
