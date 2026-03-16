"use client";

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface MacroItem {
  key: string;
  name: string;
  ticker: string;
  price: number;
  change_pct: number;
  unit: string;
  error?: boolean;
}

export default function MacroPanel() {
  const { data, error, isLoading } = useSWR<MacroItem[]>("/api/macro", fetcher, {
    refreshInterval: 600000, // 10분
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 animate-pulse">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-20 bg-glass rounded-xl border border-glass-border"></div>
        ))}
      </div>
    );
  }

  if (error || !data) return null;

  return (
    <section
      className="glass-card"
      style={{
        borderRadius: 20,
        padding: 20,
        background:
          "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
      }}
    >
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: "var(--accent)" }}
          >
            Live Dashboard
          </p>
          <h3 className="mt-2 text-xl font-bold" style={{ color: "var(--foreground)" }}>
            글로벌 매크로 체크포인트
          </h3>
        </div>
        <p className="text-xs max-w-md" style={{ color: "var(--text-dim)" }}>
          원유, 금리, 환율, 달러 흐름을 같은 카드 규칙 위에서 압축해 보여주는 실시간 체크 영역입니다.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        {data.map((item) => {
          if (item.error) return null;
          const isUp = item.change_pct > 0;
          const isDown = item.change_pct < 0;
          const color = isUp ? "var(--buy)" : isDown ? "var(--sell)" : "var(--text-dim)";

          return (
            <div
              key={item.key}
              className="flex flex-col justify-between rounded-2xl px-4 py-4 transition-transform hover:-translate-y-0.5"
              style={{
                minHeight: 128,
                background: "linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.015) 100%)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: "var(--text-dim)" }}>
                    {item.ticker}
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                    style={{
                      color,
                      background: isUp
                        ? "rgba(0,212,170,0.08)"
                        : isDown
                        ? "rgba(255,71,87,0.08)"
                        : "rgba(255,255,255,0.04)",
                      border: `1px solid ${
                        isUp
                          ? "rgba(0,212,170,0.18)"
                          : isDown
                          ? "rgba(255,71,87,0.18)"
                          : "rgba(255,255,255,0.06)"
                      }`,
                    }}
                  >
                    {isUp ? "UP" : isDown ? "DOWN" : "FLAT"}
                  </span>
                </div>
                <span className="block text-[11px] font-medium" style={{ color: "var(--text-dim)" }}>
                  {item.name}
                </span>
                <span className="text-lg font-bold block" style={{ color: "var(--foreground)" }}>
                  {item.key === "US10Y"
                    ? item.price.toFixed(3)
                    : item.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  {item.unit && (
                    <span className="ml-1 text-xs font-medium" style={{ color: "var(--text-dim)" }}>
                      {item.unit}
                    </span>
                  )}
                </span>
              </div>
              <span className="mt-4 text-[11px] font-bold" style={{ color }}>
                {isUp ? "▲" : isDown ? "▼" : "•"} {Math.abs(item.change_pct).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
