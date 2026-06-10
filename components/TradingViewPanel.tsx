"use client";

import { useEffect, useRef } from "react";

const INTERVAL_MAP: Record<string, string> = {
  "5m": "5",
  "15m": "15",
  "30m": "30",
  hourly: "60",
  "60m": "60",
  daily: "D",
};

export function TradingViewPanel({
  symbol,
  timeframe,
  compact = false,
}: {
  symbol: string;
  timeframe?: string | null;
  compact?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = "";
    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    const interval = INTERVAL_MAP[timeframe || "daily"] || "D";
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: `NSE:${symbol.toUpperCase()}`,
      interval,
      timezone: "Asia/Kolkata",
      theme: "dark",
      style: "1",
      locale: "en",
      allow_symbol_change: true,
      calendar: false,
      support_host: "https://www.tradingview.com",
      studies: ["STD;VWAP", "STD;RSI", "STD;MACD", "STD;Volume"],
    });
    containerRef.current.appendChild(widget);
    containerRef.current.appendChild(script);
  }, [symbol, timeframe]);

  return (
    <section className="panel tradingview-module">
      <div className="panel-header">
        <strong>TradingView</strong>
        <span className="muted">
          NSE:{symbol.toUpperCase()} · {timeframe || "daily"}
        </span>
      </div>
      <div className={`tradingview-widget-container tradingview-panel ${compact ? "compact" : ""}`} ref={containerRef} />
    </section>
  );
}
