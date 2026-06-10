"use client";

import type { FactorSnapshot } from "@/lib/types";

const AXIS_ORDER = [
  "technical",
  "intraday_signal",
  "sentiment",
  "volume_volatility",
  "quant",
  "regime_fit",
  "event_proximity",
  "liquidity",
  "pattern",
];

const SHORT_LABELS: Record<string, string> = {
  technical: "Tech",
  intraday_signal: "Intra",
  sentiment: "Sent",
  volume_volatility: "Vol",
  quant: "Quant",
  regime_fit: "Regime",
  event_proximity: "Event",
  liquidity: "Liq",
  pattern: "Pttn",
};

export function FactorRadar({ snapshot, size = 120 }: { snapshot: FactorSnapshot; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.4;
  const subscores = snapshot.subscores || {};
  const points = AXIS_ORDER.map((axis, index) => {
    const angle = (index / AXIS_ORDER.length) * Math.PI * 2 - Math.PI / 2;
    const sub = subscores[axis];
    const longVal = (sub?.long || 0) / 100;
    const shortVal = (sub?.short || 0) / 100;
    return { axis, angle, longVal, shortVal };
  });

  const longPath = points.map((point, index) => {
    const x = cx + Math.cos(point.angle) * radius * point.longVal;
    const y = cy + Math.sin(point.angle) * radius * point.longVal;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ") + " Z";

  const shortPath = points.map((point, index) => {
    const x = cx + Math.cos(point.angle) * radius * point.shortVal;
    const y = cy + Math.sin(point.angle) * radius * point.shortVal;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ") + " Z";

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="factor-radar" width={size} height={size}>
      <circle cx={cx} cy={cy} r={radius} fill="rgba(255,255,255,0.02)" stroke="rgba(145,164,173,0.18)" />
      <circle cx={cx} cy={cy} r={radius * 0.66} fill="none" stroke="rgba(145,164,173,0.1)" />
      <circle cx={cx} cy={cy} r={radius * 0.33} fill="none" stroke="rgba(145,164,173,0.08)" />
      {points.map((point) => {
        const x = cx + Math.cos(point.angle) * radius;
        const y = cy + Math.sin(point.angle) * radius;
        const lx = cx + Math.cos(point.angle) * (radius + 8);
        const ly = cy + Math.sin(point.angle) * (radius + 8);
        return (
          <g key={point.axis}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(145,164,173,0.08)" />
            <text x={lx} y={ly} textAnchor="middle" className="factor-radar-label">{SHORT_LABELS[point.axis] || point.axis}</text>
          </g>
        );
      })}
      <path d={shortPath} fill="rgba(239,68,68,0.16)" stroke="#EF4444" strokeWidth={1} />
      <path d={longPath} fill="rgba(34,197,94,0.18)" stroke="#22C55E" strokeWidth={1.2} />
    </svg>
  );
}
