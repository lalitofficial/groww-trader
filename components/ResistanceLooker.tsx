"use client";

import { Bot, RefreshCw } from "lucide-react";
import { useState } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import type { StockAnalysis } from "@/lib/types";

type Level = {
  level: number;
  type: "support" | "resistance";
  distance_pct: number;
  touches: number;
  strength: number;
};

export function ResistanceLooker({ levels = [], price, symbol, analysis }: { levels?: Level[]; price?: number | null; symbol: string; analysis: StockAnalysis }) {
  const [currentLevels, setCurrentLevels] = useState(levels);
  const [currentPrice, setCurrentPrice] = useState(price);
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [interpretation, setInterpretation] = useState("");
  const resistances = currentLevels.filter((item) => item.type === "resistance").sort((a, b) => a.level - b.level);
  const supports = currentLevels.filter((item) => item.type === "support").sort((a, b) => b.level - a.level);

  async function refreshLevels() {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"}/api/stocks/${encodeURIComponent(symbol)}/analysis?refresh=true`);
      const data = await response.json();
      setCurrentLevels(data.daily_analysis?.levels || []);
      setCurrentPrice(data.daily_analysis?.last_price ?? null);
    } finally {
      setLoading(false);
    }
  }

  async function interpretLevels(force = false) {
    setAiLoading(true);
    try {
      const response = await fetch("/api/ai/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis, task_type: "resistance_read", force }),
      });
      const data = await response.json();
      setInterpretation(data.content || data.error || "No interpretation returned.");
    } finally {
      setAiLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <strong>Resistance Looker</strong>
          <div className="muted">Live pivot clusters. Current price: {currentPrice ?? "-"}</div>
        </div>
        <div className="panel-actions">
          <button type="button" onClick={() => interpretLevels(false)} disabled={aiLoading} className="btn btn-secondary">
            <Bot size={14} />
            {aiLoading ? "Reading" : "Interpret Levels"}
          </button>
          <button type="button" onClick={refreshLevels} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={14} />
            {loading ? "Updating" : "Live Update"}
          </button>
        </div>
      </div>
      <div className="panel-body stack">
        <div className="source-strip">
          <span>Daily source: {analysis.data_source?.daily?.provider || "unknown"}</span>
          <span>{analysis.data_source?.daily?.freshness || analysis.data_freshness?.daily || "unknown"}</span>
          {analysis.data_source?.daily?.normalized_symbol ? <span>{analysis.data_source.daily.normalized_symbol}</span> : null}
        </div>
        <div className="level-focus">
          <LevelTable title="Resistance Stack" levels={resistances} currentPrice={currentPrice} priority />
          <LevelTable title="Support Floor" levels={supports} currentPrice={currentPrice} />
        </div>
        {interpretation ? <LevelInterpretation content={interpretation} /> : null}
      </div>
    </section>
  );
}

function LevelInterpretation({ content }: { content: string }) {
  let parsed: any = null;
  try {
    parsed = JSON.parse(content);
  } catch {
    parsed = null;
  }
  if (!parsed) {
    return (
      <div className="ai-report">
        <MarkdownView content={content} />
      </div>
    );
  }
  return (
    <div className="report-view">
      <div className="decision-card">
        <div>
          <span>Level Read</span>
          <strong>{parsed.decision?.stance || "Interpretation"}</strong>
          <p>{parsed.decision?.summary || "-"}</p>
        </div>
        <div className="decision-grade">
          <strong>{parsed.decision?.grade || "-"}</strong>
          <span>{parsed.decision?.confidence ?? "-"}%</span>
        </div>
      </div>
      {parsed.levels ? (
        <div className="setup-grid">
          {Object.entries(parsed.levels).map(([key, value]) => (
            <div className="mini-box" key={key}>
              <span>{key.replace(/_/g, " ")}</span>
              <strong>{String(value)}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function LevelTable({ title, levels, currentPrice, priority = false }: { title: string; levels: Level[]; currentPrice?: number | null; priority?: boolean }) {
  return (
    <div className={priority ? "level-table priority" : "level-table"}>
      <div className="level-table-title">
        <strong>{title}</strong>
        <span>{levels.length} levels</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Level</th>
            <th>Dist</th>
            <th>Price Gap</th>
            <th>Touches</th>
            <th>Strength</th>
          </tr>
        </thead>
        <tbody>
          {levels.map((item) => (
            <tr key={`${item.type}-${item.level}`}>
              <td>{item.level}</td>
              <td>{item.distance_pct}%</td>
              <td>{currentPrice ? Math.abs(item.level - currentPrice).toFixed(2) : "-"}</td>
              <td>{item.touches}</td>
              <td>
                <span className={`score ${item.strength >= 70 ? "high" : item.strength >= 40 ? "mid" : "low"}`}>{item.strength}</span>
              </td>
            </tr>
          ))}
          {levels.length === 0 ? (
            <tr>
              <td colSpan={5} className="muted">
                No levels found.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
