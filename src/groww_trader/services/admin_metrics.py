from __future__ import annotations

import os
import time
from collections import deque
from pathlib import Path
from typing import Any

from .request_budget import RequestBudget
from .storage import Storage


class AdminMetrics:
    def __init__(self, storage: Storage, request_budget: RequestBudget, api_usage: dict[str, Any], database_path: Path) -> None:
        self.storage = storage
        self.request_budget = request_budget
        self.api_usage = api_usage
        self.database_path = database_path

    def overview(self) -> dict[str, Any]:
        budget = self.request_budget.snapshot(_float_env("AZURE_PROMPT_USD_PER_MTOK"), _float_env("AZURE_COMPLETION_USD_PER_MTOK"))
        with self.storage.connect() as conn:
            paper = conn.execute("select status, count(*) count from paper_trades group by status").fetchall()
            events = conn.execute("select id, session_date, symbol, kind, payload, at from session_events order by id desc limit 100").fetchall()
            ai_threads = conn.execute("select count(*) count from ai_threads").fetchone()["count"]
            ai_messages = conn.execute("select count(*) count from ai_messages").fetchone()["count"]
            audit = conn.execute("select id, action, details, at from admin_audit_log order by id desc limit 20").fetchall()
        return {
            "budget": budget,
            "api_usage": self._api_usage(),
            "paper": {row["status"]: row["count"] for row in paper},
            "ai": {"threads": ai_threads, "messages": ai_messages},
            "events": [_json_row(row) for row in events],
            "audit": [_json_row(row) for row in audit],
            "db": self.schema_summary(),
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "budget": self.request_budget.snapshot(_float_env("AZURE_PROMPT_USD_PER_MTOK"), _float_env("AZURE_COMPLETION_USD_PER_MTOK")),
            "api_usage": self._api_usage(),
            "top_endpoints": self.top_endpoints(),
        }

    def series(self, window_seconds: int = 3600, bucket_seconds: int = 300) -> dict[str, Any]:
        return {"items": self.request_budget.endpoint_series(bucket_seconds=bucket_seconds, window_seconds=window_seconds)}

    def top_endpoints(self) -> list[dict[str, Any]]:
        endpoints = self.request_budget.snapshot().get("endpoints", {})
        return sorted(
            [{"endpoint": key, **value} for key, value in endpoints.items()],
            key=lambda row: (row["count"], row["p95_ms"]),
            reverse=True,
        )

    def schema_summary(self) -> dict[str, Any]:
        with self.storage.connect() as conn:
            tables = conn.execute("select name from sqlite_master where type='table' order by name").fetchall()
            rows = []
            for table in tables:
                name = table["name"]
                if name.startswith("sqlite_"):
                    continue
                count = conn.execute(f"select count(*) count from {name}").fetchone()["count"]
                rows.append({"table": name, "rows": count})
        return {"path": str(self.database_path), "size_bytes": os.path.getsize(self.database_path) if self.database_path.exists() else 0, "tables": rows}

    def _api_usage(self) -> dict[str, Any]:
        now = time.time()
        recent = [item for item in list(self.api_usage.get("recent", deque())) if now - item["timestamp"] <= 3600]
        return {
            "total_requests": self.api_usage.get("total_requests", 0),
            "error_requests": self.api_usage.get("error_requests", 0),
            "recent_1h": len(recent),
            "errors_1h": sum(1 for item in recent if item.get("status", 200) >= 400),
            "avg_duration_ms_1h": round(sum(item.get("duration_ms", 0) for item in recent) / len(recent), 1) if recent else 0,
            "recent": recent[-100:],
        }


def _json_row(row) -> dict[str, Any]:
    import json

    result = dict(row)
    for key in ("payload", "details"):
        if key in result:
            try:
                result[key] = json.loads(result[key] or "{}")
            except Exception:
                pass
    return result


def _float_env(name: str) -> float:
    try:
        return float(os.getenv(name, "0") or 0)
    except ValueError:
        return 0.0
