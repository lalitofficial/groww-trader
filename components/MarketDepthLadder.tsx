"use client";

import type { LiveDepthEvent } from "@/lib/types";

export function MarketDepthLadder({ depth }: { depth: LiveDepthEvent | undefined }) {
  if (!depth) {
    return (
      <section className="panel depth-panel">
        <div className="panel-header">
          <strong>Order Book</strong>
        </div>
        <div className="panel-body muted">Waiting for depth…</div>
      </section>
    );
  }
  const maxQty = Math.max(
    ...depth.bids.map((row) => row.qty || 0),
    ...depth.asks.map((row) => row.qty || 0),
    1,
  );
  return (
    <section className="panel depth-panel">
      <div className="panel-header">
        <strong>Order Book</strong>
        <span className="muted">Imbalance {depth.imbalance ?? "-"}</span>
      </div>
      <div className="panel-body">
        <div className="depth-grid">
          <div>
            <div className="depth-head">Bid</div>
            {depth.bids.map((row, index) => (
              <div key={index} className="depth-row bid">
                <span className="depth-qty" style={{ width: `${Math.min(100, ((row.qty || 0) / maxQty) * 100)}%` }} />
                <span className="depth-price">{fmt(row.price)}</span>
                <span className="depth-qty-text">{fmtInt(row.qty)}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="depth-head">Ask</div>
            {depth.asks.map((row, index) => (
              <div key={index} className="depth-row ask">
                <span className="depth-qty" style={{ width: `${Math.min(100, ((row.qty || 0) / maxQty) * 100)}%` }} />
                <span className="depth-price">{fmt(row.price)}</span>
                <span className="depth-qty-text">{fmtInt(row.qty)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="depth-totals">
          <span>Total bid {fmtInt(depth.total_bid_qty)}</span>
          <span>Total ask {fmtInt(depth.total_ask_qty)}</span>
        </div>
      </div>
    </section>
  );
}

function fmt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "-";
}

function fmtInt(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? Math.round(value).toLocaleString("en-IN") : "-";
}
