"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Overview",
    eyebrow: "Overview",
    summary: "시장 요약과 진입 흐름",
  },
  {
    href: "/signals",
    label: "KR Signals",
    eyebrow: "Workspace",
    summary: "국내 종목 분석 보드",
  },
  {
    href: "/bigtech",
    label: "US Big Tech",
    eyebrow: "Scanner",
    summary: "빅테크 드로우다운 스캐너",
  },
  {
    href: "/autonomous",
    label: "Autonomous",
    eyebrow: "Operations",
    summary: "자동매매 운영 콘솔",
  },
  {
    href: "/macro",
    label: "Macro",
    eyebrow: "Context",
    summary: "거시 환경 보드",
  },
];

function isActivePath(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppNavigation() {
  const pathname = usePathname();
  const currentItem =
    NAV_ITEMS.find((item) => isActivePath(pathname, item.href)) ?? NAV_ITEMS[0];

  return (
    <header
      className="sticky top-0 z-50 border-b backdrop-blur-xl"
      style={{
        background: "var(--header-bg)",
        borderColor: "rgba(133, 158, 194, 0.12)",
      }}
    >
      <div className="mx-auto flex max-w-7xl items-start justify-between gap-4 px-4 py-4">
        <div className="min-w-0 flex-1">
          <Link href="/" className="block">
            <p
              className="text-[11px] font-semibold uppercase tracking-[0.24em]"
              style={{ color: "var(--accent)" }}
            >
              Signalight
            </p>
            <h1 className="truncate text-base font-semibold sm:text-lg" style={{ color: "var(--foreground)" }}>
              Market Operating Console
            </h1>
          </Link>

          <div className="mt-3 flex items-start gap-3">
            <span
              className="mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full"
              style={{
                background: "var(--accent)",
                boxShadow: "0 0 12px rgba(246,197,68,0.4)",
              }}
            />
            <div className="min-w-0">
              <p
                className="text-[10px] font-semibold uppercase tracking-[0.22em]"
                style={{ color: "var(--accent)" }}
              >
                {currentItem.eyebrow}
              </p>
              <p className="mt-1 text-xs leading-5 sm:text-sm" style={{ color: "var(--text-dim)" }}>
                {currentItem.summary}
              </p>
            </div>
          </div>
        </div>

        <div className="hidden flex-1 justify-center xl:flex">
          <nav
            className="flex items-center gap-2 rounded-2xl p-1"
            style={{
              background: "var(--chip-surface)",
              border: "1px solid var(--chip-border)",
            }}
          >
            {NAV_ITEMS.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-xl px-4 py-2 text-sm font-medium transition-colors"
                  style={{
                    background: active ? "var(--chip-active-surface)" : "transparent",
                    color: active ? "var(--accent)" : "var(--text-dim)",
                    border: active ? "1px solid var(--chip-active-border)" : "1px solid transparent",
                  }}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex flex-shrink-0 items-center gap-3">
          <ThemeToggle />
        </div>
      </div>

      <div className="border-t px-4 py-3 xl:hidden" style={{ borderColor: "var(--chip-border)" }}>
        <div className="mb-2 flex items-center justify-between gap-3">
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: "var(--text-dim)" }}
          >
            Quick Navigation
          </p>
          <p className="text-[10px]" style={{ color: "var(--text-dim)" }}>
            현재: {currentItem.label}
          </p>
        </div>
        <nav className="flex min-w-max items-center gap-2 overflow-x-auto pb-1">
          {NAV_ITEMS.map((item) => {
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-xl px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap"
                style={{
                  background: active ? "var(--chip-active-surface)" : "var(--chip-surface)",
                  color: active ? "var(--accent)" : "var(--text-dim)",
                  border: active
                    ? "1px solid var(--chip-active-border)"
                    : "1px solid var(--chip-border)",
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
