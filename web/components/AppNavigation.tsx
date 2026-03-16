"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/signals", label: "KR Signals" },
  { href: "/bigtech", label: "US Big Tech" },
  { href: "/autonomous", label: "Autonomous" },
  { href: "/macro", label: "Macro" },
];

export default function AppNavigation() {
  const pathname = usePathname();

  return (
    <header
      className="sticky top-0 z-50 border-b backdrop-blur-xl"
      style={{
        background: "var(--header-bg)",
        borderColor: "rgba(133, 158, 194, 0.12)",
      }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4">
        <div className="min-w-0">
          <Link href="/" className="block">
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Signalight
            </p>
            <h1 className="truncate text-lg font-semibold" style={{ color: "var(--foreground)" }}>
              Market Operating Console
            </h1>
          </Link>
        </div>

        <div className="hidden flex-1 justify-center lg:flex">
          <nav
            className="flex items-center gap-2 rounded-2xl p-1"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-xl px-4 py-2 text-sm font-medium transition-colors"
                  style={{
                    background: active ? "rgba(246,197,68,0.14)" : "transparent",
                    color: active ? "var(--accent)" : "var(--text-dim)",
                    border: active ? "1px solid rgba(246,197,68,0.22)" : "1px solid transparent",
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden text-right md:block">
            <p className="text-xs" style={{ color: "var(--text-dim)" }}>
              Overview는 요약, 각 메뉴는 작업 화면입니다.
            </p>
          </div>
          <ThemeToggle />
        </div>
      </div>

      <div className="overflow-x-auto px-4 pb-3 lg:hidden">
        <nav className="flex min-w-max items-center gap-2">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-xl px-3 py-2 text-sm font-medium transition-colors"
                style={{
                  background: active ? "rgba(246,197,68,0.14)" : "rgba(255,255,255,0.03)",
                  color: active ? "var(--accent)" : "var(--text-dim)",
                  border: active
                    ? "1px solid rgba(246,197,68,0.22)"
                    : "1px solid rgba(255,255,255,0.06)",
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
