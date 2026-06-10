import { AdminUiEditor } from "@/components/AdminUiEditor";
import { safeAdminFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export default async function AdminUiPage() {
  const flags = await safeAdminFetch<any>("/api/admin/feature-flags", { flags: {} });
  const ui = await safeAdminFetch<any>("/api/admin/ui-config", { tokens: {}, layout: {} });
  return (
    <div className="admin-page">
      <div className="admin-head"><div><span>Admin</span><h1>UI</h1></div></div>
      <AdminUiEditor initialFlags={flags.flags || {}} initialUi={ui} />
    </div>
  );
}
