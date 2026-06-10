import type { StockAnalysis } from "@/lib/types";

export function AnalysisPanels({ analysis }: { analysis: StockAnalysis }) {
  const daily = analysis.daily_analysis || {};
  return (
    <div className="analysis-grid">
      <Panel title="Predictive Profile" items={daily.predictive} />
      <Panel title="Alpha Factors" items={daily.alpha_factors} />
      <Panel title="Market Regime" items={daily.regime} />
      <section className="panel">
        <div className="panel-header">
          <strong>Strategy Signals</strong>
          <span className="muted">Directional, read-only</span>
        </div>
        <div className="panel-body stack">
          {(daily.strategies || []).map((signal: any) => (
            <div className="strategy" key={signal.name}>
              <div>
                <strong>{signal.name}</strong>
                <div className="muted">{signal.trigger}</div>
              </div>
              <span className={`score ${signal.active ? "high" : signal.quality > 50 ? "mid" : "low"}`}>{signal.quality}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Panel({ title, items }: { title: string; items?: Record<string, any> }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>{title}</strong>
      </div>
      <div className="panel-body kv-list">
        {Object.entries(items || {}).map(([key, value]) => (
          <div className="kv" key={key}>
            <span>{label(key)}</span>
            <strong>{format(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function label(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function format(value: any) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return value.toLocaleString("en-IN");
  return String(value);
}
