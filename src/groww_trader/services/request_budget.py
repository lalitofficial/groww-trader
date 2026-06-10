from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class RequestBudget:
    """Tracks API hits per provider so the user can see cost / rate-limit usage."""

    def __init__(self, window_seconds: int = 3600) -> None:
        self.window_seconds = window_seconds
        self._events: deque[tuple[float, str, str]] = deque(maxlen=5000)
        self._token_events: deque[tuple[float, str, int, int, int]] = deque(maxlen=5000)
        self._endpoint_events: deque[tuple[float, str, float, int]] = deque(maxlen=10000)
        self._lock = threading.Lock()

    def record(self, provider: str, label: str = "request") -> None:
        with self._lock:
            self._events.append((time.time(), provider, label))

    def record_tokens(self, provider: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        total_tokens = max(0, int(prompt_tokens or 0)) + max(0, int(completion_tokens or 0))
        with self._lock:
            self._events.append((time.time(), provider, "tokens"))
            self._token_events.append((time.time(), provider, int(prompt_tokens or 0), int(completion_tokens or 0), total_tokens))

    def record_endpoint(self, endpoint: str, duration_ms: float, status_code: int) -> None:
        with self._lock:
            self._endpoint_events.append((time.time(), endpoint, float(duration_ms), int(status_code)))

    def reset_provider(self, provider: str) -> None:
        with self._lock:
            self._events = deque((event for event in self._events if event[1] != provider), maxlen=5000)
            self._token_events = deque((event for event in self._token_events if event[1] != provider), maxlen=5000)

    def snapshot(self, prompt_usd_per_mtok: float = 0, completion_usd_per_mtok: float = 0) -> dict[str, Any]:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            recent = [event for event in self._events if event[0] >= cutoff]
            token_recent = [event for event in self._token_events if event[0] >= cutoff]
            endpoint_recent = [event for event in self._endpoint_events if event[0] >= cutoff]
        by_provider: dict[str, dict[str, int]] = {}
        for _, provider, label in recent:
            entry = by_provider.setdefault(provider, {"total": 0})
            entry["total"] += 1
            entry[label] = entry.get(label, 0) + 1
        token_usage: dict[str, dict[str, int]] = {}
        for _, provider, prompt, completion, total in token_recent:
            entry = token_usage.setdefault(provider, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            entry["prompt_tokens"] += prompt
            entry["completion_tokens"] += completion
            entry["total_tokens"] += total
            if provider == "azure_openai":
                entry["cost_usd_total"] = round(
                    (entry["prompt_tokens"] / 1_000_000) * prompt_usd_per_mtok
                    + (entry["completion_tokens"] / 1_000_000) * completion_usd_per_mtok,
                    6,
                )
        endpoints: dict[str, dict[str, Any]] = {}
        for _, endpoint, duration, status in endpoint_recent:
            entry = endpoints.setdefault(endpoint, {"count": 0, "errors": 0, "durations": []})
            entry["count"] += 1
            entry["errors"] += 1 if status >= 400 else 0
            entry["durations"].append(duration)
        endpoint_stats = {
            endpoint: {
                "count": value["count"],
                "errors": value["errors"],
                "error_rate": round(value["errors"] / value["count"], 4) if value["count"] else 0,
                "p50_ms": percentile(value["durations"], 50),
                "p95_ms": percentile(value["durations"], 95),
            }
            for endpoint, value in endpoints.items()
        }
        return {
            "window_seconds": self.window_seconds,
            "total": len(recent),
            "by_provider": by_provider,
            "token_usage": token_usage,
            "endpoints": endpoint_stats,
            "last_event_at": recent[-1][0] if recent else None,
        }

    def endpoint_series(self, bucket_seconds: int = 300, window_seconds: int | None = None) -> list[dict[str, Any]]:
        now = time.time()
        window = window_seconds or self.window_seconds
        cutoff = now - window
        with self._lock:
            events = [event for event in self._endpoint_events if event[0] >= cutoff]
        buckets: dict[int, dict[str, Any]] = {}
        for ts, endpoint, duration, status in events:
            bucket = int((ts - cutoff) // bucket_seconds)
            row = buckets.setdefault(bucket, {"bucket": bucket, "at": cutoff + bucket * bucket_seconds, "count": 0, "errors": 0, "duration_ms": 0.0})
            row["count"] += 1
            row["errors"] += 1 if status >= 400 else 0
            row["duration_ms"] += duration
            row.setdefault("endpoints", {}).setdefault(endpoint, 0)
            row["endpoints"][endpoint] += 1
        return [
            {
                **row,
                "avg_duration_ms": round(row["duration_ms"] / row["count"], 1) if row["count"] else 0,
            }
            for _, row in sorted(buckets.items())
        ]


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[index], 1)


_BUDGET = RequestBudget()


def budget() -> RequestBudget:
    return _BUDGET
