from __future__ import annotations

import json
from typing import Any

from .storage import Storage


class AdminAuditLog:
    def __init__(self, storage: Storage, cap: int = 10_000) -> None:
        self.storage = storage
        self.cap = cap

    def append(self, action: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.storage.connect() as conn:
            cursor = conn.execute(
                "insert into admin_audit_log(action, details) values(?, ?)",
                (action, json.dumps(details or {}, default=str)),
            )
            conn.execute(
                """
                delete from admin_audit_log
                where id not in (select id from admin_audit_log order by id desc limit ?)
                """,
                (self.cap,),
            )
            row = conn.execute("select id, action, details, at from admin_audit_log where id = ?", (cursor.lastrowid,)).fetchone()
        return decode(row)

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.storage.connect() as conn:
            rows = conn.execute(
                "select id, action, details, at from admin_audit_log order by id desc limit ?",
                (limit,),
            ).fetchall()
        return [decode(row) for row in rows]


def decode(row) -> dict[str, Any]:
    return {"id": row["id"], "action": row["action"], "details": json.loads(row["details"] or "{}"), "at": row["at"]}
