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
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between mb-5">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: "var(--accent)" }}
          >
            Macro Pulse
          </p>
          <h3 className="mt-2 text-xl font-bold" style={{ color: "var(--foreground)" }}>
            글로벌 매크로 체크포인트
          </h3>
        </div>
        <p className="text-xs max-w-md" style={{ color: "var(--text-dim)" }}>
          원유, 금리, 환율, 달러 흐름을 한 번에 읽는 요약 구간입니다. 상승과 하락 방향이 같은
          톤으로 정리되어 전체 대시보드 흐름을 맞춰줍니다.
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
                minHeight: 112,
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.05)",
              }}
            >
              <div>
                <span className="text-[10px] font-medium opacity-60 mb-2 block">{item.name}</span>
                <span className="text-lg font-bold block" style={{ color: "var(--foreground)" }}>
                  {item.key === "US10Y"
                    ? item.price.toFixed(3)
                    : item.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <span className="text-[11px] font-bold mt-4" style={{ color }}>
                {isUp ? "▲" : isDown ? "▼" : "•"} {Math.abs(item.change_pct).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
