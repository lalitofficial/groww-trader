import Link from "next/link";
import { AccountAiRisk } from "@/components/AccountAiRisk";
import type { AccountOrder, AccountPosition, AlertEvent } from "@/lib/types";

export function AccountRiskCards({ items }: { items: AccountPosition[] }) {
  return (
    <div className="risk-card-grid">
      {items.map((item) => (
        <article className="panel" key={`${item.kind}-${item.symbol}`}>
          <div className="panel-header">
            <div>
              <strong>{item.symbol}</strong>
              <div className="muted">{item.kind} · qty {fmt(item.quantity)}</div>
            </div>
            <Link className="btn btn-secondary" href={`/stock/${item.symbol}`}>
              Analyze
            </Link>
          </div>
          <div className="panel-body kv-list">
            <Row label="Avg price" value={item.average_price} />
            <Row label="Current price" value={item.current_price} />
            <Row label="Day P&L" value={item.day_pnl} />
            <Row label="Unrealized P&L" value={item.unrealized_pnl} />
            <Row label="Support" value={item.nearest_support} />
            <Row label="Resistance" value={item.nearest_resistance} />
            <Row label="Dist to support" value={pct(item.distance_to_support_pct)} />
            <Row label="Dist to resistance" value={pct(item.distance_to_resistance_pct)} />
            <AccountAiRisk symbol={item.symbol} />
          </div>
        </article>
      ))}
      {items.length === 0 ? <Empty title="No live holdings or positions returned." /> : null}
    </div>
  );
}

export function PositionsTable({ title, items, error }: { title: string; items: AccountPosition[]; error?: string }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>{title}</strong>
        <span className="muted">{items.length} rows</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Qty</th>
              <th>Avg</th>
              <th>LTP</th>
              <th>Day P&L</th>
              <th>Unrealized</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${title}-${item.symbol}`}>
                <td>
                  <Link href={`/stock/${item.symbol}`}>
                    <strong>{item.symbol}</strong>
                  </Link>
                </td>
                <td>{fmt(item.quantity)}</td>
                <td>{fmt(item.average_price)}</td>
                <td>{fmt(item.current_price)}</td>
                <td>{fmt(item.day_pnl)}</td>
                <td>{fmt(item.unrealized_pnl)}</td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  {error || "No rows."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OrdersTable({ items, error }: { items: AccountOrder[]; error?: string }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>Recent Orders</strong>
        <span className="muted">{items.length} rows</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Symbol</th>
              <th>Status</th>
              <th>Side</th>
              <th>Qty</th>
              <th>Filled</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.order_id || `${item.symbol}-${item.created_at}`}>
                <td>{item.order_id || "-"}</td>
                <td>{item.symbol || "-"}</td>
                <td>{item.status || "-"}</td>
                <td>{item.transaction_type || "-"}</td>
                <td>{fmt(item.quantity)}</td>
                <td>{fmt(item.filled_quantity)}</td>
                <td>{fmt(item.price)}</td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  {error || "No recent orders."}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function AlertsPanel({ alerts }: { alerts: AlertEvent[] }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>Active Alerts</strong>
        <span className="muted">{alerts.length} triggered</span>
      </div>
      <div className="panel-body stack">
        {alerts.map((alert) => (
          <article className={`alert ${alert.severity}`} key={alert.event_key}>
            <strong>{alert.symbol} · {alert.title}</strong>
            <p>{alert.message}</p>
            <div className="muted">{alert.created_at || "just now"}</div>
          </article>
        ))}
        {alerts.length === 0 ? <div className="muted">No active alerts.</div> : null}
      </div>
    </section>
  );
}

export function PositionOverlay({ item }: { item?: AccountPosition | null }) {
  if (!item) return null;
  return (
    <section className="panel">
      <div className="panel-header">
        <strong>Live Position Context</strong>
        <span className="muted">Read-only Groww account data</span>
      </div>
      <div className="panel-body metrics">
        <Metric label="Kind" value={item.kind} />
        <Metric label="Qty" value={item.quantity} />
        <Metric label="Avg price" value={item.average_price} />
        <Metric label="Current" value={item.current_price} />
        <Metric label="Day P&L" value={item.day_pnl} />
        <Metric label="Unrealized" value={item.unrealized_pnl} />
        <Metric label="To support" value={pct(item.distance_to_support_pct)} />
        <Metric label="To resistance" value={pct(item.distance_to_resistance_pct)} />
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="kv">
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{String(value ?? "-")}</strong>
    </div>
  );
}

function Empty({ title }: { title: string }) {
  return (
    <section className="panel">
      <div className="panel-body muted">{title}</div>
    </section>
  );
}

function fmt(value?: number | null) {
  return value === null || value === undefined ? "-" : value.toLocaleString("en-IN");
}

function pct(value?: number | null) {
  return value === null || value === undefined ? "-" : `${value}%`;
}
