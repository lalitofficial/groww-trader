from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from groww_trader.settings import AppSettings

from .indicators import normalize_candles
from .market_data import MarketDataRouter
from .scanner import resolve_timeframe
from .storage import Storage
from .strategies import BUILTIN_STRATEGIES, StrategySpec, get_builtin_strategy, run_strategy
from .strategies.github_import import GitHubImportError, import_spec_from_url
from .strategies.spec import validate_spec


class StrategyService:
    def __init__(self, storage: Storage, market_data: MarketDataRouter, settings: AppSettings) -> None:
        self.storage = storage
        self.market_data = market_data
        self.settings = settings

    # -------- Catalog --------
    def list(self) -> list[dict[str, Any]]:
        builtin = [
            {**spec.to_dict(), "id": spec.id, "kind": "builtin"}
            for spec in BUILTIN_STRATEGIES.values()
        ]
        user_imported = self.storage.list_user_strategies()
        return builtin + user_imported

    def get(self, strategy_id: str) -> StrategySpec | None:
        spec = get_builtin_strategy(strategy_id)
        if spec is not None:
            return spec
        record = self.storage.user_strategy(strategy_id)
        if record is None:
            return None
        return validate_spec(record["spec"])

    # -------- Imports --------
    def import_from_url(self, url: str) -> dict[str, Any]:
        spec = import_spec_from_url(url)
        record = self.storage.upsert_user_strategy(
            spec_id=spec.id,
            name=spec.name,
            spec=spec.to_dict(),
            source_url=spec.source_url,
            author=spec.author,
        )
        return record

    def import_inline(self, payload: dict[str, Any]) -> dict[str, Any]:
        spec = validate_spec(payload)
        record = self.storage.upsert_user_strategy(
            spec_id=spec.id,
            name=spec.name,
            spec=spec.to_dict(),
            source_url=spec.source_url,
            author=spec.author,
        )
        return record

    def delete(self, strategy_id: str) -> bool:
        return self.storage.delete_user_strategy(strategy_id)

    # -------- Execution --------
    def run(self, strategy_id: str, symbol: str, timeframe: str = "daily", refresh: bool = False) -> dict[str, Any]:
        spec = self.get(strategy_id)
        if spec is None:
            raise KeyError(f"Strategy '{strategy_id}' not found.")
        tf = resolve_timeframe(timeframe)
        payload = self.market_data.safe_historical_candles(symbol.upper(), interval_minutes=tf["interval"], lookback_days=tf["lookback"], refresh=refresh)
        candles = normalize_candles(payload)
        result = run_strategy(spec, candles, timeframe=tf["label"], settings=self.settings)
        result["symbol"] = symbol.upper()
        result["data_source"] = payload.get("data_source")
        result["data_freshness"] = payload.get("data_freshness")
        return result

    def bench(self, symbol: str, timeframe: str = "daily", strategy_ids: list[str] | None = None, refresh: bool = False) -> dict[str, Any]:
        tf = resolve_timeframe(timeframe)
        payload = self.market_data.safe_historical_candles(symbol.upper(), interval_minutes=tf["interval"], lookback_days=tf["lookback"], refresh=refresh)
        candles = normalize_candles(payload)
        if strategy_ids:
            specs = [self.get(strategy_id) for strategy_id in strategy_ids]
            specs = [spec for spec in specs if spec is not None]
        else:
            user_specs = [validate_spec(record["spec"]) for record in self.storage.list_user_strategies()]
            specs = list(BUILTIN_STRATEGIES.values()) + user_specs
            specs = [spec for spec in specs if tf["label"] in spec.timeframes or "daily" in spec.timeframes and tf["label"] == "daily"]
        if not specs:
            return {"symbol": symbol.upper(), "timeframe": tf["label"], "results": []}

        def run_one(spec: StrategySpec) -> dict[str, Any]:
            result = run_strategy(spec, candles, timeframe=tf["label"], settings=self.settings)
            metrics = result.get("metrics") or {}
            return {
                "strategy_id": spec.id,
                "name": spec.name,
                "author": spec.author,
                "source_url": spec.source_url,
                "tags": spec.tags,
                "sample_size": metrics.get("sample_size", 0),
                "win_rate": metrics.get("win_rate"),
                "total_return_pct": metrics.get("total_return_pct"),
                "profit_factor": metrics.get("profit_factor"),
                "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                "expectancy": metrics.get("expectancy"),
                "sharpe": metrics.get("sharpe"),
            }

        with ThreadPoolExecutor(max_workers=min(8, len(specs))) as pool:
            rows = list(pool.map(run_one, specs))
        rows.sort(key=lambda row: (
            -(row.get("sharpe") or 0),
            -(row.get("profit_factor") or 0),
            -(row.get("total_return_pct") or 0),
        ))
        return {"symbol": symbol.upper(), "timeframe": tf["label"], "results": rows, "data_source": payload.get("data_source")}


__all__ = ["StrategyService", "GitHubImportError"]
