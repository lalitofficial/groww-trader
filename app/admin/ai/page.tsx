import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminAiPage() {
  const metrics = await safeAdminFetch<any>("/api/admin/metrics", { budget: {} });
  const threads = await safeAdminFetch<any>("/api/admin/logs/ai-threads?limit=50", { items: [] });
  const messages = await safeAdminFetch<any>("/api/admin/logs/ai-messages?limit=50", { items: [] });
  const usage = metrics.budget?.token_usage?.azure_openai || {};
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>AI</h1></div></div>
      <div className="admin-card-grid">
        <Metric title="Prompt tokens" value={usage.prompt_tokens || 0} />
        <Metric title="Completion tokens" value={usage.completion_tokens || 0} />
        <Metric title="Total tokens" value={usage.total_tokens || 0} />
        <Metric title="Cost USD" value={usage.cost_usd_total || 0} />
      </div>
      <div className="admin-grid two">
        <section className="admin-card">
          <h2>Threads</h2>
          <Table rows={threads.items} keys={["id", "symbol", "task_type", "updated_at"]} />
        </section>
        <section className="admin-card">
          <h2>Recent Messages</h2>
          <Table rows={messages.items} keys={["created_at", "role", "tool_name", "content"]} />
        </section>
      </div>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: unknown }) {
  return <section className="admin-metric"><span>{title}</span><strong>{String(value)}</strong></section>;
}

function Table({ rows, keys }: { rows: Array<Record<string, any>>; keys: string[] }) {
  return <div className="admin-table-wrap"><table className="admin-table"><tbody>{rows.map((row, index) => <tr key={row.id || index}>{keys.map((key) => <td key={key}>{String(row[key] ?? "-").slice(0, 100)}</td>)}</tr>)}</tbody></table></div>;
}
