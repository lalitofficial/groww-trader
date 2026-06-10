from __future__ import annotations

import math
import re
import time
from typing import Any

from .storage import Storage


# Cheap keyword-based fallback used when we don't have AI quota or as a first pass.
# Each tuple is (word, weight). Negative weight = bearish.
_LEXICON: list[tuple[str, int]] = [
    ("profit", 4), ("revenue", 3), ("growth", 3), ("expansion", 3),
    ("acquisition", 4), ("merger", 3), ("buyback", 6), ("dividend", 4),
    ("order", 4), ("win", 4), ("contract", 4), ("upgrade", 5), ("rating", 2),
    ("outperform", 5), ("beat", 4), ("guidance", 2), ("record", 3),
    ("stake", 3), ("invests", 3), ("launch", 2), ("approval", 5),
    ("decline", -4), ("drop", -3), ("loss", -5), ("weak", -3),
    ("probe", -6), ("fraud", -8), ("scam", -8), ("downgrade", -6),
    ("cuts", -3), ("warning", -4), ("miss", -4), ("delay", -3),
    ("fall", -3), ("falls", -3), ("slump", -5), ("crash", -7),
    ("halt", -4), ("suspend", -5), ("recall", -5), ("layoff", -4),
    ("ban", -5), ("restructure", -3), ("downgraded", -6),
]


class SentimentService:
    """Computes a recency-weighted sentiment score for a symbol from catalysts.

    Uses a lightweight lexicon as the deterministic baseline. The optional AI
    rescore path (when AI gate is open) batch-calls Azure for the same catalyst
    titles to refine labels. Results are cached in `ai_cache` for ~30 minutes
    so we don't burn calls re-rating the same headlines.
    """

    HALF_LIFE_HOURS = 24
    CACHE_TTL_SECONDS = 30 * 60

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def score_for(self, symbol: str, catalysts: list[dict[str, Any]]) -> dict[str, Any]:
        if not catalysts:
            return {"symbol": symbol.upper(), "score": 0, "label": "neutral", "items": []}
        scored: list[dict[str, Any]] = []
        total = 0.0
        weight_sum = 0.0
        for item in catalysts[:25]:
            label, raw = _classify(item.get("title") or "", item.get("summary") or "")
            age_hours = _age_hours(item.get("published_at"))
            decay = 0.5 ** (age_hours / self.HALF_LIFE_HOURS)
            relevance = float(item.get("relevance_score") or 0.5)
            weight = decay * relevance
            score = raw * weight
            total += score
            weight_sum += weight
            scored.append({
                "title": item.get("title"),
                "label": label,
                "score": round(raw, 1),
                "weight": round(weight, 3),
                "age_hours": round(age_hours, 1),
                "url": item.get("url"),
            })
        normalized = max(-100, min(100, int(total / max(weight_sum, 0.001))))
        label = "positive" if normalized > 8 else "negative" if normalized < -8 else "neutral"
        return {
            "symbol": symbol.upper(),
            "score": normalized,
            "label": label,
            "items": scored[:10],
            "method": "lexicon",
        }


def _classify(title: str, summary: str) -> tuple[str, float]:
    text = f"{title} {summary}".lower()
    if not text.strip():
        return "neutral", 0.0
    score = 0
    for word, weight in _LEXICON:
        if re.search(rf"\b{re.escape(word)}\b", text):
            score += weight
    if score > 4:
        return "positive", float(min(100, score * 6))
    if score < -4:
        return "negative", float(max(-100, score * 6))
    return "neutral", float(score * 4)


def _age_hours(published_at: Any) -> float:
    if not published_at:
        return 12.0
    text = str(published_at)
    formats = (
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    import datetime as _dt
    for fmt in formats:
        try:
            value = _dt.datetime.strptime(text, fmt)
            if value.tzinfo is None:
                value = value.replace(tzinfo=_dt.timezone.utc)
            delta = _dt.datetime.now(_dt.timezone.utc) - value
            return max(0.0, delta.total_seconds() / 3600)
        except ValueError:
            continue
    return 24.0
