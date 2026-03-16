"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Overview",
    eyebrow: "Overview",
    summary: "시장을 훑고 다음 작업 화면을 고르는 진입 허브",
  },
  {
    href: "/signals",
    label: "KR Signals",
    eyebrow: "Workspace",
    summary: "한국 종목 상세 신호와 차트를 읽는 분석 화면",
  },
  {
    href: "/bigtech",
    label: "US Big Tech",
    eyebrow: "Scanner",
    summary: "미국 빅테크 낙폭과 우선순위를 비교하는 스캐너",
  },
  {
    href: "/autonomous",
    label: "Autonomous",
    eyebrow: "Operations",
    summary: "KR·US 자동매매 운영 상태와 성과를 점검하는 콘솔",
  },
  {
    href: "/macro",
    label: "Macro",
    eyebrow: "Context",
    summary: "금리·달러·원자재 흐름으로 시장 컨텍스트를 맞추는 화면",
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
                <span style={{ color: "var(--foreground)" }}>{currentItem.label}</span>
                {" · "}
                {currentItem.summary}
              </p>
            </div>
          </div>
        </div>

        <div className="hidden flex-1 justify-center xl:flex">
          <nav
            className="flex items-center gap-2 rounded-2xl p-1"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
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

        <div className="flex flex-shrink-0 items-center gap-3">
          <div className="hidden text-right lg:block">
            <p className="text-xs" style={{ color: "var(--text-dim)" }}>
              시장 상황을 훑고 필요한 작업 화면으로 바로 이동합니다.
            </p>
          </div>
          <ThemeToggle />
        </div>
      </div>

      <div className="border-t px-4 py-3 xl:hidden" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
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
