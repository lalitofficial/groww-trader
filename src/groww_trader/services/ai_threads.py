from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from .storage import Storage


class AiThreadService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def list_threads(self, symbol: str, task_type: str) -> list[dict[str, Any]]:
        with self.storage.connect() as conn:
            rows = conn.execute(
                """
                select id, symbol, task_type, title, active, created_at, updated_at
                from ai_threads
                where symbol = ? and task_type = ?
                order by active desc, updated_at desc, id desc
                """,
                (symbol.upper(), task_type),
            ).fetchall()
            return [dict(row) for row in rows]

    def ensure_thread(self, symbol: str, task_type: str, title: str | None = None) -> dict[str, Any]:
        existing = self.list_threads(symbol, task_type)
        active = next((thread for thread in existing if thread["active"]), None)
        return active or self.create_thread(symbol, task_type, title=title)

    def create_thread(self, symbol: str, task_type: str, title: str | None = None, archive_existing: bool = True) -> dict[str, Any]:
        with self.storage.connect() as conn:
            if archive_existing:
                conn.execute(
                    "update ai_threads set active = 0, updated_at = current_timestamp where symbol = ? and task_type = ? and active = 1",
                    (symbol.upper(), task_type),
                )
            cursor = conn.execute(
                """
                insert into ai_threads(symbol, task_type, title, active, updated_at)
                values(?, ?, ?, 1, current_timestamp)
                """,
                (symbol.upper(), task_type, title or f"{symbol.upper()} {task_type}"),
            )
            row = conn.execute(
                "select id, symbol, task_type, title, active, created_at, updated_at from ai_threads where id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)

    def clear_thread(self, thread_id: int) -> dict[str, Any] | None:
        with self.storage.connect() as conn:
            thread = conn.execute(
                "select id, symbol, task_type, title, active, created_at, updated_at from ai_threads where id = ?",
                (thread_id,),
            ).fetchone()
            if not thread:
                return None
            conn.execute("delete from ai_messages where thread_id = ?", (thread_id,))
            conn.execute("update ai_threads set updated_at = current_timestamp where id = ?", (thread_id,))
            return dict(thread)

    def messages(self, thread_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.storage.connect() as conn:
            rows = conn.execute(
                """
                select id, thread_id, role, content, tool_name, payload, prompt_version, created_at
                from ai_messages
                where thread_id = ?
                order by id desc
                limit ?
                """,
                (thread_id, limit),
            ).fetchall()
            return [self._decode_message(row) for row in reversed(rows)]

    def add_message(
        self,
        thread_id: int,
        role: str,
        content: str,
        tool_name: str | None = None,
        payload: dict[str, Any] | None = None,
        prompt_version: str | None = None,
    ) -> dict[str, Any]:
        with self.storage.connect() as conn:
            cursor = conn.execute(
                """
                insert into ai_messages(thread_id, role, content, tool_name, payload, prompt_version)
                values(?, ?, ?, ?, ?, ?)
                """,
                (thread_id, role, content, tool_name, json.dumps(payload or {}, default=str), prompt_version),
            )
            conn.execute("update ai_threads set updated_at = current_timestamp where id = ?", (thread_id,))
            row = conn.execute(
                """
                select id, thread_id, role, content, tool_name, payload, prompt_version, created_at
                from ai_messages
                where id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            return self._decode_message(row)

    def record_feedback(self, message_id: int | None, symbol: str, task_type: str, rating: int, prompt_version: str | None = None) -> dict[str, Any]:
        with self.storage.connect() as conn:
            cursor = conn.execute(
                """
                insert into ai_feedback(message_id, symbol, task_type, rating, prompt_version)
                values(?, ?, ?, ?, ?)
                """,
                (message_id, symbol.upper(), task_type, 1 if rating > 0 else -1, prompt_version),
            )
            return {"id": cursor.lastrowid, "rating": 1 if rating > 0 else -1}

    def feedback_summary(self, task_type: str, prompt_version: str | None = None) -> dict[str, Any]:
        query = "select rating from ai_feedback where task_type = ?"
        params: list[Any] = [task_type]
        if prompt_version:
            query += " and prompt_version = ?"
            params.append(prompt_version)
        with self.storage.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        total = len(rows)
        positive = sum(1 for row in rows if row["rating"] > 0)
        return {"positive_pct": round((positive / total) * 100, 1) if total else None, "count": total}

    def get_cache(self, kind: str, cache_key: str) -> dict[str, Any] | None:
        now = _utcnow()
        with self.storage.connect() as conn:
            row = conn.execute(
                """
                select cache_key, kind, symbol, task_type, payload, expires_at, updated_at
                from ai_cache
                where kind = ? and cache_key = ? and (expires_at is null or expires_at > ?)
                """,
                (kind, cache_key, now),
            ).fetchone()
            if not row:
                return None
            return {**dict(row), "payload": json.loads(row["payload"])}

    def set_cache(
        self,
        kind: str,
        cache_key: str,
        payload: dict[str, Any],
        symbol: str | None = None,
        task_type: str | None = None,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        expires_at = _utcnow(ttl_seconds) if ttl_seconds else None
        with self.storage.connect() as conn:
            conn.execute(
                """
                insert into ai_cache(cache_key, kind, symbol, task_type, payload, expires_at, updated_at)
                values(?, ?, ?, ?, ?, ?, current_timestamp)
                on conflict(cache_key) do update set
                    kind=excluded.kind,
                    symbol=excluded.symbol,
                    task_type=excluded.task_type,
                    payload=excluded.payload,
                    expires_at=excluded.expires_at,
                    updated_at=current_timestamp
                """,
                (cache_key, kind, symbol.upper() if symbol else None, task_type, json.dumps(payload, default=str), expires_at),
            )
        return {"cache_key": cache_key, "kind": kind, "cached": True}

    def get_tool_cache(self, cache_key: str) -> dict[str, Any] | None:
        now = _utcnow()
        with self.storage.connect() as conn:
            row = conn.execute(
                """
                select cache_key, tool_name, args, payload, expires_at, updated_at
                from ai_tool_cache
                where cache_key = ? and expires_at > ?
                """,
                (cache_key, now),
            ).fetchone()
            if not row:
                return None
            return {**dict(row), "args": json.loads(row["args"]), "payload": json.loads(row["payload"])}

    def set_tool_cache(self, cache_key: str, tool_name: str, args: dict[str, Any], payload: dict[str, Any], ttl_seconds: int = 900) -> dict[str, Any]:
        with self.storage.connect() as conn:
            conn.execute(
                """
                insert into ai_tool_cache(cache_key, tool_name, args, payload, expires_at, updated_at)
                values(?, ?, ?, ?, ?, current_timestamp)
                on conflict(cache_key) do update set
                    tool_name=excluded.tool_name,
                    args=excluded.args,
                    payload=excluded.payload,
                    expires_at=excluded.expires_at,
                    updated_at=current_timestamp
                """,
                (cache_key, tool_name, json.dumps(args, default=str), json.dumps(payload, default=str), _utcnow(ttl_seconds)),
            )
        return {"cache_key": cache_key, "tool_name": tool_name, "cached": True}

    def _decode_message(self, row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "role": row["role"],
            "content": row["content"],
            "tool_name": row["tool_name"],
            "payload": json.loads(row["payload"] or "{}"),
            "prompt_version": row["prompt_version"],
            "created_at": row["created_at"],
        }


def _utcnow(add_seconds: int | None = None) -> str:
    value = datetime.now(timezone.utc)
    if add_seconds:
        value += timedelta(seconds=add_seconds)
    return value.strftime("%Y-%m-%d %H:%M:%S")
