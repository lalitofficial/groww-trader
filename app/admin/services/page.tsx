import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminServicesPage() {
  const health = await safeAdminFetch<any>("/api/admin/health", { items: [] });
  const log = await safeAdminFetch<any>("/api/admin/health/log?limit=50", { items: [] });
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>Services</h1></div></div>
      <section className="admin-card">
        <h2>Provider Health</h2>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead><tr><th>Provider</th><th>State</th><th>Latency</th><th>Error</th><th>At</th></tr></thead>
            <tbody>
              {health.items.map((item: any) => (
                <tr key={item.provider}>
                  <td>{item.provider}</td>
                  <td><span className={item.ok ? "admin-dot ok" : "admin-dot bad"} />{item.ok ? "ok" : "fail"}</td>
                  <td>{item.latency_ms}ms</td>
                  <td>{item.error || "-"}</td>
                  <td>{item.at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="admin-card">
        <h2>Probe Log</h2>
        <AdminTable rows={log.items} />
      </section>
    </div>
  );
}

function AdminTable({ rows }: { rows: Array<Record<string, any>> }) {
  return <div className="admin-table-wrap"><table className="admin-table"><tbody>{rows.map((row) => <tr key={row.id}><td>{row.at}</td><td>{row.provider}</td><td>{row.ok ? "ok" : "fail"}</td><td>{row.error || "-"}</td></tr>)}</tbody></table></div>;
}
