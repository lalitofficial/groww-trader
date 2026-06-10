import type { Metadata } from "next";
import { ThemeRegistry } from "@/components/ThemeRegistry";
import { safeAdminFetch } from "@/lib/admin";
import "./globals.css";

export const metadata: Metadata = {
  title: "Groww AI Swing Dashboard",
  description: "Read-only Groww swing trading analysis dashboard.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const ui = await safeAdminFetch<{ cssText?: string }>("/api/admin/ui-config", {});
  return (
    <html lang="en">
      <head>{ui.cssText ? <style dangerouslySetInnerHTML={{ __html: ui.cssText }} /> : null}</head>
      <body>
        <ThemeRegistry>{children}</ThemeRegistry>
      </body>
    </html>
  );
}
