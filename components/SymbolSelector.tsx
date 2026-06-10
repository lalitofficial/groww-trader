"use client";

import { Search, X } from "lucide-react";
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import type { Instrument } from "@/lib/types";

export function SymbolSelector({ initialSymbols }: { initialSymbols: string }) {
  const [query, setQuery] = useState(initialSymbols);
  const [results, setResults] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const cleaned = useMemo(() => query.trim().toUpperCase(), [query]);

  useEffect(() => {
    const search = query.trim();
    if (search.length < 2) {
      setResults([]);
      return;
    }
    const timeout = window.setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setLoading(true);
      try {
        const response = await fetch(`/api/instruments/search?q=${encodeURIComponent(search)}`, {
          signal: controller.signal,
        });
        const data = await response.json();
        setResults(data.items || []);
        setOpen(true);
        setHighlighted(0);
      } catch (error) {
        if ((error as Error).name !== "AbortError") setResults([]);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => window.clearTimeout(timeout);
  }, [query]);

  function analyze() {
    const first = results[highlighted]?.trading_symbol || cleaned.split(/[,\s]/)[0];
    if (first) window.location.href = `/stock/${encodeURIComponent(first)}`;
  }

  function select(item: Instrument) {
    setQuery(item.trading_symbol);
    setOpen(false);
    window.location.href = `/stock/${encodeURIComponent(item.trading_symbol)}`;
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((value) => Math.min(value + 1, Math.max(results.length - 1, 0)));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((value) => Math.max(value - 1, 0));
    }
    if (event.key === "Enter") {
      event.preventDefault();
      analyze();
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <strong>Deep Stock Analyzer</strong>
          <div className="muted">Search NSE stock name or symbol.</div>
        </div>
        <button type="button" onClick={analyze} className="btn btn-primary">
          <Search size={14} />
          Analyze
        </button>
      </div>
      <div className="panel-body">
        <div className="field search-field">
          <label>Symbol or company</label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" size={15} />
            <input
              className="input h-9 pl-8 pr-8"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onFocus={() => setOpen(true)}
              onKeyDown={onKeyDown}
              placeholder="Reliance, TCS, Infosys..."
            />
            {query ? (
              <button type="button" className="btn-icon absolute right-1.5 top-1/2 -translate-y-1/2" onClick={() => setQuery("")} aria-label="Clear search">
                <X size={13} />
              </button>
            ) : null}
          </div>
          {open && (results.length > 0 || loading) ? (
            <div className="search-results">
              {loading ? <div className="search-row muted">Searching instruments...</div> : null}
              {results.map((item, index) => (
                <button
                  type="button"
                  className={`search-row ${index === highlighted ? "active" : ""}`}
                  key={item.groww_symbol || item.trading_symbol}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => select(item)}
                >
                  <strong>{item.trading_symbol}</strong>
                  <span>{item.name || item.groww_symbol}</span>
                  <em>{item.exchange} · {item.segment}</em>
                </button>
              ))}
            </div>
          ) : null}
          {query.length >= 2 && !loading && open && results.length === 0 ? (
            <div className="search-hint">
              No cached match yet. Press Analyze to try the typed symbol, or refresh instruments from the backend.
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
