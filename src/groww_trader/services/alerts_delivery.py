from __future__ import annotations

from typing import Any

import requests

from groww_trader.settings import AppSettings

from .storage import Storage


class AlertsDeliveryService:
    """Deliver alert events to external channels (Telegram, browser-push log)."""

    def __init__(self, storage: Storage, settings: AppSettings) -> None:
        self.storage = storage
        self.settings = settings

    def deliver(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {"channels": {}, "delivered": 0}
        summary: dict[str, Any] = {"channels": {}, "delivered": 0}
        for channel, handler in self._channels().items():
            already_sent = self.storage.delivered_alert_keys(channel)
            queued = [event for event in events if event["event_key"] not in already_sent]
            sent = 0
            errors: list[str] = []
            for event in queued:
                try:
                    handler(event)
                    self.storage.record_alert_delivery(event["event_key"], channel, "ok", _format_text(event))
                    sent += 1
                except Exception as exc:
                    self.storage.record_alert_delivery(event["event_key"], channel, "error", str(exc))
                    errors.append(str(exc))
            summary["channels"][channel] = {"sent": sent, "queued": len(queued), "errors": errors}
            summary["delivered"] += sent
        return summary

    def _channels(self) -> dict[str, Any]:
        channels: dict[str, Any] = {"browser": self._noop_handler}
        if self.settings.telegram_bot_token and self.settings.telegram_chat_id:
            channels["telegram"] = self._telegram_handler
        return channels

    def _noop_handler(self, event: dict[str, Any]) -> None:  # browser channel = just log to DB
        return None

    def _telegram_handler(self, event: dict[str, Any]) -> None:
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": _format_text(event, markdown=True),
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code >= 400:
            raise RuntimeError(response.text)


def _format_text(event: dict[str, Any], markdown: bool = False) -> str:
    icon = {"critical": "[ALERT]", "warning": "[WARN]", "info": "[INFO]"}.get(event.get("severity"), "[INFO]")
    symbol = event.get("symbol")
    title = event.get("title")
    body = event.get("message")
    if markdown:
        return f"{icon} *{symbol}* — _{title}_\n{body}"
    return f"{icon} {symbol} — {title}\n{body}"
