from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _paper_trade_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "product": row["product"],
        "quantity": row["quantity"],
        "entry_price": row["entry_price"],
        "stop_loss": row["stop_loss"],
        "target": row["target"],
        "exit_price": row["exit_price"],
        "pnl": row["pnl"],
        "fees": row["fees"],
        "status": row["status"],
        "strategy_id": row["strategy_id"],
        "timeframe": row["timeframe"],
        "grade": row["grade"],
        "notes": row["notes"],
        "opened_at": row["opened_at"],
        "closed_at": row["closed_at"],
        "metadata": json.loads(row["metadata"] or "{}"),
    }


def _session_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_date": row["session_date"],
        "status": row["status"],
        "macro_snapshot": json.loads(row["macro_snapshot"] or "{}"),
        "shortlist": json.loads(row["shortlist"] or "[]"),
        "picks": json.loads(row["picks"] or "[]"),
        "notes": row["notes"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_date": row["session_date"],
        "symbol": row["symbol"],
        "kind": row["kind"],
        "payload": json.loads(row["payload"] or "{}"),
        "at": row["at"],
    }


def _ai_settings_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "ai_enabled": bool(row["ai_enabled"]),
        "commentary_enabled": bool(row["commentary_enabled"]),
        "commentary_cadence_seconds": int(row["commentary_cadence_seconds"]),
        "event_triggers": json.loads(row["event_triggers"] or "{}"),
        "require_heartbeat": bool(row["require_heartbeat"]),
        "heartbeat_grace_seconds": int(row["heartbeat_grace_seconds"]),
        "last_heartbeat_at": float(row["last_heartbeat_at"] or 0),
        "circuit_open_until": float(row["circuit_open_until"] or 0),
        "consecutive_failures": int(row["consecutive_failures"] or 0),
        "updated_at": row["updated_at"],
    }


def _decode_ai_report(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["payload"])
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "task_type": row["task_type"] if "task_type" in row.keys() else "stock_report",
        "updated_at": row["updated_at"],
        **payload,
    }


def _decode_candle_row(row: sqlite3.Row) -> dict[str, Any]:
    updated_at = row["updated_at"]
    age_seconds = None
    if updated_at:
        try:
            updated = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            age_seconds = max(0, int((datetime.now(timezone.utc) - updated).total_seconds()))
        except ValueError:
            age_seconds = None
    return {
        "cache_key": row["cache_key"],
        "trading_symbol": row["trading_symbol"],
        "exchange": row["exchange"],
        "segment": row["segment"],
        "interval_minutes": row["interval_minutes"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "provider": row["provider"],
        "normalized_symbol": row["normalized_symbol"],
        "warning": row["warning"],
        "error": row["error"],
        "updated_at": updated_at,
        "age_seconds": age_seconds,
        "payload": json.loads(row["payload"]),
    }


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists instruments (
                    groww_symbol text primary key,
                    trading_symbol text not null,
                    name text,
                    exchange text,
                    segment text,
                    payload text not null,
                    updated_at text default current_timestamp
                );

                create table if not exists candles (
                    cache_key text primary key,
                    trading_symbol text not null,
                    exchange text not null,
                    segment text not null,
                    interval_minutes integer not null,
                    start_time text not null,
                    end_time text not null,
                    provider text,
                    normalized_symbol text,
                    warning text,
                    error text,
                    payload text not null,
                    updated_at text default current_timestamp
                );

                create table if not exists catalysts (
                    id integer primary key autoincrement,
                    symbol text not null,
                    source_type text not null,
                    title text not null,
                    url text not null,
                    published_at text,
                    summary text,
                    relevance_score real default 0,
                    unique(symbol, url)
                );

                create table if not exists ai_reports (
                    id integer primary key autoincrement,
                    symbol text not null,
                    task_type text not null default 'stock_report',
                    payload text not null,
                    updated_at text default current_timestamp
                );

                create table if not exists ai_threads (
                    id integer primary key autoincrement,
                    symbol text not null,
                    task_type text not null,
                    title text,
                    active integer not null default 1,
                    created_at text default current_timestamp,
                    updated_at text default current_timestamp
                );

                create table if not exists ai_messages (
                    id integer primary key autoincrement,
                    thread_id integer not null,
                    role text not null,
                    content text not null,
                    tool_name text,
                    payload text,
                    prompt_version text,
                    created_at text default current_timestamp,
                    foreign key(thread_id) references ai_threads(id)
                );

                create table if not exists ai_feedback (
                    id integer primary key autoincrement,
                    message_id integer,
                    symbol text not null,
                    task_type text not null,
                    rating integer not null,
                    prompt_version text,
                    created_at text default current_timestamp
                );

                create table if not exists ai_cache (
                    cache_key text primary key,
                    kind text not null,
                    symbol text,
                    task_type text,
                    payload text not null,
                    expires_at text,
                    updated_at text default current_timestamp
                );

                create table if not exists ai_tool_cache (
                    cache_key text primary key,
                    tool_name text not null,
                    args text not null,
                    payload text not null,
                    expires_at text,
                    updated_at text default current_timestamp
                );

                create table if not exists alert_rules (
                    id integer primary key autoincrement,
                    symbol text,
                    rule_type text not null,
                    threshold real,
                    enabled integer default 1,
                    payload text not null default '{}',
                    created_at text default current_timestamp
                );

                create table if not exists alert_events (
                    id integer primary key autoincrement,
                    event_key text not null unique,
                    symbol text not null,
                    severity text not null,
                    title text not null,
                    message text not null,
                    trigger_value real,
                    current_value real,
                    related_level real,
                    status text not null default 'active',
                    created_at text default current_timestamp
                );

                create table if not exists dismissed_alerts (
                    event_key text primary key,
                    dismissed_at text default current_timestamp
                );

                create table if not exists last_seen_order_statuses (
                    order_id text primary key,
                    status text,
                    payload text not null,
                    updated_at text default current_timestamp
                );

                create table if not exists watchlists (
                    id integer primary key autoincrement,
                    name text not null unique,
                    kind text not null default 'swing',
                    symbols text not null default '[]',
                    created_at text default current_timestamp,
                    updated_at text default current_timestamp
                );

                create table if not exists paper_trades (
                    id integer primary key autoincrement,
                    symbol text not null,
                    side text not null,
                    product text not null default 'intraday',
                    quantity real not null,
                    entry_price real not null,
                    stop_loss real,
                    target real,
                    exit_price real,
                    pnl real,
                    fees real default 0,
                    status text not null default 'open',
                    strategy_id text,
                    timeframe text,
                    grade text,
                    notes text,
                    opened_at text default current_timestamp,
                    closed_at text,
                    metadata text default '{}'
                );

                create table if not exists alert_deliveries (
                    id integer primary key autoincrement,
                    event_key text not null,
                    channel text not null,
                    status text not null,
                    message text,
                    delivered_at text default current_timestamp,
                    unique(event_key, channel)
                );

                create table if not exists user_strategies (
                    id integer primary key autoincrement,
                    spec_id text not null unique,
                    name text not null,
                    author text,
                    source_url text,
                    spec text not null,
                    enabled integer default 1,
                    created_at text default current_timestamp,
                    updated_at text default current_timestamp
                );

                create table if not exists trading_sessions (
                    id integer primary key autoincrement,
                    session_date text not null unique,
                    status text not null default 'open',
                    macro_snapshot text default '{}',
                    shortlist text default '[]',
                    picks text default '[]',
                    notes text default '',
                    created_at text default current_timestamp,
                    updated_at text default current_timestamp
                );

                create table if not exists session_events (
                    id integer primary key autoincrement,
                    session_date text not null,
                    symbol text,
                    kind text not null,
                    payload text default '{}',
                    at text default current_timestamp
                );

                create table if not exists ai_settings (
                    id integer primary key check (id = 1),
                    ai_enabled integer not null default 1,
                    commentary_enabled integer not null default 1,
                    commentary_cadence_seconds integer not null default 300,
                    event_triggers text not null default '{}',
                    require_heartbeat integer not null default 1,
                    heartbeat_grace_seconds integer not null default 600,
                    last_heartbeat_at real default 0,
                    circuit_open_until real default 0,
                    consecutive_failures integer default 0,
                    updated_at text default current_timestamp
                );

                create table if not exists feature_flags (
                    key text primary key,
                    value text not null,
                    updated_at text default current_timestamp
                );

                create table if not exists ui_config (
                    id integer primary key check (id = 1),
                    tokens text not null default '{}',
                    layout text not null default '{}',
                    updated_at text default current_timestamp
                );

                create table if not exists admin_audit_log (
                    id integer primary key autoincrement,
                    action text not null,
                    details text default '{}',
                    at text default current_timestamp
                );

                create table if not exists provider_health_log (
                    id integer primary key autoincrement,
                    provider text not null,
                    ok integer not null,
                    status_code integer,
                    latency_ms real,
                    error text,
                    at text default current_timestamp
                );
                """
            )
            columns = [row["name"] for row in conn.execute("pragma table_info(ai_reports)").fetchall()]
            if "id" not in columns:
                conn.executescript(
                    """
                    alter table ai_reports rename to ai_reports_legacy;
                    create table ai_reports (
                        id integer primary key autoincrement,
                        symbol text not null,
                        task_type text not null default 'stock_report',
                        payload text not null,
                        updated_at text default current_timestamp
                    );
                    insert into ai_reports(symbol, task_type, payload, updated_at)
                    select symbol, 'stock_report', payload, updated_at from ai_reports_legacy;
                    drop table ai_reports_legacy;
                    """
                )
            else:
                report_columns = [row["name"] for row in conn.execute("pragma table_info(ai_reports)").fetchall()]
                if "task_type" not in report_columns:
                    conn.execute("alter table ai_reports add column task_type text not null default 'stock_report'")
            conn.execute("create index if not exists idx_ai_reports_symbol_updated on ai_reports(symbol, task_type, updated_at desc)")
            conn.execute("create index if not exists idx_ai_threads_symbol_task on ai_threads(symbol, task_type, active, updated_at desc)")
            conn.execute("create index if not exists idx_ai_messages_thread on ai_messages(thread_id, created_at desc)")
            conn.execute("create index if not exists idx_ai_cache_kind on ai_cache(kind, symbol, task_type, updated_at desc)")
            conn.execute("create index if not exists idx_session_events_date on session_events(session_date, at desc)")
            conn.execute("create index if not exists idx_session_events_symbol on session_events(symbol, at desc)")
            conn.execute("create index if not exists idx_provider_health_provider_at on provider_health_log(provider, at desc)")
            conn.execute("create index if not exists idx_admin_audit_at on admin_audit_log(at desc)")
            conn.execute("insert or ignore into ui_config(id, tokens, layout) values (1, '{}', '{}')")
            conn.execute(
                "insert or ignore into ai_settings(id, event_triggers) values (1, ?)",
                (json.dumps({
                    "near_stop": True,
                    "near_target": True,
                    "level_break_up": True,
                    "level_break_down": True,
                    "vol_spike": True,
                    "supertrend_flip": True,
                    "vwap_cross_up": True,
                    "vwap_cross_down": True,
                    "orb_break_up": True,
                    "orb_break_down": True,
                    "rsi_extreme": False,
                    "pnl_milestone": True,
                    "daily_loss_threshold": True,
                }),),
            )
            candle_columns = [row["name"] for row in conn.execute("pragma table_info(candles)").fetchall()]
            for column, kind in (
                ("provider", "text"),
                ("normalized_symbol", "text"),
                ("warning", "text"),
                ("error", "text"),
            ):
                if column not in candle_columns:
                    conn.execute(f"alter table candles add column {column} {kind}")

    def upsert_instruments(self, instruments: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                insert into instruments(groww_symbol, trading_symbol, name, exchange, segment, payload, updated_at)
                values(:groww_symbol, :trading_symbol, :name, :exchange, :segment, :payload, current_timestamp)
                on conflict(groww_symbol) do update set
                    trading_symbol=excluded.trading_symbol,
                    name=excluded.name,
                    exchange=excluded.exchange,
                    segment=excluded.segment,
                    payload=excluded.payload,
                    updated_at=current_timestamp
                """,
                [
                    {
                        "groww_symbol": row.get("groww_symbol"),
                        "trading_symbol": row.get("trading_symbol"),
                        "name": row.get("name"),
                        "exchange": row.get("exchange"),
                        "segment": row.get("segment"),
                        "payload": json.dumps(row, default=str),
                    }
                    for row in instruments
                    if row.get("groww_symbol") and row.get("trading_symbol")
                ],
            )

    def list_instruments(self, search: str | None, limit: int) -> list[dict[str, Any]]:
        query = "select payload from instruments where exchange = 'NSE' and segment = 'CASH'"
        params: list[Any] = []
        if search:
            query += " and (trading_symbol like ? or name like ? or groww_symbol like ?)"
            like = f"%{search.upper()}%"
            params.extend([like, like, like])
        query += " order by trading_symbol limit ?"
        params.append(limit)
        with self.connect() as conn:
            return [json.loads(row["payload"]) for row in conn.execute(query, params)]

    def get_candles(self, key: str) -> dict[str, Any] | None:
        record = self.get_candles_record(key)
        return record["payload"] if record else None

    def get_candles_record(self, key: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select cache_key, trading_symbol, exchange, segment, interval_minutes, start_time, end_time,
                    provider, normalized_symbol, warning, error, payload, updated_at
                from candles
                where cache_key = ?
                """,
                (key,),
            ).fetchone()
            return _decode_candle_row(row) if row else None

    def get_latest_candles(self, trading_symbol: str, interval_minutes: int) -> dict[str, Any] | None:
        record = self.get_latest_candles_record(trading_symbol, interval_minutes)
        return record["payload"] if record else None

    def get_latest_candles_record(self, trading_symbol: str, interval_minutes: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select cache_key, trading_symbol, exchange, segment, interval_minutes, start_time, end_time,
                    provider, normalized_symbol, warning, error, payload, updated_at
                from candles
                where trading_symbol = ? and interval_minutes = ?
                order by updated_at desc
                limit 1
                """,
                (trading_symbol.upper(), interval_minutes),
            ).fetchone()
            return _decode_candle_row(row) if row else None

    def set_candles(self, key: str, metadata: dict[str, Any], payload: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into candles(
                    cache_key, trading_symbol, exchange, segment, interval_minutes, start_time, end_time,
                    provider, normalized_symbol, warning, error, payload, updated_at
                )
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
                on conflict(cache_key) do update set
                    provider=excluded.provider,
                    normalized_symbol=excluded.normalized_symbol,
                    warning=excluded.warning,
                    error=excluded.error,
                    payload=excluded.payload,
                    updated_at=current_timestamp
                """,
                (
                    key,
                    metadata["trading_symbol"],
                    metadata["exchange"],
                    metadata["segment"],
                    metadata["interval_minutes"],
                    metadata["start_time"],
                    metadata["end_time"],
                    metadata.get("provider"),
                    metadata.get("normalized_symbol"),
                    metadata.get("warning"),
                    metadata.get("error"),
                    json.dumps(payload, default=str),
                ),
            )

    def upsert_catalysts(self, symbol: str, catalysts: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                insert or ignore into catalysts(symbol, source_type, title, url, published_at, summary, relevance_score)
                values(:symbol, :source_type, :title, :url, :published_at, :summary, :relevance_score)
                """,
                [{**item, "symbol": symbol} for item in catalysts],
            )

    def list_catalysts(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select source_type, title, url, published_at, summary, relevance_score
                from catalysts
                where symbol = ?
                order by coalesce(published_at, '') desc, id desc
                limit ?
                """,
                (symbol.upper(), limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_ai_report(self, symbol: str, payload: dict[str, Any], task_type: str = "stock_report") -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into ai_reports(symbol, task_type, payload, updated_at)
                values(?, ?, ?, current_timestamp)
                """,
                (symbol.upper(), task_type, json.dumps(payload, default=str)),
            )
            row = conn.execute(
                """
                select id, symbol, task_type, payload, updated_at
                from ai_reports
                where id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            return _decode_ai_report(row)

    def list_ai_reports(self, symbol: str, limit: int = 8, task_type: str | None = None) -> list[dict[str, Any]]:
        query = """
            select id, symbol, task_type, payload, updated_at
            from ai_reports
            where symbol = ?
        """
        params: list[Any] = [symbol.upper()]
        if task_type:
            query += " and task_type = ?"
            params.append(task_type)
        query += " order by updated_at desc, id desc limit ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [_decode_ai_report(row) for row in rows]

    def upsert_alert_events(self, events: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                insert into alert_events(event_key, symbol, severity, title, message, trigger_value, current_value, related_level, status, created_at)
                values(:event_key, :symbol, :severity, :title, :message, :trigger_value, :current_value, :related_level, 'active', current_timestamp)
                on conflict(event_key) do update set
                    severity=excluded.severity,
                    title=excluded.title,
                    message=excluded.message,
                    trigger_value=excluded.trigger_value,
                    current_value=excluded.current_value,
                    related_level=excluded.related_level,
                    status='active'
                """,
                events,
            )

    def list_alert_events(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = """
            select event_key, symbol, severity, title, message, trigger_value, current_value, related_level, status, created_at
            from alert_events
            where status = 'active'
        """
        params: list[Any] = []
        if symbol:
            query += " and symbol = ?"
            params.append(symbol.upper())
        query += " order by created_at desc limit ?"
        params.append(limit)
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    # ------------------------------------------------------------------
    # Watchlists
    # ------------------------------------------------------------------
    def list_watchlists(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select id, name, kind, symbols, updated_at from watchlists order by name"
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "symbols": json.loads(row["symbols"] or "[]"),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def upsert_watchlist(self, name: str, kind: str, symbols: list[str]) -> dict[str, Any]:
        clean = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        with self.connect() as conn:
            conn.execute(
                """
                insert into watchlists(name, kind, symbols, updated_at)
                values(?, ?, ?, current_timestamp)
                on conflict(name) do update set
                    kind=excluded.kind,
                    symbols=excluded.symbols,
                    updated_at=current_timestamp
                """,
                (name.strip(), kind, json.dumps(clean)),
            )
            row = conn.execute(
                "select id, name, kind, symbols, updated_at from watchlists where name = ?",
                (name.strip(),),
            ).fetchone()
            return {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "symbols": json.loads(row["symbols"] or "[]"),
                "updated_at": row["updated_at"],
            }

    def delete_watchlist(self, name: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("delete from watchlists where name = ?", (name.strip(),))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Paper trades
    # ------------------------------------------------------------------
    def open_paper_trade(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into paper_trades(
                    symbol, side, product, quantity, entry_price, stop_loss, target,
                    fees, status, strategy_id, timeframe, grade, notes, metadata
                ) values(?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    payload["symbol"].upper(),
                    payload["side"].upper(),
                    payload.get("product", "intraday"),
                    float(payload["quantity"]),
                    float(payload["entry_price"]),
                    _opt_float(payload.get("stop_loss")),
                    _opt_float(payload.get("target")),
                    float(payload.get("fees", 0)),
                    payload.get("strategy_id"),
                    payload.get("timeframe"),
                    payload.get("grade"),
                    payload.get("notes"),
                    json.dumps(payload.get("metadata", {}), default=str),
                ),
            )
            return self.paper_trade(cursor.lastrowid)

    def close_paper_trade(self, trade_id: int, exit_price: float, fees: float = 0, notes: str | None = None) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from paper_trades where id = ? and status = 'open'", (trade_id,)
            ).fetchone()
            if not row:
                return None
            side = (row["side"] or "BUY").upper()
            qty = float(row["quantity"])
            entry = float(row["entry_price"])
            sign = 1 if side == "BUY" else -1
            gross_pnl = sign * (exit_price - entry) * qty
            total_fees = float(row["fees"] or 0) + float(fees or 0)
            pnl = gross_pnl - total_fees
            conn.execute(
                """
                update paper_trades
                set exit_price = ?, pnl = ?, fees = ?, status = 'closed',
                    closed_at = current_timestamp, notes = coalesce(?, notes)
                where id = ?
                """,
                (exit_price, pnl, total_fees, notes, trade_id),
            )
            return self.paper_trade(trade_id)

    def paper_trade(self, trade_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from paper_trades where id = ?", (trade_id,)).fetchone()
            return _paper_trade_row(row) if row else None

    def list_paper_trades(self, status: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "select * from paper_trades where 1=1"
        params: list[Any] = []
        if status:
            query += " and status = ?"
            params.append(status)
        if symbol:
            query += " and symbol = ?"
            params.append(symbol.upper())
        query += " order by opened_at desc limit ?"
        params.append(limit)
        with self.connect() as conn:
            return [_paper_trade_row(row) for row in conn.execute(query, params).fetchall()]

    def paper_trade_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute("select status, pnl, fees from paper_trades").fetchall()
        closed = [row for row in rows if row["status"] == "closed" and row["pnl"] is not None]
        open_count = sum(1 for row in rows if row["status"] == "open")
        wins = [row for row in closed if (row["pnl"] or 0) > 0]
        losses = [row for row in closed if (row["pnl"] or 0) <= 0]
        gross_profit = sum((row["pnl"] or 0) for row in wins)
        gross_loss = abs(sum((row["pnl"] or 0) for row in losses))
        total_pnl = sum((row["pnl"] or 0) for row in closed)
        total_fees = sum((row["fees"] or 0) for row in rows)
        return {
            "total_trades": len(closed),
            "open_trades": open_count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round((len(wins) / len(closed)) * 100, 2) if closed else 0,
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
            "total_fees": round(total_fees, 2),
            "expectancy": round(total_pnl / len(closed), 2) if closed else 0,
        }

    # ------------------------------------------------------------------
    # Trading sessions (one per trading day)
    # ------------------------------------------------------------------
    def get_or_create_session(self, session_date: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "select * from trading_sessions where session_date = ?", (session_date,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "insert into trading_sessions(session_date) values(?)",
                    (session_date,),
                )
                row = conn.execute(
                    "select * from trading_sessions where session_date = ?", (session_date,)
                ).fetchone()
            return _session_row(row)

    def update_session(self, session_date: str, **fields: Any) -> dict[str, Any]:
        if not fields:
            return self.get_or_create_session(session_date)
        allowed = {"status", "macro_snapshot", "shortlist", "picks", "notes"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown session fields: {sorted(unknown)}")
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            values.append(json.dumps(value) if key in {"macro_snapshot", "shortlist", "picks"} else value)
        values.append(session_date)
        with self.connect() as conn:
            conn.execute(
                f"update trading_sessions set {', '.join(assignments)}, updated_at = current_timestamp where session_date = ?",
                values,
            )
        return self.get_or_create_session(session_date)

    def list_sessions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from trading_sessions order by session_date desc limit ?", (limit,)
            ).fetchall()
            return [_session_row(row) for row in rows]

    def record_session_event(self, session_date: str, kind: str, symbol: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload or {})
        with self.connect() as conn:
            cursor = conn.execute(
                "insert into session_events(session_date, symbol, kind, payload) values(?, ?, ?, ?)",
                (session_date, symbol, kind, body),
            )
            row = conn.execute("select * from session_events where id = ?", (cursor.lastrowid,)).fetchone()
            return _event_row(row)

    def list_session_events(self, session_date: str, since_id: int = 0, limit: int = 200, kinds: list[str] | None = None) -> list[dict[str, Any]]:
        query = "select * from session_events where session_date = ? and id > ?"
        params: list[Any] = [session_date, since_id]
        if kinds:
            placeholders = ",".join("?" * len(kinds))
            query += f" and kind in ({placeholders})"
            params.extend(kinds)
        query += " order by id asc limit ?"
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [_event_row(row) for row in rows]

    # ------------------------------------------------------------------
    # AI settings (single row)
    # ------------------------------------------------------------------
    def ai_settings(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("select * from ai_settings where id = 1").fetchone()
            if row is None:
                conn.execute("insert into ai_settings(id, event_triggers) values (1, '{}')")
                row = conn.execute("select * from ai_settings where id = 1").fetchone()
            return _ai_settings_row(row)

    def update_ai_settings(self, **fields: Any) -> dict[str, Any]:
        allowed = {
            "ai_enabled",
            "commentary_enabled",
            "commentary_cadence_seconds",
            "event_triggers",
            "require_heartbeat",
            "heartbeat_grace_seconds",
            "last_heartbeat_at",
            "circuit_open_until",
            "consecutive_failures",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown AI settings fields: {sorted(unknown)}")
        if not fields:
            return self.ai_settings()
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            if key == "event_triggers":
                values.append(json.dumps(value))
            elif key in {"ai_enabled", "commentary_enabled", "require_heartbeat"}:
                values.append(1 if value else 0)
            else:
                values.append(value)
        with self.connect() as conn:
            conn.execute(
                f"update ai_settings set {', '.join(assignments)}, updated_at = current_timestamp where id = 1",
                values,
            )
        return self.ai_settings()

    # ------------------------------------------------------------------
    # User strategies
    # ------------------------------------------------------------------
    def list_user_strategies(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select spec_id, name, author, source_url, spec, enabled, updated_at from user_strategies order by updated_at desc"
            ).fetchall()
            return [
                {
                    "id": row["spec_id"],
                    "name": row["name"],
                    "author": row["author"],
                    "source_url": row["source_url"],
                    "spec": json.loads(row["spec"]),
                    "enabled": bool(row["enabled"]),
                    "kind": "user",
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def user_strategy(self, spec_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "select spec_id, name, author, source_url, spec, enabled, updated_at from user_strategies where spec_id = ?",
                (spec_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["spec_id"],
                "name": row["name"],
                "author": row["author"],
                "source_url": row["source_url"],
                "spec": json.loads(row["spec"]),
                "enabled": bool(row["enabled"]),
                "kind": "user",
                "updated_at": row["updated_at"],
            }

    def upsert_user_strategy(self, spec_id: str, name: str, spec: dict[str, Any], source_url: str | None, author: str | None) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                insert into user_strategies(spec_id, name, author, source_url, spec, updated_at)
                values(?, ?, ?, ?, ?, current_timestamp)
                on conflict(spec_id) do update set
                    name=excluded.name,
                    author=excluded.author,
                    source_url=excluded.source_url,
                    spec=excluded.spec,
                    updated_at=current_timestamp
                """,
                (spec_id, name, author, source_url, json.dumps(spec)),
            )
        return self.user_strategy(spec_id) or {}

    def delete_user_strategy(self, spec_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("delete from user_strategies where spec_id = ?", (spec_id,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Alert deliveries
    # ------------------------------------------------------------------
    def record_alert_delivery(self, event_key: str, channel: str, status: str, message: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into alert_deliveries(event_key, channel, status, message)
                values(?, ?, ?, ?)
                on conflict(event_key, channel) do update set
                    status=excluded.status,
                    message=excluded.message,
                    delivered_at=current_timestamp
                """,
                (event_key, channel, status, message),
            )

    def delivered_alert_keys(self, channel: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "select event_key from alert_deliveries where channel = ? and status = 'ok'",
                (channel,),
            ).fetchall()
            return {row["event_key"] for row in rows}

    def upsert_order_statuses(self, orders: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                insert into last_seen_order_statuses(order_id, status, payload, updated_at)
                values(:order_id, :status, :payload, current_timestamp)
                on conflict(order_id) do update set
                    status=excluded.status,
                    payload=excluded.payload,
                    updated_at=current_timestamp
                """,
                [
                    {
                        "order_id": row["order_id"],
                        "status": row.get("status"),
                        "payload": json.dumps(row, default=str),
                    }
                    for row in orders
                    if row.get("order_id")
                ],
            )
