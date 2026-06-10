"use client";

import { Activity, Search, Sunrise } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const MODES = [
  { id: "open", label: "Open Desk", path: "/open-desk", icon: Sunrise },
  { id: "live", label: "Live Desk", path: "/live-desk", icon: Activity },
  { id: "research", label: "Research", path: "/", icon: Search },
];

export function ModePills() {
  const pathname = usePathname() || "/";

  function isActive(path: string) {
    if (path === "/") return pathname === "/" || pathname.startsWith("/stock");
    return pathname.startsWith(path);
  }

  return (
    <nav className="mode-pills">
      {MODES.map((mode) => {
        const Icon = mode.icon;
        return (
          <Link key={mode.id} href={mode.path} className={isActive(mode.path) ? "active" : ""}>
            <Icon size={12} />
            <span>{mode.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
