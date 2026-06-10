from __future__ import annotations

import os
import time
import urllib.request
from typing import Any, Callable

from .account import AccountService
from .public_data import PublicDataService
from .storage import Storage


class AdminHealth:
    def __init__(self, storage: Storage, public_data: PublicDataService, account: AccountService) -> None:
        self.storage = storage
        self.public_data = public_data
        self.account = account

    def probes(self) -> list[dict[str, Any]]:
        checks: list[tuple[str, Callable[[], Any]]] = [
            ("nse", lambda: self.public_data.quote("RELIANCE")),
            ("yahoo", lambda: _url("https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=1d&interval=1d")),
            ("google_finance", lambda: self.public_data.google.quote("RELIANCE")),
            ("screener", lambda: self.public_data.fundamentals("RELIANCE")),
            ("moneycontrol", lambda: _url("https://www.moneycontrol.com/rss/latestnews.xml")),
            ("azure_openai", _azure_probe),
            ("telegram", _telegram_probe),
            ("groww", lambda: self.account.summary()),
        ]
        return [self._run(provider, fn) for provider, fn in checks]

    def log(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.storage.connect() as conn:
            rows = conn.execute(
                """
                select id, provider, ok, status_code, latency_ms, error, at
                from provider_health_log
                order by id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _run(self, provider: str, fn: Callable[[], Any]) -> dict[str, Any]:
        started = time.perf_counter()
        ok = False
        status_code = None
        error = None
        payload = None
        try:
            payload = fn()
            ok = bool(payload)
            status_code = 200 if ok else 502
        except Exception as exc:
            error = str(exc)
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        with self.storage.connect() as conn:
            conn.execute(
                "insert into provider_health_log(provider, ok, status_code, latency_ms, error) values(?, ?, ?, ?, ?)",
                (provider, 1 if ok else 0, status_code, latency_ms, error),
            )
            row = conn.execute(
                """
                select provider, ok, status_code, latency_ms, error, at
                from provider_health_log
                where provider = ?
                order by id desc
                limit 1
                """,
                (provider,),
            ).fetchone()
        result = dict(row)
        result["ok"] = bool(result["ok"])
        if payload is not None:
            result["payload_preview"] = _preview(payload)
        return result


def _url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "groww-trader-admin"})
    with urllib.request.urlopen(request, timeout=6) as response:
        return {"status": response.status, "bytes": len(response.read(256))}


def _azure_probe() -> dict[str, Any]:
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    if not endpoint or not key:
        return {"configured": False}
    request = urllib.request.Request(f"{endpoint}/openai/deployments?api-version={api_version}", headers={"api-key": key})
    with urllib.request.urlopen(request, timeout=6) as response:
        return {"status": response.status}


def _telegram_probe() -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"configured": False}
    return _url(f"https://api.telegram.org/bot{token}/getMe")


def _preview(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: payload[key] for key in list(payload)[:8]}
    if isinstance(payload, list):
        return payload[:3]
    return str(payload)[:200]
