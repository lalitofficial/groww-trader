import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminMetricsPage() {
  const metrics = await safeAdminFetch<any>("/api/admin/metrics", { budget: {}, top_endpoints: [] });
  const series = await safeAdminFetch<any>("/api/admin/metrics/series", { items: [] });
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>Metrics</h1></div></div>
      <section className="admin-card">
        <h2>Endpoint Latency</h2>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead><tr><th>Endpoint</th><th>Count</th><th>Errors</th><th>p50</th><th>p95</th></tr></thead>
            <tbody>{metrics.top_endpoints.map((row: any) => <tr key={row.endpoint}><td>{row.endpoint}</td><td>{row.count}</td><td>{row.errors}</td><td>{row.p50_ms}ms</td><td>{row.p95_ms}ms</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className="admin-card">
        <h2>Rolling Series</h2>
        <div className="admin-spark-row">
          {series.items.map((item: any) => <div key={item.bucket} style={{ height: `${Math.max(4, item.count * 3)}px` }} title={`${item.count} calls`} />)}
        </div>
      </section>
    </div>
  );
}
