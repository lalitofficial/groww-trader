from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import shutil
import sqlite3
from collections import deque
from pathlib import Path
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from groww_trader.settings import load_app_settings
from groww_trader.services.account import AccountService
from groww_trader.services.admin_audit import AdminAuditLog
from groww_trader.services.admin_dangerous import ConfirmTokenStore
from groww_trader.services.admin_health import AdminHealth
from groww_trader.services.admin_metrics import AdminMetrics
from groww_trader.services.ai_commentary import AiCommentaryService
from groww_trader.services.ai_settings import AiSettingsService
from groww_trader.services.ai_threads import AiThreadService
from groww_trader.services.alerts_delivery import AlertsDeliveryService
from groww_trader.services.calendar import CalendarService
from groww_trader.services.catalysts import CatalystService
from groww_trader.services.factors import FactorPipeline
from groww_trader.services.feature_flags import FeatureFlagStore
from groww_trader.services.global_cues import GlobalCuesService
from groww_trader.services.groww_data import GrowwDataService
from groww_trader.services.live_feed import LiveFeed
from groww_trader.services.market_data import MarketDataRouter
from groww_trader.services.paper_trades import PaperTradeService
from groww_trader.services.public_data import PublicDataService
from groww_trader.services.regime import RegimeService
from groww_trader.services.request_budget import budget
from groww_trader.services.scanner import ScannerService, TIMEFRAME_MAP
from groww_trader.services.sentiment import SentimentService
from groww_trader.services.session_service import SessionService
from groww_trader.services.storage import Storage
from groww_trader.services.strategies.github_import import GitHubImportError
from groww_trader.services.strategy_service import StrategyService
from groww_trader.services.ui_config import UiConfigStore
from groww_trader.services.watchlists import WatchlistService


settings = load_app_settings()
storage = Storage(settings.database_path)
data_service = GrowwDataService(storage, settings)
public_data_service = PublicDataService()
market_data_service = MarketDataRouter(storage, settings, data_service, public_data=public_data_service)
catalyst_service = CatalystService(storage, public_data=public_data_service)
scanner_service = ScannerService(market_data_service, catalyst_service, settings)
account_service = AccountService(storage, scanner_service)
regime_service = RegimeService(market_data_service, settings)
paper_service = PaperTradeService(storage, market_data_service, settings)
alerts_delivery = AlertsDeliveryService(storage, settings)
watchlists_service = WatchlistService(storage, settings)
watchlists_service.ensure_default()
strategy_service = StrategyService(storage, market_data_service, settings)
ai_thread_service = AiThreadService(storage)
ai_settings_service = AiSettingsService(storage)
session_service = SessionService(storage)
calendar_service = CalendarService()
global_cues_service = GlobalCuesService()
sentiment_service = SentimentService(storage)
factor_pipeline = FactorPipeline(
    market_data=market_data_service,
    public_data=public_data_service,
    catalysts=catalyst_service,
    regime=regime_service,
    sentiment=sentiment_service,
    calendar=calendar_service,
    settings=settings,
)
live_feed = LiveFeed(market_data=market_data_service, public_data=public_data_service, session_service=session_service)
ai_commentary_service = AiCommentaryService(
    ai_settings=ai_settings_service,
    ai_threads=ai_thread_service,
    session_service=session_service,
    public_data=public_data_service,
)

api_started_at = time.time()
api_usage: dict[str, object] = {
    "total_requests": 0,
    "error_requests": 0,
    "recent": deque(maxlen=250),
}

admin_audit = AdminAuditLog(storage)
feature_flags = FeatureFlagStore(storage)
ui_config_store = UiConfigStore(storage)
admin_metrics = AdminMetrics(storage, budget(), api_usage, settings.database_path)
admin_health = AdminHealth(storage, public_data_service, account_service)
confirm_tokens = ConfirmTokenStore()

TIMEFRAME_PATTERN = "^(5m|15m|30m|hourly|daily)$"


app = FastAPI(title="Groww AI Intraday Trading API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002", "http://127.0.0.1:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AiReportPayload(BaseModel):
    symbol: str
    task_type: str = "stock_report"
    company: str | None = None
    content: str
    model: str | None = None
    source: str = "azure-openai"
    prompt_version: str | None = None
    context_hash: str | None = None
    context_summary: dict[str, object] | None = None


class AiThreadPayload(BaseModel):
    symbol: str
    task_type: str = "stock_report"
    title: str | None = None
    archive_existing: bool = True


class AiMessagePayload(BaseModel):
    thread_id: int
    role: str
    content: str
    tool_name: str | None = None
    payload: dict[str, object] | None = None
    prompt_version: str | None = None


class AiFeedbackPayload(BaseModel):
    message_id: int | None = None
    symbol: str
    task_type: str
    rating: int
    prompt_version: str | None = None


class AiCachePayload(BaseModel):
    kind: str
    cache_key: str
    payload: dict[str, object]
    symbol: str | None = None
    task_type: str | None = None
    ttl_seconds: int | None = None


class AiToolCachePayload(BaseModel):
    cache_key: str
    tool_name: str
    args: dict[str, object]
    payload: dict[str, object]
    ttl_seconds: int = 900


class AiBudgetPayload(BaseModel):
    provider: str = "azure_openai"
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BacktestPayload(BaseModel):
    strategy_id: str = "ma_trend_pullback"
    timeframe: str = "daily"
    params: dict[str, object] | None = None
    refresh: bool = False


class WatchlistPayload(BaseModel):
    name: str
    kind: str = "swing"
    symbols: list[str] = []


class OpenPaperTradePayload(BaseModel):
    symbol: str
    side: str = "BUY"
    quantity: float
    entry_price: float
    product: str = "intraday"
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    strategy_id: Optional[str] = None
    timeframe: Optional[str] = None
    grade: Optional[str] = None
    notes: Optional[str] = None
    metadata: dict[str, object] | None = None


class ClosePaperTradePayload(BaseModel):
    exit_price: float
    notes: Optional[str] = None


class AutoPaperTradePayload(BaseModel):
    symbol: str
    timeframe: str = "15m"


class StrategyImportPayload(BaseModel):
    url: Optional[str] = None
    spec: Optional[dict[str, object]] = None


class StrategyRunPayload(BaseModel):
    symbol: str
    timeframe: str = "daily"
    refresh: bool = False


class StrategyBenchPayload(BaseModel):
    symbol: str
    timeframe: str = "daily"
    strategy_ids: Optional[list[str]] = None
    refresh: bool = False


class SessionShortlistPayload(BaseModel):
    symbol: str
    reason: Optional[str] = None
    factors: Optional[dict[str, object]] = None


class SessionPickPayload(BaseModel):
    symbol: str
    direction: str = "long"
    plan: Optional[dict[str, object]] = None
    sized_qty: Optional[float] = None
    notes: Optional[str] = None


class SessionPicksPayload(BaseModel):
    picks: list[SessionPickPayload] = []


class SessionEventPayload(BaseModel):
    kind: str
    symbol: Optional[str] = None
    payload: Optional[dict[str, object]] = None


class SessionMacroPayload(BaseModel):
    snapshot: dict[str, object]


class SessionNotesPayload(BaseModel):
    notes: str


class FactorBatchPayload(BaseModel):
    symbols: list[str]
    timeframe: str = "daily"
    refresh: bool = False


class CommentaryFirePayload(BaseModel):
    symbol: str
    paper_trade: Optional[dict[str, object]] = None


class CommentaryEventPayload(BaseModel):
    symbol: str
    kind: str
    payload: dict[str, object] = {}
    paper_trade: Optional[dict[str, object]] = None


class ShortlistRankerPayload(BaseModel):
    symbols: list[str]
    timeframe: str = "daily"


class LiveFocusPayload(BaseModel):
    symbol: Optional[str] = None


class AiSettingsPayload(BaseModel):
    ai_enabled: Optional[bool] = None
    commentary_enabled: Optional[bool] = None
    commentary_cadence_seconds: Optional[int] = None
    event_triggers: Optional[dict[str, bool]] = None
    require_heartbeat: Optional[bool] = None
    heartbeat_grace_seconds: Optional[int] = None


def admin_guard(request: Request) -> None:
    token = os.getenv("ADMIN_TOKEN")
    if token and request.headers.get("x-admin-token") != token:
        raise HTTPException(status_code=403, detail="Admin token required.")
    origin = request.headers.get("origin") or ""
    host = request.client.host if request.client else ""
    if origin and not _is_loopback(origin):
        raise HTTPException(status_code=403, detail="Admin API is loopback-only.")
    if host and host not in {"127.0.0.1", "::1", "localhost"} and not host.startswith("172.") and not host.startswith("10."):
        # Allow Docker/private network during local dev, reject obvious remote callers.
        raise HTTPException(status_code=403, detail="Admin API is local-only.")


AdminOnly = Depends(admin_guard)


class AdminFlagPayload(BaseModel):
    key: str
    value: bool


class AdminUiConfigPayload(BaseModel):
    tokens: dict[str, object] | None = None
    layout: dict[str, object] | None = None
    reset: bool = False


class AdminCacheFlushPayload(BaseModel):
    kind: str = "all"
    confirm_token: str | None = None


class AdminConfirmIntentPayload(BaseModel):
    action: str
    details: dict[str, object] | None = None


class AdminPaperResetPayload(BaseModel):
    confirm_token: str


class AdminSessionResetPayload(BaseModel):
    confirm_token: str


class AdminConfirmPayload(BaseModel):
    confirm_token: str


class AdminSqlQueryPayload(BaseModel):
    sql: str


class AdminFactorWeightsPayload(BaseModel):
    weights: dict[str, float]


@app.middleware("http")
async def usage_middleware(request, call_next):
    started = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - started) * 1000, 1)
    if request.url.path != "/api/usage":
        api_usage["total_requests"] = int(api_usage["total_requests"]) + 1
        if response.status_code >= 400:
            api_usage["error_requests"] = int(api_usage["error_requests"]) + 1
        api_usage["recent"].append(
            {
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            }
        )
        budget().record_endpoint(request.url.path, duration_ms, response.status_code)
    return response


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "database": str(settings.database_path),
        "benchmark": settings.benchmark_symbol,
        "read_only": True,
        "supported_timeframes": list(TIMEFRAME_MAP.keys()),
        "intraday_leverage": settings.intraday_leverage,
        "paper_capital": settings.paper_capital,
        "telegram_enabled": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }


@app.get("/api/usage")
def usage() -> dict[str, object]:
    now = time.time()
    recent = [item for item in list(api_usage["recent"]) if now - item["timestamp"] <= 300]
    return {
        "total_requests": api_usage["total_requests"],
        "error_requests": api_usage["error_requests"],
        "recent_5m": len(recent),
        "uptime_seconds": round(now - api_started_at),
        "last_status": recent[-1]["status"] if recent else None,
        "last_path": recent[-1]["path"] if recent else None,
        "avg_duration_ms_5m": round(sum(item["duration_ms"] for item in recent) / len(recent), 1) if recent else 0,
    }


# -------- Regime / breadth --------

@app.get("/api/regime")
def regime(refresh: bool = False) -> dict[str, object]:
    return regime_service.snapshot(refresh=refresh)


# -------- Account --------

@app.get("/api/account/summary")
def account_summary() -> dict[str, object]:
    return account_service.summary()


@app.get("/api/account/positions")
def account_positions() -> dict[str, object]:
    return account_service.positions()


@app.get("/api/account/holdings")
def account_holdings() -> dict[str, object]:
    return account_service.holdings()


@app.get("/api/account/orders")
def account_orders(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    return account_service.orders(page=page, page_size=page_size)


@app.get("/api/account/orders/{order_id}")
def account_order_detail(order_id: str, segment: str = "CASH") -> dict[str, object]:
    return account_service.order_detail(order_id=order_id, segment=segment)


@app.get("/api/account/alerts")
def account_alerts(symbol: str | None = None) -> dict[str, object]:
    return account_service.alerts(symbol=symbol)


@app.post("/api/account/alerts/evaluate")
def evaluate_account_alerts(symbol: str | None = None, deliver: bool = False) -> dict[str, object]:
    result = account_service.evaluate_alerts(symbol=symbol)
    if deliver and result.get("items"):
        result["delivery"] = alerts_delivery.deliver(result["items"])
    return result


@app.post("/api/alerts/deliver")
def deliver_alerts(symbol: str | None = None) -> dict[str, object]:
    items = account_service.alerts(symbol=symbol)["items"]
    return alerts_delivery.deliver(items)


# -------- Instruments --------

@app.get("/api/instruments")
def instruments(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
    refresh: bool = False,
) -> dict[str, object]:
    items = market_data_service.load_instruments(refresh=refresh, limit=limit, search=search)
    if search and not items:
        items = _fallback_instruments(search, limit)
    return {"items": items, "count": len(items)}


# -------- Scanner --------

@app.get("/api/scanner")
def scanner(
    limit: int = Query(default=25, ge=1, le=500),
    refresh: bool = False,
    universe: str = Query(default="watchlist", pattern="^(watchlist|nifty50|all)$"),
    symbols: str | None = None,
    timeframe: str = Query(default="daily", pattern=TIMEFRAME_PATTERN),
) -> dict[str, object]:
    rows = scanner_service.scan(limit=limit, refresh=refresh, universe=universe, symbols=symbols, timeframe=timeframe)
    return {"items": rows, "count": len(rows), "universe": universe, "symbols": symbols, "timeframe": timeframe}


# -------- Stock analysis --------

@app.get("/api/stocks/{symbol}/analysis")
def stock_analysis(
    symbol: str,
    refresh: bool = False,
    timeframe: str = Query(default="daily", pattern=TIMEFRAME_PATTERN),
    include_account: bool = False,
) -> dict[str, object]:
    detail = scanner_service.detail(symbol=symbol, refresh=refresh, timeframe=timeframe)
    detail["position_context"] = account_service.position_context(symbol, analysis=detail) if include_account else None
    detail["alerts"] = account_service.alerts(symbol=symbol)["items"]
    return detail


@app.get("/api/stocks/{symbol}/chart-context")
def stock_chart_context(
    symbol: str,
    timeframe: str = Query(default="daily", pattern=TIMEFRAME_PATTERN),
    refresh: bool = False,
) -> dict[str, object]:
    return scanner_service.chart_context(symbol=symbol, timeframe=timeframe, refresh=refresh)


@app.get("/api/stocks/{symbol}/quote")
def stock_quote(symbol: str) -> dict[str, object]:
    quote = market_data_service.latest_quote(symbol)
    if not quote:
        raise HTTPException(status_code=404, detail="No quote available.")
    return quote


@app.post("/api/stocks/{symbol}/backtest")
def stock_backtest(symbol: str, payload: BacktestPayload) -> dict[str, object]:
    return scanner_service.backtest(
        symbol=symbol,
        strategy_id=payload.strategy_id,
        timeframe=payload.timeframe,
        params=payload.params,
        refresh=payload.refresh,
    )


@app.get("/api/stocks/{symbol}/catalysts")
def catalysts(symbol: str, company: str | None = None, refresh: bool = False) -> dict[str, object]:
    items = catalyst_service.catalysts_for(symbol=symbol, company_name=company, refresh=refresh)
    return {"items": items, "count": len(items)}


# -------- AI reports cache --------

@app.get("/api/ai/reports")
def ai_reports(symbol: str, limit: int = Query(default=8, ge=1, le=25), task_type: str | None = None) -> dict[str, object]:
    items = storage.list_ai_reports(symbol=symbol, limit=limit, task_type=task_type)
    return {"items": items, "count": len(items)}


@app.post("/api/ai/reports")
def save_ai_report(payload: AiReportPayload) -> dict[str, object]:
    item = storage.add_ai_report(
        payload.symbol,
        {
            "company": payload.company,
            "content": payload.content,
            "model": payload.model,
            "source": payload.source,
            "prompt_version": payload.prompt_version,
            "context_hash": payload.context_hash,
            "context_summary": payload.context_summary,
        },
        task_type=payload.task_type,
    )
    return {"item": item}


@app.get("/api/ai/threads")
def ai_threads(symbol: str, task_type: str = "stock_report") -> dict[str, object]:
    items = ai_thread_service.list_threads(symbol=symbol, task_type=task_type)
    active = next((item for item in items if item.get("active")), None)
    if not active:
        active = ai_thread_service.ensure_thread(symbol=symbol, task_type=task_type)
        items = ai_thread_service.list_threads(symbol=symbol, task_type=task_type)
    return {"items": items, "active": active, "count": len(items)}


@app.post("/api/ai/threads")
def create_ai_thread(payload: AiThreadPayload) -> dict[str, object]:
    item = ai_thread_service.create_thread(
        symbol=payload.symbol,
        task_type=payload.task_type,
        title=payload.title,
        archive_existing=payload.archive_existing,
    )
    return {"item": item}


@app.post("/api/ai/threads/{thread_id}/clear")
def clear_ai_thread(thread_id: int) -> dict[str, object]:
    item = ai_thread_service.clear_thread(thread_id)
    if not item:
        raise HTTPException(status_code=404, detail="AI thread not found.")
    return {"item": item}


@app.get("/api/ai/messages")
def ai_messages(thread_id: int, limit: int = Query(default=10, ge=1, le=50)) -> dict[str, object]:
    items = ai_thread_service.messages(thread_id=thread_id, limit=limit)
    return {"items": items, "count": len(items)}


@app.post("/api/ai/messages")
def save_ai_message(payload: AiMessagePayload) -> dict[str, object]:
    item = ai_thread_service.add_message(
        thread_id=payload.thread_id,
        role=payload.role,
        content=payload.content,
        tool_name=payload.tool_name,
        payload=payload.payload,
        prompt_version=payload.prompt_version,
    )
    return {"item": item}


@app.post("/api/ai/feedback")
def save_ai_feedback(payload: AiFeedbackPayload) -> dict[str, object]:
    item = ai_thread_service.record_feedback(
        message_id=payload.message_id,
        symbol=payload.symbol,
        task_type=payload.task_type,
        rating=payload.rating,
        prompt_version=payload.prompt_version,
    )
    summary = ai_thread_service.feedback_summary(task_type=payload.task_type, prompt_version=payload.prompt_version)
    return {"item": item, "summary": summary}


@app.get("/api/ai/feedback/summary")
def ai_feedback_summary(task_type: str, prompt_version: str | None = None) -> dict[str, object]:
    return ai_thread_service.feedback_summary(task_type=task_type, prompt_version=prompt_version)


@app.get("/api/ai/cache")
def get_ai_cache(kind: str, cache_key: str) -> dict[str, object]:
    item = ai_thread_service.get_cache(kind=kind, cache_key=cache_key)
    if not item:
        raise HTTPException(status_code=404, detail="AI cache miss.")
    return {"item": item}


@app.post("/api/ai/cache")
def set_ai_cache(payload: AiCachePayload) -> dict[str, object]:
    return ai_thread_service.set_cache(
        kind=payload.kind,
        cache_key=payload.cache_key,
        payload=payload.payload,
        symbol=payload.symbol,
        task_type=payload.task_type,
        ttl_seconds=payload.ttl_seconds,
    )


@app.get("/api/ai/tool-cache")
def get_ai_tool_cache(cache_key: str) -> dict[str, object]:
    item = ai_thread_service.get_tool_cache(cache_key)
    if not item:
        raise HTTPException(status_code=404, detail="AI tool cache miss.")
    return {"item": item}


@app.post("/api/ai/tool-cache")
def set_ai_tool_cache(payload: AiToolCachePayload) -> dict[str, object]:
    return ai_thread_service.set_tool_cache(
        cache_key=payload.cache_key,
        tool_name=payload.tool_name,
        args=payload.args,
        payload=payload.payload,
        ttl_seconds=payload.ttl_seconds,
    )


@app.post("/api/ai/budget")
def record_ai_budget(payload: AiBudgetPayload) -> dict[str, object]:
    budget().record_tokens(payload.provider, payload.prompt_tokens, payload.completion_tokens)
    return budget().snapshot()


# -------- Watchlists --------

@app.get("/api/watchlists")
def list_watchlists() -> dict[str, object]:
    items = watchlists_service.list()
    return {"items": items, "count": len(items)}


@app.post("/api/watchlists")
def save_watchlist(payload: WatchlistPayload) -> dict[str, object]:
    item = watchlists_service.save(name=payload.name, kind=payload.kind, symbols=payload.symbols)
    return {"item": item}


@app.delete("/api/watchlists/{name}")
def delete_watchlist(name: str) -> dict[str, object]:
    return {"deleted": watchlists_service.delete(name)}


# -------- Paper trades --------

@app.get("/api/paper/trades")
def list_paper_trades(
    status: str | None = Query(default=None, pattern="^(open|closed)$"),
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    return paper_service.list_trades(status=status, symbol=symbol, limit=limit)


@app.get("/api/paper/summary")
def paper_summary() -> dict[str, object]:
    return paper_service.summary()


@app.post("/api/paper/trades")
def open_paper_trade(payload: OpenPaperTradePayload) -> dict[str, object]:
    return paper_service.open(payload.model_dump())


@app.post("/api/paper/trades/{trade_id}/close")
def close_paper_trade(trade_id: int, payload: ClosePaperTradePayload) -> dict[str, object]:
    closed = paper_service.close(trade_id=trade_id, exit_price=payload.exit_price, notes=payload.notes)
    if not closed:
        raise HTTPException(status_code=404, detail="Trade not found or already closed.")
    return closed


@app.post("/api/paper/auto-open")
def auto_open_paper_trade(payload: AutoPaperTradePayload) -> dict[str, object]:
    detail = scanner_service.detail(symbol=payload.symbol, timeframe=payload.timeframe)
    intraday = detail.get("intraday_view") or {}
    signal = intraday.get("primary_signal")
    if not signal or not signal.get("entry"):
        return {"opened": None, "reason": "No actionable intraday signal yet."}
    analysis_for_paper = detail.get("intraday_analysis") or detail.get("daily_analysis") or {}
    trade = paper_service.auto_open_from_signal(
        symbol=payload.symbol,
        signal=signal,
        analysis=analysis_for_paper,
        timeframe=payload.timeframe,
    )
    if not trade:
        return {"opened": None, "reason": "Open trade already exists or invalid risk."}
    return {"opened": trade}


# -------- Public sources (NSE / Google Finance / Screener) --------

@app.get("/api/sources/usage")
def sources_usage() -> dict[str, object]:
    return public_data_service.usage()


@app.get("/api/sources/budget")
def sources_budget() -> dict[str, object]:
    return budget().snapshot()


@app.get("/api/sources/market-status")
def sources_market_status() -> dict[str, object]:
    data = public_data_service.market_status()
    if data is None:
        raise HTTPException(status_code=502, detail="Market status unavailable.")
    return data


@app.get("/api/sources/breadth")
def sources_breadth() -> dict[str, object]:
    return public_data_service.breadth()


@app.get("/api/sources/fii-dii")
def sources_fii_dii() -> dict[str, object]:
    return {"items": public_data_service.fii_dii()}


@app.get("/api/sources/quote/{symbol}")
def sources_quote(symbol: str) -> dict[str, object]:
    data = public_data_service.quote(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail="Quote not available from public sources.")
    return data


@app.get("/api/sources/fundamentals/{symbol}")
def sources_fundamentals(symbol: str) -> dict[str, object]:
    data = public_data_service.fundamentals(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail="Fundamentals not available.")
    return data


@app.get("/api/sources/option-chain/{symbol}")
def sources_option_chain(symbol: str) -> dict[str, object]:
    data = public_data_service.option_chain(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail="Option chain unavailable for this symbol.")
    return data


@app.get("/api/sources/announcements")
def sources_announcements(symbol: str | None = None) -> dict[str, object]:
    return {"items": public_data_service.corporate_announcements(symbol=symbol)}


# -------- Strategy Lab --------

@app.get("/api/strategies")
def list_strategies() -> dict[str, object]:
    items = strategy_service.list()
    return {"items": items, "count": len(items)}


@app.post("/api/strategies/import")
def import_strategy(payload: StrategyImportPayload) -> dict[str, object]:
    try:
        if payload.url:
            record = strategy_service.import_from_url(payload.url)
        elif payload.spec:
            record = strategy_service.import_inline(payload.spec)
        else:
            raise HTTPException(status_code=400, detail="Provide either 'url' or 'spec'.")
    except GitHubImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"item": record}


@app.delete("/api/strategies/{strategy_id}")
def delete_strategy(strategy_id: str) -> dict[str, object]:
    return {"deleted": strategy_service.delete(strategy_id)}


@app.post("/api/strategies/{strategy_id}/run")
def run_strategy_endpoint(strategy_id: str, payload: StrategyRunPayload) -> dict[str, object]:
    try:
        return strategy_service.run(strategy_id, payload.symbol, timeframe=payload.timeframe, refresh=payload.refresh)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/strategies/bench")
def bench_strategies(payload: StrategyBenchPayload) -> dict[str, object]:
    return strategy_service.bench(symbol=payload.symbol, timeframe=payload.timeframe, strategy_ids=payload.strategy_ids, refresh=payload.refresh)


# -------- Trading session (one per IST trading day) --------

@app.get("/api/session")
def session_current() -> dict[str, object]:
    return session_service.current()


@app.get("/api/session/history")
def session_history(limit: int = Query(default=30, ge=1, le=180)) -> dict[str, object]:
    items = session_service.history(limit=limit)
    return {"items": items, "count": len(items)}


@app.post("/api/session/shortlist")
def session_add_shortlist(payload: SessionShortlistPayload) -> dict[str, object]:
    return session_service.add_to_shortlist(payload.symbol, reason=payload.reason, factors=payload.factors)


@app.delete("/api/session/shortlist/{symbol}")
def session_remove_shortlist(symbol: str) -> dict[str, object]:
    return session_service.remove_from_shortlist(symbol)


@app.delete("/api/session/shortlist")
def session_clear_shortlist() -> dict[str, object]:
    return session_service.clear_shortlist()


@app.post("/api/session/picks")
def session_set_picks(payload: SessionPicksPayload) -> dict[str, object]:
    return session_service.set_picks([item.model_dump() for item in payload.picks])


@app.delete("/api/session/picks/{symbol}")
def session_remove_pick(symbol: str) -> dict[str, object]:
    return session_service.remove_pick(symbol)


@app.post("/api/session/macro")
def session_set_macro(payload: SessionMacroPayload) -> dict[str, object]:
    return session_service.set_macro(payload.snapshot)


@app.post("/api/session/notes")
def session_set_notes(payload: SessionNotesPayload) -> dict[str, object]:
    return session_service.update_notes(payload.notes)


@app.post("/api/session/events")
def session_post_event(payload: SessionEventPayload) -> dict[str, object]:
    return session_service.record_event(payload.kind, payload.symbol, payload.payload)


@app.get("/api/session/events")
def session_events(
    since_id: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    kinds: Optional[str] = None,
) -> dict[str, object]:
    parsed = [token.strip() for token in (kinds or "").split(",") if token.strip()] or None
    items = session_service.events_since(since_id=since_id, limit=limit, kinds=parsed)
    return {"items": items, "count": len(items), "next_since_id": items[-1]["id"] if items else since_id}


@app.post("/api/session/close")
def session_close() -> dict[str, object]:
    return session_service.close()


# -------- AI governance (settings + heartbeat + status) --------

@app.get("/api/ai/settings")
def ai_settings_get() -> dict[str, object]:
    return ai_settings_service.settings()


@app.put("/api/ai/settings")
def ai_settings_update(payload: AiSettingsPayload) -> dict[str, object]:
    fields = {key: value for key, value in payload.model_dump().items() if value is not None}
    return ai_settings_service.update(**fields)


@app.post("/api/ai/heartbeat")
def ai_heartbeat() -> dict[str, object]:
    ai_settings_service.heartbeat()
    return ai_settings_service.status()


@app.get("/api/ai/status")
def ai_status() -> dict[str, object]:
    return ai_settings_service.status()


@app.post("/api/ai/enable")
def ai_enable() -> dict[str, object]:
    ai_settings_service.enable_now()
    return ai_settings_service.status()


@app.post("/api/ai/disable")
def ai_disable() -> dict[str, object]:
    ai_settings_service.disable_now()
    return ai_settings_service.status()


# -------- Factor pipeline (Phase 2 + 4) --------

@app.get("/api/factors/{symbol}")
def factor_for(symbol: str, timeframe: str = Query(default="daily", pattern=TIMEFRAME_PATTERN), refresh: bool = False) -> dict[str, object]:
    return factor_pipeline.snapshot(symbol, timeframe=timeframe, refresh=refresh)


@app.post("/api/factors/batch")
def factors_batch(payload: FactorBatchPayload) -> dict[str, object]:
    if payload.timeframe not in {"5m", "15m", "30m", "hourly", "daily"}:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    rows = factor_pipeline.batch(payload.symbols, timeframe=payload.timeframe, refresh=payload.refresh)
    return {"items": rows, "count": len(rows)}


# -------- Global cues + Calendar (Phase 9) --------

@app.get("/api/sources/global-cues")
def global_cues(refresh: bool = False) -> dict[str, object]:
    return global_cues_service.snapshot(refresh=refresh)


@app.get("/api/sources/calendar")
def calendar(refresh: bool = False) -> dict[str, object]:
    return calendar_service.snapshot(refresh=refresh)


# -------- Live feed (Phase 5 + 6) --------

@app.get("/api/live/stream")
async def live_stream() -> StreamingResponse:
    await live_feed.ensure_running()
    queue: asyncio.Queue[str] = live_feed.subscribe()

    async def event_generator():
        try:
            # Send an initial hello so the client knows we're connected.
            yield "event: connected\ndata: {\"ok\": true}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:  # pragma: no cover - client disconnect
            return
        finally:
            live_feed.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/live/focus")
def live_focus(payload: LiveFocusPayload) -> dict[str, object]:
    live_feed.focus(payload.symbol)
    return {"focused": payload.symbol}


# -------- AI commentary (Phase 7) --------

@app.post("/api/ai/commentary/manual")
def commentary_manual(payload: CommentaryFirePayload) -> dict[str, object]:
    return ai_commentary_service.manual(symbol=payload.symbol, paper_trade=payload.paper_trade)


@app.post("/api/ai/commentary/event")
def commentary_event(payload: CommentaryEventPayload) -> dict[str, object]:
    result = ai_commentary_service.fire_event(
        symbol=payload.symbol,
        kind=payload.kind,
        payload=payload.payload,
        paper_trade=payload.paper_trade,
    )
    if result is None:
        raise HTTPException(status_code=409, detail="Event trigger disabled or cooled down.")
    return result


@app.post("/api/ai/commentary/cadence")
def commentary_cadence(payload: CommentaryFirePayload) -> dict[str, object]:
    result = ai_commentary_service.maybe_fire_cadence(symbol=payload.symbol, paper_trade=payload.paper_trade)
    if result is None:
        raise HTTPException(status_code=409, detail="Cadence not yet due or no open paper trade.")
    return result


# -------- Shortlist ranker AI task (Phase 8) --------

@app.post("/api/ai/shortlist-ranker")
def ai_shortlist_ranker(payload: ShortlistRankerPayload) -> dict[str, object]:
    decision = ai_settings_service.gate()
    if not decision.allowed:
        # Deterministic ranking by long_score - short_score difference (best long picks first).
        rows = factor_pipeline.batch(payload.symbols, timeframe=payload.timeframe)
        rows.sort(key=lambda row: (row.get("long_score") or 0) - (row.get("short_score") or 0), reverse=True)
        return {
            "ranking": [
                {
                    "symbol": row["symbol"],
                    "bias": row.get("bias"),
                    "long_score": row.get("long_score"),
                    "short_score": row.get("short_score"),
                    "reason": ", ".join((row.get("rationale") or {}).get("top_positive") or []) or "balanced score",
                }
                for row in rows
            ],
            "fallback": True,
            "reason": decision.reason,
        }
    # AI path is a stub that returns the same scoring with a placeholder reason; the frontend
    # AI panel does the actual Azure call (so token accounting flows through that route).
    rows = factor_pipeline.batch(payload.symbols, timeframe=payload.timeframe)
    rows.sort(key=lambda row: (row.get("long_score") or 0), reverse=True)
    return {"ranking": [{"symbol": row["symbol"], "long_score": row.get("long_score"), "short_score": row.get("short_score"), "bias": row.get("bias")} for row in rows]}


# -------- Admin panel --------

@app.get("/api/admin/overview", dependencies=[AdminOnly])
def admin_overview() -> dict[str, object]:
    return admin_metrics.overview()


@app.get("/api/admin/metrics", dependencies=[AdminOnly])
def admin_metrics_route() -> dict[str, object]:
    return admin_metrics.metrics()


@app.get("/api/admin/metrics/series", dependencies=[AdminOnly])
def admin_metrics_series(window_seconds: int = 3600, bucket_seconds: int = 300) -> dict[str, object]:
    return admin_metrics.series(window_seconds=window_seconds, bucket_seconds=bucket_seconds)


@app.get("/api/admin/health", dependencies=[AdminOnly])
def admin_health_route() -> dict[str, object]:
    items = admin_health.probes()
    return {"items": items, "count": len(items)}


@app.get("/api/admin/health/log", dependencies=[AdminOnly])
def admin_health_log(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    items = admin_health.log(limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/admin/logs/sessions", dependencies=[AdminOnly])
def admin_session_logs(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    with storage.connect() as conn:
        rows = conn.execute("select * from session_events order by id desc limit ?", (limit,)).fetchall()
    items = [_decode_json_fields(dict(row), "payload") for row in rows]
    return {"items": items, "count": len(items)}


@app.get("/api/admin/logs/alerts", dependencies=[AdminOnly])
def admin_alert_logs(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    with storage.connect() as conn:
        rows = conn.execute(
            """
            select ae.*, ad.channel, ad.status as delivery_status, ad.message as delivery_message, ad.delivered_at
            from alert_events ae
            left join alert_deliveries ad on ad.event_key = ae.event_key
            order by ae.created_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}


@app.get("/api/admin/logs/ai-threads", dependencies=[AdminOnly])
def admin_ai_threads(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    with storage.connect() as conn:
        rows = conn.execute(
            """
            select t.*, (
                select content from ai_messages m where m.thread_id = t.id order by m.id desc limit 1
            ) as last_message
            from ai_threads t
            order by t.updated_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}


@app.get("/api/admin/logs/ai-messages", dependencies=[AdminOnly])
def admin_ai_messages(thread_id: int | None = None, limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    query = "select * from ai_messages"
    params: list[object] = []
    if thread_id:
        query += " where thread_id = ?"
        params.append(thread_id)
    query += " order by id desc limit ?"
    params.append(limit)
    with storage.connect() as conn:
        rows = conn.execute(query, params).fetchall()
    items = [_decode_json_fields(dict(row), "payload") for row in rows]
    return {"items": items, "count": len(items)}


@app.get("/api/admin/feature-flags", dependencies=[AdminOnly])
def admin_feature_flags() -> dict[str, object]:
    return {"flags": feature_flags.all()}


@app.post("/api/admin/feature-flags", dependencies=[AdminOnly])
def admin_feature_flags_set(payload: AdminFlagPayload) -> dict[str, object]:
    before = feature_flags.all().get(payload.key)
    flags = feature_flags.set(payload.key, payload.value)
    admin_audit.append("feature_flags.set", {"key": payload.key, "before": before, "after": payload.value})
    return {"flags": flags}


@app.get("/api/admin/ui-config", dependencies=[AdminOnly])
def admin_ui_config() -> dict[str, object]:
    return ui_config_store.get()


@app.post("/api/admin/ui-config", dependencies=[AdminOnly])
def admin_ui_config_update(payload: AdminUiConfigPayload) -> dict[str, object]:
    before = ui_config_store.get()
    result = ui_config_store.reset() if payload.reset else ui_config_store.update(tokens=payload.tokens, layout=payload.layout)
    admin_audit.append("ui_config.update", {"before": before, "after": result})
    return result


@app.get("/api/admin/audit", dependencies=[AdminOnly])
def admin_audit_route(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, object]:
    items = admin_audit.list(limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/admin/db/schema", dependencies=[AdminOnly])
def admin_db_schema() -> dict[str, object]:
    return admin_metrics.schema_summary()


@app.get("/api/admin/db/query", dependencies=[AdminOnly])
def admin_db_query(sql: str) -> dict[str, object]:
    return _run_readonly_query(sql)


@app.post("/api/admin/db/query", dependencies=[AdminOnly])
def admin_db_query_post(payload: AdminSqlQueryPayload) -> dict[str, object]:
    return _run_readonly_query(payload.sql)


@app.get("/api/admin/exports/{table}.csv", dependencies=[AdminOnly])
def admin_export_table(table: str) -> PlainTextResponse:
    _assert_table_name(table)
    with storage.connect() as conn:
        rows = conn.execute(f"select * from {table} limit 10000").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        writer.writerows([list(row) for row in rows])
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={table}.csv"})


@app.get("/api/admin/factor-weights", dependencies=[AdminOnly])
def admin_factor_weights() -> dict[str, object]:
    return {"weights": factor_pipeline.weights}


@app.post("/api/admin/factor-weights", dependencies=[AdminOnly])
def admin_factor_weights_set(payload: AdminFactorWeightsPayload) -> dict[str, object]:
    total = round(sum(payload.weights.values()), 4)
    if total != 100:
        raise HTTPException(status_code=400, detail="Factor weights must sum to 100.")
    before = dict(factor_pipeline.weights)
    factor_pipeline.weights = {key: int(value) for key, value in payload.weights.items()}
    admin_audit.append("factor_weights.update", {"before": before, "after": factor_pipeline.weights})
    return {"weights": factor_pipeline.weights}


@app.post("/api/admin/confirm/intent", dependencies=[AdminOnly])
def admin_confirm_intent(payload: AdminConfirmIntentPayload) -> dict[str, object]:
    return confirm_tokens.issue(payload.action, payload.details)


@app.post("/api/admin/cache/flush", dependencies=[AdminOnly])
def admin_cache_flush(payload: AdminCacheFlushPayload) -> dict[str, object]:
    kind = payload.kind
    cleared: dict[str, object] = {}
    if kind in {"all", "quotes", "factors"}:
        public_data_service._cache.data.clear()
        cleared["public_data_cache"] = True
    if kind in {"all", "candles"}:
        with storage.connect() as conn:
            deleted = conn.execute("delete from candles").rowcount
        cleared["candles"] = deleted
    if kind in {"all", "ai_cache"}:
        with storage.connect() as conn:
            cleared["ai_cache"] = conn.execute("delete from ai_cache").rowcount
            cleared["ai_tool_cache"] = conn.execute("delete from ai_tool_cache").rowcount
    admin_audit.append("cache.flush", {"kind": kind, "cleared": cleared})
    return {"kind": kind, "cleared": cleared}


@app.post("/api/admin/nse/refresh-session", dependencies=[AdminOnly])
def admin_nse_refresh() -> dict[str, object]:
    public_data_service.nse._ensure_session(force=True)
    admin_audit.append("nse.refresh_session")
    return {"ok": True}


@app.post("/api/admin/live-feed/restart", dependencies=[AdminOnly])
async def admin_live_restart() -> dict[str, object]:
    if live_feed.task and not live_feed.task.done():
        live_feed.task.cancel()
        await asyncio.sleep(0)
    live_feed.task = None
    await live_feed.ensure_running()
    admin_audit.append("live_feed.restart")
    return {"ok": True}


@app.post("/api/admin/paper/reset", dependencies=[AdminOnly])
def admin_paper_reset(payload: AdminPaperResetPayload) -> dict[str, object]:
    confirm_tokens.consume(payload.confirm_token, "paper.reset")
    with storage.connect() as conn:
        deleted = conn.execute("delete from paper_trades").rowcount
    admin_audit.append("paper.reset", {"deleted": deleted})
    return {"deleted": deleted}


@app.post("/api/admin/session/reset", dependencies=[AdminOnly])
def admin_session_reset(payload: AdminSessionResetPayload) -> dict[str, object]:
    confirm_tokens.consume(payload.confirm_token, "session.reset")
    current = session_service.current()
    with storage.connect() as conn:
        conn.execute("delete from session_events where session_date = ?", (current["session_date"],))
        conn.execute(
            "update trading_sessions set status = 'open', shortlist = '[]', picks = '[]', notes = '', updated_at = current_timestamp where session_date = ?",
            (current["session_date"],),
        )
    admin_audit.append("session.reset", {"session_date": current["session_date"]})
    return session_service.current()


@app.post("/api/admin/db/vacuum", dependencies=[AdminOnly])
def admin_db_vacuum(payload: AdminConfirmPayload) -> dict[str, object]:
    confirm_tokens.consume(payload.confirm_token, "db.vacuum")
    conn = sqlite3.connect(settings.database_path)
    try:
        conn.execute("vacuum")
    finally:
        conn.close()
    admin_audit.append("db.vacuum")
    return {"ok": True}


@app.post("/api/admin/db/backup", dependencies=[AdminOnly])
def admin_db_backup() -> dict[str, object]:
    backups = settings.database_path.parent / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    target = backups / f"groww_trader-{int(time.time())}.sqlite3"
    shutil.copy2(settings.database_path, target)
    admin_audit.append("db.backup", {"path": str(target)})
    return {"path": str(target)}


@app.get("/api/admin/stream", dependencies=[AdminOnly])
async def admin_stream() -> StreamingResponse:
    async def event_generator():
        last_event_id = 0
        while True:
            metrics_payload = json.dumps(admin_metrics.metrics(), default=str)
            yield f"event: metrics\ndata: {metrics_payload}\n\n"
            with storage.connect() as conn:
                rows = conn.execute("select * from session_events where id > ? order by id asc limit 20", (last_event_id,)).fetchall()
            for row in rows:
                last_event_id = row["id"]
                yield f"event: event\ndata: {json.dumps(_decode_json_fields(dict(row), 'payload'), default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _fallback_instruments(search: str, limit: int) -> list[dict[str, str]]:
    common = [
        ("RELIANCE", "Reliance Industries"),
        ("TCS", "TCS"),
        ("INFY", "Infosys"),
        ("HDFCBANK", "HDFC Bank"),
        ("ICICIBANK", "ICICI Bank"),
        ("SBIN", "State Bank of India"),
        ("LT", "Larsen & Toubro"),
        ("AXISBANK", "Axis Bank"),
        ("ITC", "ITC"),
        ("BHARTIARTL", "Bharti Airtel"),
        ("KOTAKBANK", "Kotak Mahindra Bank"),
        ("HINDUNILVR", "Hindustan Unilever"),
        ("BAJFINANCE", "Bajaj Finance"),
        ("MARUTI", "Maruti Suzuki"),
        ("SUNPHARMA", "Sun Pharma"),
        ("TITAN", "Titan"),
        ("ULTRACEMCO", "UltraTech Cement"),
        ("ASIANPAINT", "Asian Paints"),
        ("WIPRO", "Wipro"),
        ("POWERGRID", "Power Grid Corporation"),
    ]
    query = search.upper()
    matches = [
        {
            "exchange": "NSE",
            "trading_symbol": symbol,
            "groww_symbol": f"NSE-{symbol}",
            "name": name,
            "instrument_type": "EQ",
            "segment": "CASH",
            "series": "EQ",
        }
        for symbol, name in common
        if query in symbol or query in name.upper()
    ]
    return matches[:limit]


def _is_loopback(origin: str) -> bool:
    return any(host in origin for host in ("localhost", "127.0.0.1", "[::1]"))


def _decode_json_fields(row: dict[str, object], *keys: str) -> dict[str, object]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str):
            try:
                row[key] = json.loads(value or "{}")
            except json.JSONDecodeError:
                pass
    return row


def _assert_table_name(table: str) -> None:
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table name.")
    with storage.connect() as conn:
        exists = conn.execute("select 1 from sqlite_master where type='table' and name = ?", (table,)).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Table not found.")


def _run_readonly_query(sql: str) -> dict[str, object]:
    text = sql.strip().rstrip(";")
    lowered = text.lower()
    if ";" in text or not (lowered.startswith("select ") or lowered.startswith("pragma ")):
        raise HTTPException(status_code=400, detail="Only a single SELECT or PRAGMA statement is allowed.")
    blocked = (" insert ", " update ", " delete ", " drop ", " alter ", " create ", " attach ", " detach ", " vacuum ", " replace ")
    padded = f" {lowered} "
    if any(token in padded for token in blocked):
        raise HTTPException(status_code=400, detail="Query must be read-only.")
    limited = text if lowered.startswith("pragma ") or " limit " in lowered else f"{text} limit 500"
    with storage.connect() as conn:
        rows = conn.execute(limited).fetchall()
    return {"columns": list(rows[0].keys()) if rows else [], "rows": [dict(row) for row in rows], "count": len(rows), "capped": len(rows) >= 500}
