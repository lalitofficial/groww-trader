from __future__ import annotations

import json
from typing import Any

from .storage import Storage


DEFAULT_FLAGS: dict[str, bool] = {
    "open_desk": True,
    "live_desk": True,
    "research_workstation": True,
    "strategy_lab": True,
    "paper_ledger": True,
    "fundamentals_panel": True,
    "option_chain_panel": True,
    "breadth_panel": True,
    "ai_commentary_default_on": True,
    "intraday_workspace_default": True,
    "mode_pills_in_header": True,
}


class FeatureFlagStore:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def all(self) -> dict[str, bool]:
        with self.storage.connect() as conn:
            rows = conn.execute("select key, value from feature_flags").fetchall()
        values = DEFAULT_FLAGS.copy()
        for row in rows:
            try:
                values[row["key"]] = bool(json.loads(row["value"]))
            except json.JSONDecodeError:
                values[row["key"]] = row["value"].lower() in {"1", "true", "yes", "on"}
        return values

    def set(self, key: str, value: Any) -> dict[str, bool]:
        if key not in DEFAULT_FLAGS:
            raise ValueError(f"Unknown feature flag: {key}")
        parsed = bool(value)
        with self.storage.connect() as conn:
            conn.execute(
                """
                insert into feature_flags(key, value, updated_at)
                values(?, ?, current_timestamp)
                on conflict(key) do update set value=excluded.value, updated_at=current_timestamp
                """,
                (key, json.dumps(parsed)),
            )
        return self.all()
