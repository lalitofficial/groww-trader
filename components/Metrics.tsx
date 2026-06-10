export function Metrics({ analysis, riskPlan }: { analysis: Record<string, any>; riskPlan: Record<string, any> }) {
  const items = [
    ["Price", analysis.last_price],
    ["Trend", analysis.trend_state],
    ["RSI", analysis.rsi],
    ["R:R", analysis.risk_reward],
    ["Support", analysis.support],
    ["Resistance", analysis.resistance],
    ["Qty", riskPlan.estimated_quantity],
    ["Risk budget", riskPlan.risk_budget],
  ];
  return (
    <div className="metrics">
      {items.map(([label, value]) => (
        <div className="metric" key={label}>
          <span>{label}</span>
          <strong>{value ?? "-"}</strong>
        </div>
      ))}
    </div>
  );
}
