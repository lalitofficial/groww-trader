"use client";

import { useState } from "react";
import { adminFetch } from "@/lib/admin";

const TOKEN_LABELS = ["--bg", "--panel", "--ink", "--muted", "--accent", "--accent-2", "--warn", "--bad"];

export function AdminUiEditor({ initialFlags, initialUi }: { initialFlags: Record<string, boolean>; initialUi: Record<string, any> }) {
  const [flags, setFlags] = useState(initialFlags);
  const [tokens, setTokens] = useState<Record<string, string>>(initialUi.tokens || {});
  const [density, setDensity] = useState(initialUi.layout?.density || "compact");
  const [status, setStatus] = useState("");

  async function saveUi() {
    const result = await adminFetch("/api/admin/ui-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tokens, layout: { density } }),
    });
    setStatus(`Saved UI config at ${result.updated_at || "now"}`);
  }

  async function resetUi() {
    const result = await adminFetch("/api/admin/ui-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset: true }),
    });
    setTokens(result.tokens || {});
    setDensity(result.layout?.density || "compact");
    setStatus("Reset to Modern Elite");
  }

  async function toggle(key: string, value: boolean) {
    const result = await adminFetch("/api/admin/feature-flags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value }),
    });
    setFlags(result.flags);
  }

  return (
    <div className="admin-grid two">
      <section className="admin-card">
        <h2>Theme Editor</h2>
        <div className="admin-token-grid">
          {TOKEN_LABELS.map((key) => (
            <label key={key}>
              <span>{key}</span>
              <input type="color" value={tokens[key] || fallbackColor(key)} onChange={(event) => setTokens((value) => ({ ...value, [key]: event.target.value }))} />
              <input value={tokens[key] || ""} placeholder={fallbackColor(key)} onChange={(event) => setTokens((value) => ({ ...value, [key]: event.target.value }))} />
            </label>
          ))}
        </div>
        <div className="admin-row">
          <label>Density</label>
          <select value={density} onChange={(event) => setDensity(event.target.value)}>
            <option value="compact">Compact</option>
            <option value="cozy">Cozy</option>
            <option value="comfortable">Comfortable</option>
          </select>
        </div>
        <div className="admin-actions">
          <button className="admin-button primary" onClick={saveUi}>Save</button>
          <button className="admin-button" onClick={resetUi}>Reset to Modern Elite</button>
        </div>
        {status ? <p className="admin-muted">{status}</p> : null}
        <div className="admin-preview" style={tokens as any}>
          <strong>Preview Panel</strong>
          <p>Sample row, table line and action button.</p>
          <button className="admin-button primary">Primary</button>
        </div>
      </section>

      <section className="admin-card">
        <h2>Feature Flags</h2>
        <div className="admin-flag-list">
          {Object.entries(flags).map(([key, value]) => (
            <label key={key} className="admin-toggle">
              <span>{key.replace(/_/g, " ")}</span>
              <input type="checkbox" checked={value} onChange={(event) => toggle(key, event.target.checked)} />
            </label>
          ))}
        </div>
      </section>
    </div>
  );
}

function fallbackColor(key: string) {
  const map: Record<string, string> = {
    "--bg": "#0A0A0A",
    "--panel": "#111113",
    "--ink": "#F4F4F5",
    "--muted": "#A1A1AA",
    "--accent": "#22C55E",
    "--accent-2": "#3B82F6",
    "--warn": "#EAB308",
    "--bad": "#EF4444",
  };
  return map[key] || "#22C55E";
}
