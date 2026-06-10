from groww_trader.services.indicators import Candle
from groww_trader.services.strategies import BUILTIN_STRATEGIES, run_strategy
from groww_trader.services.strategies.spec import StrategySpec, validate_spec
from groww_trader.services.strategies.github_import import GitHubImportError, _normalize


def _candles(count: int = 260) -> list[Candle]:
    return [
        Candle(
            timestamp=1_700_000_000 + i * 86_400,
            open=100 + (i * 0.6),
            high=103 + (i * 0.6) + (i % 4),
            low=98 + (i * 0.58) - (i % 3),
            close=101 + (i * 0.62),
            volume=1000 + (i * 12),
        )
        for i in range(count)
    ]


def test_builtin_strategies_load_and_validate():
    assert len(BUILTIN_STRATEGIES) >= 10
    for spec in BUILTIN_STRATEGIES.values():
        validated = validate_spec(spec.to_dict())
        assert validated.id == spec.id
        assert validated.entry_long or validated.entry_short


def test_golden_cross_runs_on_uptrend():
    spec = BUILTIN_STRATEGIES["golden_cross_50_200"]
    result = run_strategy(spec, _candles(), timeframe="daily")
    assert result["strategy_id"] == "golden_cross_50_200"
    assert "metrics" in result
    assert isinstance(result["trades"], list)


def test_validate_spec_rejects_unknown_op():
    bad = {"id": "x", "name": "x", "indicators": {"sma_50": ["sma", 50]}, "entry_long": [{"op": "nope", "a": "close", "b": 0}]}
    try:
        validate_spec(bad)
    except ValueError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("validate_spec should have rejected the unknown op")


def test_github_url_normalization():
    raw = _normalize("https://github.com/foo/bar/blob/main/strategies/x.yaml")
    assert raw == "https://raw.githubusercontent.com/foo/bar/main/strategies/x.yaml"
    assert _normalize("not-a-url") is None
