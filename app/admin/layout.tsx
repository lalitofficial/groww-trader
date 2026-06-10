import Link from "next/link";
import { AdminStatusStrip } from "@/components/AdminStatusStrip";

export const dynamic = "force-dynamic";

const NAV = [
  ["/admin", "Overview"],
  ["/admin/services", "Services"],
  ["/admin/ai", "AI"],
  ["/admin/metrics", "Metrics"],
  ["/admin/logs", "Logs"],
  ["/admin/data", "Data"],
  ["/admin/ui", "UI"],
  ["/admin/system", "System"],
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <Link href="/" className="admin-brand">Groww Admin</Link>
        <nav>
          {NAV.map(([href, label]) => (
            <Link key={href} href={href}>{label}</Link>
          ))}
        </nav>
      </aside>
      <section className="admin-main">
        {children}
      </section>
      <AdminStatusStrip />
    </main>
  );
}
