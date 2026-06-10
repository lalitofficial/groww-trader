"use client";

import { useState } from "react";
import { adminExportUrl, adminFetch } from "@/lib/admin";

export function AdminSystemPanel({ schema, audit }: { schema: Record<string, any>; audit: Array<Record<string, any>> }) {
  const [sql, setSql] = useState("select name from sqlite_master where type='table'");
  const [queryResult, setQueryResult] = useState<Record<string, any> | null>(null);
  const [status, setStatus] = useState("");

  async function runQuery() {
    const result = await adminFetch("/api/admin/db/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    setQueryResult(result);
  }

  async function backup() {
    const result = await adminFetch("/api/admin/db/backup", { method: "POST" });
    setStatus(`Backup written: ${result.path}`);
  }

  async function destructive(action: "paper.reset" | "session.reset" | "db.vacuum") {
    const intent = await adminFetch("/api/admin/confirm/intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const endpoint = action === "paper.reset" ? "/api/admin/paper/reset" : action === "session.reset" ? "/api/admin/session/reset" : "/api/admin/db/vacuum";
    const result = await adminFetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm_token: intent.confirm_token }),
    });
    setStatus(`${action} completed: ${JSON.stringify(result).slice(0, 120)}`);
  }

  return (
    <div className="admin-grid two">
      <section className="admin-card">
        <h2>Database</h2>
        <p className="admin-muted">{schema.path} · {formatBytes(schema.size_bytes || 0)}</p>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead><tr><th>Table</th><th>Rows</th><th>Export</th></tr></thead>
            <tbody>
              {(schema.tables || []).map((table: any) => (
                <tr key={table.table}>
                  <td>{table.table}</td>
                  <td>{table.rows}</td>
                  <td><a href={adminExportUrl(table.table)}>CSV</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="admin-actions">
          <button className="admin-button" onClick={backup}>Backup DB</button>
          <button className="admin-button danger" onClick={() => destructive("db.vacuum")}>Vacuum</button>
          <button className="admin-button danger" onClick={() => destructive("paper.reset")}>Reset Paper</button>
          <button className="admin-button danger" onClick={() => destructive("session.reset")}>Reset Session</button>
        </div>
        {status ? <p className="admin-muted">{status}</p> : null}
      </section>

      <section className="admin-card">
        <h2>Read-only SQL</h2>
        <textarea className="admin-textarea" value={sql} onChange={(event) => setSql(event.target.value)} />
        <button className="admin-button primary" onClick={runQuery}>Run SELECT</button>
        {queryResult ? (
          <pre className="admin-pre">{JSON.stringify(queryResult, null, 2)}</pre>
        ) : null}
      </section>

      <section className="admin-card wide">
        <h2>Audit Log</h2>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <tbody>
              {audit.map((item) => (
                <tr key={item.id}><td>{item.at}</td><td>{item.action}</td><td>{JSON.stringify(item.details)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
