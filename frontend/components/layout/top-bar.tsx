"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/positions", label: "Positions" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/triggers", label: "Triggers" },
  { href: "/flows", label: "Flows" },
];

export default function TopBar() {
  const pathname = usePathname();

  return (
    <header
      className="flex items-center h-12 px-4 border-b shrink-0"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 mr-6">
        <Activity size={20} style={{ color: "var(--aegis-brand)" }} />
        <span
          className="text-sm font-semibold tracking-wide"
          style={{ color: "var(--aegis-text-primary)" }}
        >
          AEGIS
        </span>
      </Link>

      {/* Nav Tabs */}
      <nav className="flex items-center gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className="px-3 py-1.5 text-xs rounded-md transition-colors duration-150"
              style={{
                color: isActive
                  ? "var(--aegis-text-primary)"
                  : "var(--aegis-text-secondary)",
                background: isActive
                  ? "var(--aegis-bg-elevated)"
                  : "transparent",
              }}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Pipeline Status */}
      <div className="flex items-center gap-2 mr-4">
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: "var(--aegis-text-tertiary)" }}
        />
        <span
          className="text-xs"
          style={{ color: "var(--aegis-text-secondary)" }}
        >
          Pipeline Idle
        </span>
      </div>

      {/* Time */}
      <span
        className="text-xs tabular-nums"
        style={{ color: "var(--aegis-text-tertiary)" }}
      >
        {new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          timeZoneName: "short",
        })}
      </span>
    </header>
  );
}
