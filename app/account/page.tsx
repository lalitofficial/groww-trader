import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { AccountAutoRefresh } from "@/components/AccountAutoRefresh";
import { AccountRiskCards, AlertsPanel, OrdersTable, PositionsTable } from "@/components/AccountTables";
import { Header } from "@/components/Header";
import { evaluateAccountAlerts, getAccountAlerts, getAccountHoldings, getAccountOrders, getAccountPositions, getAccountSummary } from "@/lib/api";

export default async function AccountPage({ searchParams }: { searchParams: Promise<{ evaluate?: string }> }) {
  const params = await searchParams;
  if (params.evaluate === "true") {
    await evaluateAccountAlerts().catch(() => ({ items: [], count: 0 }));
  }

  const [summary, positions, holdings, orders, alerts] = await Promise.all([
    getAccountSummary().catch((error) => ({ margin: { error: error.message }, positions_count: 0, holdings_count: 0, orders_count: 0, errors: [error.message], read_only: true })),
    getAccountPositions().catch((error) => ({ items: [], count: 0, error: error.message })),
    getAccountHoldings().catch((error) => ({ items: [], count: 0, error: error.message })),
    getAccountOrders().catch((error) => ({ items: [], count: 0, error: error.message })),
    getAccountAlerts().catch(() => ({ items: [], count: 0 })),
  ]);

  const liveItems = [...positions.items, ...holdings.items];

  return (
    <main className="shell">
      <Header subtitle="Live read-only positions, orders, risk, and alerts" />
      <div className="content">
        <div className="page-header-row">
          <div>
            <span className="eyebrow">Read-only account cockpit</span>
            <h1>Positions, alerts, and order context</h1>
            <p className="muted">Use this page to monitor live exposure and jump back into a stock-level thesis.</p>
          </div>
          <div className="toolbar">
            <Link className="btn btn-secondary" href="/">
              <ArrowLeft size={14} />
              Analyzer
            </Link>
            <Link className="btn btn-primary" href="/account?evaluate=true">
              <RefreshCw size={14} />
              Evaluate alerts
            </Link>
            <AccountAutoRefresh />
          </div>
        </div>

        {summary.errors?.length ? (
          <section className="panel">
            <div className="panel-body">
              <strong>Account data warning</strong>
              <p className="muted">{summary.errors.join(" ")}</p>
            </div>
          </section>
        ) : null}

        <div className="metrics">
          <Metric label="Positions" value={summary.positions_count} />
          <Metric label="Holdings" value={summary.holdings_count} />
          <Metric label="Orders" value={summary.orders_count} />
          <Metric label="Mode" value={summary.read_only ? "Read-only" : "Unknown"} />
        </div>

        <div className="workspace-grid">
          <div className="primary-column">
            <AlertsPanel alerts={alerts.items} />
            <AccountRiskCards items={liveItems} />
          </div>
          <aside className="side-rail">
            <OrdersTable items={orders.items} error={orders.error} />
          </aside>
        </div>

        <div className="two-column">
          <div className="stack">
            <PositionsTable title="Positions" items={positions.items} error={positions.error} />
            <PositionsTable title="Holdings" items={holdings.items} error={holdings.error} />
          </div>
        </div>
      </div>
    </main>
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
