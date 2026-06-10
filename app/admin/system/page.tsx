import { AdminSystemPanel } from "@/components/AdminSystemPanel";
import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminSystemPage() {
  const schema = await safeAdminFetch<any>("/api/admin/db/schema", { tables: [] });
  const audit = await safeAdminFetch<any>("/api/admin/audit?limit=100", { items: [] });
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>System</h1></div></div>
      <AdminSystemPanel schema={schema} audit={audit.items || []} />
    </div>
  );
}
