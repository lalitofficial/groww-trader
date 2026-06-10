import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminOverviewPage() {
  const data = await safeAdminFetch<any>("/api/admin/overview", { budget: {}, api_usage: {}, paper: {}, ai: {}, events: [], audit: [], db: { tables: [] } });
  const budget = data.budget || {};
  const providers = budget.by_provider || {};

  return (
    <div className="admin-page">
      <header className="admin-head">
        <div>
          <span>Admin</span>
          <h1>Overview</h1>
        </div>
      </header>
      <div className="admin-card-grid">
        <Metric title="Calls / 1h" value={budget.total ?? 0} />
        <Metric title="API errors" value={data.api_usage?.errors_1h ?? data.api_usage?.error_requests ?? 0} tone="bad" />
        <Metric title="Open paper" value={data.paper?.open ?? 0} />
        <Metric title="AI threads" value={data.ai?.threads ?? 0} />
      </div>
      <div className="admin-grid two">
        <section className="admin-card">
          <h2>Request Budget</h2>
          <div className="admin-provider-list">
            {Object.entries(providers).map(([provider, row]: [string, any]) => (
              <div key={provider}><span>{provider}</span><strong>{row.total}</strong></div>
            ))}
          </div>
        </section>
        <section className="admin-card">
          <h2>Database</h2>
          <div className="admin-provider-list">
            {(data.db?.tables || []).slice(0, 12).map((table: any) => (
              <div key={table.table}><span>{table.table}</span><strong>{table.rows}</strong></div>
            ))}
          </div>
        </section>
        <section className="admin-card wide">
          <h2>Last Session Events</h2>
          <AdminTable rows={(data.events || []).slice(0, 20)} keys={["at", "kind", "symbol"]} />
        </section>
      </div>
    </div>
  );
}

function Metric({ title, value, tone = "" }: { title: string; value: unknown; tone?: string }) {
  return <section className={`admin-metric ${tone}`}><span>{title}</span><strong>{String(value)}</strong></section>;
}

function AdminTable({ rows, keys }: { rows: Array<Record<string, any>>; keys: string[] }) {
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <tbody>{rows.map((row, index) => <tr key={row.id || index}>{keys.map((key) => <td key={key}>{String(row[key] ?? "-")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
