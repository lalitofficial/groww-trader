from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_DIRECTIONS = {"long_only", "short_only", "both"}
VALID_INDICATORS = {"sma", "ema", "rsi", "atr", "macd_histogram", "bollinger", "vwap", "stoch_rsi", "donchian", "supertrend"}
VALID_OPS = {
    "gt", "lt", "gte", "lte", "between", "eq",
    "crosses_above", "crosses_below",
    "above", "below",
    "consec_bars_above", "consec_bars_below",
}
VALID_EXIT_TYPES = {"opposite_signal", "atr_trail", "r_multiple", "fixed_pct", "time_bars"}


@dataclass
class StrategySpec:
    id: str
    name: str
    author: str = "community"
    source_url: str | None = None
    description: str | None = None
    timeframes: tuple[str, ...] = ("daily",)
    direction: str = "long_only"
    indicators: dict[str, list[Any]] = field(default_factory=dict)
    entry_long: list[dict[str, Any]] = field(default_factory=list)
    exit_long: list[dict[str, Any]] = field(default_factory=list)
    entry_short: list[dict[str, Any]] = field(default_factory=list)
    exit_short: list[dict[str, Any]] = field(default_factory=list)
    risk: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategySpec":
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name") or payload["id"]),
            author=str(payload.get("author") or "community"),
            source_url=payload.get("source_url"),
            description=payload.get("description"),
            timeframes=tuple(payload.get("timeframes") or ["daily"]),
            direction=str(payload.get("direction") or "long_only"),
            indicators={key: list(value) for key, value in (payload.get("indicators") or {}).items()},
            entry_long=list(payload.get("entry_long") or []),
            exit_long=list(payload.get("exit_long") or []),
            entry_short=list(payload.get("entry_short") or []),
            exit_short=list(payload.get("exit_short") or []),
            risk=dict(payload.get("risk") or {}),
            tags=list(payload.get("tags") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "author": self.author,
            "source_url": self.source_url,
            "description": self.description,
            "timeframes": list(self.timeframes),
            "direction": self.direction,
            "indicators": self.indicators,
            "entry_long": self.entry_long,
            "exit_long": self.exit_long,
            "entry_short": self.entry_short,
            "exit_short": self.exit_short,
            "risk": self.risk,
            "tags": self.tags,
        }


def validate_spec(payload: dict[str, Any]) -> StrategySpec:
    if not isinstance(payload, dict):
        raise ValueError("Strategy spec must be a JSON object.")
    if not payload.get("id"):
        raise ValueError("Strategy spec missing required field 'id'.")
    spec = StrategySpec.from_dict(payload)
    if spec.direction not in VALID_DIRECTIONS:
        raise ValueError(f"Invalid direction '{spec.direction}'. Must be one of {sorted(VALID_DIRECTIONS)}.")
    for indicator_key, definition in spec.indicators.items():
        if not definition:
            raise ValueError(f"Indicator '{indicator_key}' has empty definition.")
        kind = str(definition[0])
        if kind not in VALID_INDICATORS:
            raise ValueError(f"Indicator '{indicator_key}' uses unknown kind '{kind}'. Allowed: {sorted(VALID_INDICATORS)}.")
    for label, rules in (("entry_long", spec.entry_long), ("exit_long", spec.exit_long), ("entry_short", spec.entry_short), ("exit_short", spec.exit_short)):
        for rule in rules:
            op = rule.get("op")
            if op not in VALID_OPS:
                raise ValueError(f"Rule in '{label}' uses unknown op '{op}'. Allowed: {sorted(VALID_OPS)}.")
    risk = spec.risk
    for key in risk:
        if key not in {"stop", "target", "max_bars", "size_atr_mult"}:
            raise ValueError(f"Unknown risk key '{key}'.")
    if "stop" in risk and risk["stop"].get("type") not in {None, "atr_trail", "fixed_pct"} | VALID_EXIT_TYPES:
        raise ValueError(f"Unknown stop type '{risk['stop'].get('type')}'.")
    return spec
