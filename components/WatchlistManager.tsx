"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { deleteWatchlist, getWatchlists, saveWatchlist } from "@/lib/api";
import type { Watchlist } from "@/lib/types";

export function WatchlistManager() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [activeName, setActiveName] = useState<string>("");
  const [editing, setEditing] = useState<Watchlist | null>(null);
  const [draft, setDraft] = useState({ name: "", kind: "intraday" as "intraday" | "swing", symbols: "" });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await getWatchlists();
      setWatchlists(data.items);
      if (!activeName && data.items.length) setActiveName(data.items[0].name);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Watchlists unavailable");
    }
  }, [activeName]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = useMemo(() => watchlists.find((item) => item.name === activeName) || watchlists[0] || null, [watchlists, activeName]);

  async function save() {
    setError("");
    try {
      const symbols = draft.symbols.split(/[,\s]+/).map((value) => value.trim()).filter(Boolean);
      await saveWatchlist({ name: draft.name.trim() || `Watchlist ${Date.now()}`, kind: draft.kind, symbols });
      setDraft({ name: "", kind: "intraday", symbols: "" });
      setEditing(null);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    }
  }

  async function remove(name: string) {
    if (!confirm(`Delete watchlist ${name}?`)) return;
    await deleteWatchlist(name);
    await load();
  }

  function edit(item: Watchlist) {
    setEditing(item);
    setDraft({ name: item.name, kind: (item.kind as "intraday" | "swing") || "swing", symbols: item.symbols.join(", ") });
  }

  return (
    <section className="panel watchlist-panel">
      <div className="panel-header">
        <div>
          <strong>Watchlists</strong>
          <div className="muted">Intraday and swing baskets — used by the scanner</div>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            setEditing(null);
            setDraft({ name: "", kind: "intraday", symbols: "" });
          }}
        >
          <Plus size={14} />
          New
        </button>
      </div>
      <div className="panel-body stack">
        {error ? <div className="context-badge warning">{error}</div> : null}
        <div className="watchlist-tabs">
          {watchlists.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.name === active?.name ? "active" : ""}
              onClick={() => setActiveName(item.name)}
            >
              {item.name}
              <span className="muted">{item.symbols.length}</span>
            </button>
          ))}
        </div>
        {active ? (
          <div className="watchlist-symbols">
            {active.symbols.map((symbol) => (
              <Link key={symbol} href={`/stock/${symbol}?timeframe=15m`} className="watchlist-chip">
                {symbol}
              </Link>
            ))}
            {active.symbols.length === 0 ? <span className="muted">Empty watchlist</span> : null}
          </div>
        ) : null}
        <div className="watchlist-actions">
          {active ? (
            <button type="button" className="btn btn-secondary" onClick={() => edit(active)}>
              Edit {active.name}
            </button>
          ) : null}
          {active && active.name.toLowerCase() !== "default" ? (
            <button type="button" className="btn btn-secondary" onClick={() => remove(active.name)}>
              <Trash2 size={13} />
              Delete
            </button>
          ) : null}
        </div>
        <div className="watchlist-editor">
          <strong>{editing ? `Edit ${editing.name}` : "Create watchlist"}</strong>
          <div className="watchlist-fields">
            <input
              className="input"
              placeholder="Name"
              value={draft.name}
              onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))}
            />
            <select
              className="input"
              value={draft.kind}
              onChange={(event) => setDraft((value) => ({ ...value, kind: event.target.value as "intraday" | "swing" }))}
            >
              <option value="intraday">Intraday</option>
              <option value="swing">Swing</option>
            </select>
            <textarea
              className="textarea"
              placeholder="RELIANCE, TCS, HDFCBANK..."
              rows={3}
              value={draft.symbols}
              onChange={(event) => setDraft((value) => ({ ...value, symbols: event.target.value }))}
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={save}>
            <Save size={13} />
            Save
          </button>
        </div>
      </div>
    </section>
  );
}
