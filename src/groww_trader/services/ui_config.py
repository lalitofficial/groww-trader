from __future__ import annotations

import json
from typing import Any

from .storage import Storage


TOKEN_KEYS = {
    "--bg", "--panel", "--ink", "--muted", "--accent", "--accent-2", "--warn", "--bad",
    "--fs-12", "--fs-14", "--row-h", "--btn-h", "--radius-md", "--line",
}

DENSITY = {
    "compact": {"--row-h": "24px", "--btn-h": "24px", "--sp-3": "5px", "--sp-4": "7px"},
    "cozy": {"--row-h": "28px", "--btn-h": "28px", "--sp-3": "7px", "--sp-4": "9px"},
    "comfortable": {"--row-h": "32px", "--btn-h": "32px", "--sp-3": "9px", "--sp-4": "12px"},
}


class UiConfigStore:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def get(self) -> dict[str, Any]:
        with self.storage.connect() as conn:
            conn.execute("insert or ignore into ui_config(id, tokens, layout) values (1, '{}', '{}')")
            row = conn.execute("select tokens, layout, updated_at from ui_config where id = 1").fetchone()
        tokens = json.loads(row["tokens"] or "{}")
        layout = json.loads(row["layout"] or "{}")
        return {"tokens": tokens, "layout": layout, "cssText": css_text(tokens, layout), "updated_at": row["updated_at"]}

    def update(self, tokens: dict[str, Any] | None = None, layout: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self.get()
        merged_tokens = {**current["tokens"], **validate_tokens(tokens or {})}
        merged_layout = {**current["layout"], **validate_layout(layout or {})}
        with self.storage.connect() as conn:
            conn.execute(
                "update ui_config set tokens = ?, layout = ?, updated_at = current_timestamp where id = 1",
                (json.dumps(merged_tokens), json.dumps(merged_layout)),
            )
        return self.get()

    def reset(self) -> dict[str, Any]:
        with self.storage.connect() as conn:
            conn.execute("update ui_config set tokens = '{}', layout = '{}', updated_at = current_timestamp where id = 1")
        return self.get()


def validate_tokens(tokens: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in tokens.items():
        if key not in TOKEN_KEYS:
            raise ValueError(f"Unsupported UI token: {key}")
        text = str(value).strip()
        if len(text) > 64 or any(char in text for char in "{};"):
            raise ValueError(f"Unsafe UI token value for {key}")
        clean[key] = text
    return clean


def validate_layout(layout: dict[str, Any]) -> dict[str, Any]:
    clean = dict(layout)
    if "density" in clean and clean["density"] not in DENSITY:
        raise ValueError("density must be compact, cozy, or comfortable")
    return clean


def css_text(tokens: dict[str, Any], layout: dict[str, Any]) -> str:
    values = {**DENSITY.get(str(layout.get("density", "")), {}), **tokens}
    if not values:
        return ""
    body = "\n".join(f"  {key}: {value};" for key, value in sorted(values.items()))
    return f":root {{\n{body}\n}}"
