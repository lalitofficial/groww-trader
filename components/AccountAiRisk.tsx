"use client";

import { Bot } from "lucide-react";
import { useState } from "react";

export function AccountAiRisk({ symbol }: { symbol: string }) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  async function summarize() {
    setLoading(true);
    try {
      const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
      const analysisResponse = await fetch(`${backend}/api/stocks/${encodeURIComponent(symbol)}/analysis`);
      const analysis = await analysisResponse.json();
      const response = await fetch("/api/ai/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis, task_type: "account_risk" }),
      });
      const data = await response.json();
      setContent(data.content || data.error || "No risk summary returned.");
    } finally {
      setLoading(false);
    }
  }

  const parsed = parse(content);

  return (
    <div className="stack">
      <button type="button" className="btn btn-secondary w-fit" onClick={summarize} disabled={loading}>
        <Bot size={14} />
        {loading ? "Reading risk" : "AI Risk"}
      </button>
      {parsed ? (
        <div className="context-badge">
          <strong>{parsed.decision?.stance || "Risk read"}</strong>
          <div>{parsed.decision?.summary || "-"}</div>
        </div>
      ) : content ? (
        <div className="context-badge">{content}</div>
      ) : null}
    </div>
  );
}

function parse(content: string) {
  if (!content) return null;
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}
