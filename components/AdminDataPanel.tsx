"use client";

import { useState } from "react";
import { WatchlistManager } from "@/components/WatchlistManager";
import { StrategyLab } from "@/components/StrategyLab";
import { adminFetch } from "@/lib/admin";

export function AdminDataPanel({ initialWeights }: { initialWeights: Record<string, number> }) {
  const [weights, setWeights] = useState<Record<string, number>>(initialWeights || {});
  const [status, setStatus] = useState("");
  const total = Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0);

  async function saveWeights() {
    const result = await adminFetch("/api/admin/factor-weights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights }),
    });
    setWeights(result.weights);
    setStatus("Factor weights saved");
  }

  return (
    <div className="admin-grid two">
      <WatchlistManager />
      <StrategyLab />
      <section className="admin-card wide">
        <h2>Factor Weights</h2>
        <p className={total === 100 ? "admin-muted ok" : "admin-muted warn"}>Total {total}; must equal 100.</p>
        <div className="admin-slider-grid">
          {Object.entries(weights).map(([key, value]) => (
            <label key={key}>
              <span>{key.replace(/_/g, " ")}</span>
              <input type="range" min="0" max="40" value={value} onChange={(event) => setWeights((items) => ({ ...items, [key]: Number(event.target.value) }))} />
              <strong>{value}</strong>
            </label>
          ))}
        </div>
        <button className="admin-button primary" onClick={saveWeights} disabled={total !== 100}>Save weights</button>
        {status ? <p className="admin-muted">{status}</p> : null}
      </section>
    </div>
  );
}
