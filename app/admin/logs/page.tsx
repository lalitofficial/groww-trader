import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminLogsPage() {
  const [sessions, alerts, threads, audit] = await Promise.all([
    safeAdminFetch<any>("/api/admin/logs/sessions?limit=100", { items: [] }),
    safeAdminFetch<any>("/api/admin/logs/alerts?limit=100", { items: [] }),
    safeAdminFetch<any>("/api/admin/logs/ai-threads?limit=100", { items: [] }),
    safeAdminFetch<any>("/api/admin/audit?limit=100", { items: [] }),
  ]);
  const rows = [
    ...sessions.items.map((item: any) => ({ kind: `session:${item.kind}`, at: item.at, symbol: item.symbol, detail: JSON.stringify(item.payload || {}) })),
    ...alerts.items.map((item: any) => ({ kind: `alert:${item.severity}`, at: item.created_at, symbol: item.symbol, detail: item.message })),
    ...threads.items.map((item: any) => ({ kind: `ai:${item.task_type}`, at: item.updated_at, symbol: item.symbol, detail: item.last_message || item.title })),
    ...audit.items.map((item: any) => ({ kind: `audit:${item.action}`, at: item.at, symbol: "-", detail: JSON.stringify(item.details || {}) })),
  ].sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 200);
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>Logs</h1></div></div>
      <section className="admin-card">
        <h2>Unified Event Feed</h2>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <tbody>{rows.map((row, index) => <tr key={index}><td>{row.at}</td><td>{row.kind}</td><td>{row.symbol || "-"}</td><td>{String(row.detail).slice(0, 180)}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
