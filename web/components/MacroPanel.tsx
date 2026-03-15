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
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
      {data.map((item) => {
        if (item.error) return null;
        const isUp = item.change_pct > 0;
        const isDown = item.change_pct < 0;
        const color = isUp ? "var(--buy)" : isDown ? "var(--sell)" : "var(--text-dim)";
        
        return (
          <div 
            key={item.key} 
            className="glass-card p-3 flex flex-col items-center justify-center text-center transition-transform hover:scale-[1.02]"
            style={{ border: `1px solid var(--glass-border)` }}
          >
            <span className="text-[10px] font-medium opacity-60 mb-1">{item.name}</span>
            <span className="text-sm font-bold mb-0.5">
              {item.key === "US10Y" ? item.price.toFixed(3) : item.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              <span className="text-[10px] ml-0.5 font-normal opacity-50">{item.unit === "%" ? "" : ""}</span>
            </span>
            <span className="text-[10px] font-bold" style={{ color }}>
              {isUp ? "▲" : isDown ? "▼" : ""} {Math.abs(item.change_pct).toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
