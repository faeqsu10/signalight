"use client";
import useSWR from "swr";
import { useState } from "react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface EquityPoint {
  date: string;
  total: number;
  invested: number;
  cash: number;
  positions: number;
}

interface DailyPnl {
  date: string;
  pnl: number;
  trades: number;
  wins: number;
  losses: number;
}

interface Trade {
  date: string;
  ticker: string;
  name: string;
  side: string;
  quantity: number;
  price: number;
  amount: number;
  status: string;
  reason: string | null;
  pnl_pct: number | null;
  pnl_amount: number | null;
}

interface MarketData {
  equity: EquityPoint[];
  daily_pnl: DailyPnl[];
  trades: Trade[];
  summary: {
    total_trades: number;
    win_rate: number;
    total_pnl: number;
    max_drawdown: number;
  };
  updated_at: string | null;
}

interface AutonomousData {
  kr: MarketData;
  us: MarketData;
}

function fmtAmount(amount: number, market: "kr" | "us") {
  if (market === "us") {
    return "$" + amount.toLocaleString("en-US", { minimumFractionDigits: 0 });
  }
  if (Math.abs(amount) >= 100_000_000) {
    return (amount / 100_000_000).toFixed(1) + "억원";
  }
  if (Math.abs(amount) >= 10_000) {
    return (amount / 10_000).toFixed(0) + "만원";
  }
  return amount.toLocaleString("ko-KR") + "원";
}

function fmtPnl(amount: number | null, pct: number | null, market: "kr" | "us") {
  if (amount === null && pct === null) return "-";
  const parts: string[] = [];
  if (pct !== null) {
    const sign = pct >= 0 ? "+" : "";
    parts.push(`${sign}${pct.toFixed(2)}%`);
  }
  if (amount !== null) {
    const sign = amount >= 0 ? "+" : "";
    parts.push(`${sign}${fmtAmount(amount, market)}`);
  }
  return parts.join(" / ");
}

function EquityChart({ equity, market }: { equity: EquityPoint[]; market: "kr" | "us" }) {
  if (equity.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-sm text-[var(--muted)]">
        데이터 없음
      </div>
    );
  }

  const values = equity.map((e) => e.total);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const first = values[0];
  const last = values[values.length - 1];
  const overallPct = first > 0 ? ((last - first) / first) * 100 : 0;
  const isPositive = overallPct >= 0;

  return (
    <div>
      <div className="flex items-end gap-0.5 h-40">
        {equity.map((e, i) => {
          const heightPct = ((e.total - minVal) / range) * 85 + 10;
          const isUp = i === 0 || e.total >= equity[i - 1].total;
          return (
            <div
              key={e.date}
              className="flex-1 flex flex-col justify-end group relative"
              style={{ height: "100%" }}
            >
              <div
                className={`rounded-sm transition-opacity group-hover:opacity-80 ${
                  isUp
                    ? "bg-red-400 dark:bg-red-500"
                    : "bg-blue-400 dark:bg-blue-500"
                }`}
                style={{ height: `${heightPct}%` }}
              />
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10 bg-zinc-800 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap shadow-lg">
                <div>{e.date}</div>
                <div>{fmtAmount(e.total, market)}</div>
                <div className="text-zinc-400">포지션 {e.positions}개</div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-[var(--muted)] mt-1">
        <span>{equity[0].date}</span>
        <span className={isPositive ? "text-red-500" : "text-blue-500"}>
          {isPositive ? "+" : ""}{overallPct.toFixed(2)}%
        </span>
        <span>{equity[equity.length - 1].date}</span>
      </div>
    </div>
  );
}

function SummaryCards({
  data,
  market,
}: {
  data: MarketData;
  market: "kr" | "us";
}) {
  const { summary, equity } = data;
  const latestEquity = equity.length > 0 ? equity[equity.length - 1].total : null;
  const initialEquity = equity.length > 0 ? equity[0].total : null;
  const returnPct =
    initialEquity && latestEquity && initialEquity > 0
      ? ((latestEquity - initialEquity) / initialEquity) * 100
      : null;

  const cards = [
    {
      label: "총 자산",
      value: latestEquity != null ? fmtAmount(latestEquity, market) : "-",
      color: "",
    },
    {
      label: "수익률",
      value: returnPct != null ? `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%` : "-",
      color: returnPct != null ? (returnPct >= 0 ? "text-red-500" : "text-blue-500") : "",
    },
    {
      label: "MDD",
      value: `-${summary.max_drawdown.toFixed(2)}%`,
      color: summary.max_drawdown > 10 ? "text-red-500" : "text-[var(--foreground)]",
    },
    {
      label: "거래 수",
      value: `${summary.total_trades}회`,
      color: "",
    },
    {
      label: "승률",
      value: summary.total_trades > 0 ? `${summary.win_rate}%` : "-",
      color: "",
    },
    {
      label: "총 손익",
      value: fmtAmount(summary.total_pnl, market),
      color: summary.total_pnl >= 0 ? "text-red-500" : "text-blue-500",
    },
  ];

  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-[var(--card)] rounded-lg p-3 border border-[var(--card-border)] text-center"
        >
          <div className={`text-sm font-bold truncate ${c.color}`}>{c.value}</div>
          <div className="text-[10px] text-[var(--muted)] mt-0.5">{c.label}</div>
        </div>
      ))}
    </div>
  );
}

function TradesTable({ trades, market }: { trades: Trade[]; market: "kr" | "us" }) {
  if (trades.length === 0) {
    return (
      <p className="text-sm text-[var(--muted)] text-center py-6">거래 내역 없음</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[520px]">
        <thead>
          <tr className="text-[var(--muted)] border-b border-[var(--card-border)]">
            <th className="text-left py-2 pr-3">날짜</th>
            <th className="text-left py-2 pr-3">종목</th>
            <th className="text-center py-2 pr-3">방향</th>
            <th className="text-right py-2 pr-3">수량</th>
            <th className="text-right py-2 pr-3">가격</th>
            <th className="text-right py-2 pr-3">손익</th>
            <th className="text-left py-2">사유</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const isBuy = t.side === "buy";
            const hasPnl = t.pnl_amount !== null || t.pnl_pct !== null;
            const pnlPositive =
              (t.pnl_amount !== null && t.pnl_amount > 0) ||
              (t.pnl_pct !== null && t.pnl_pct > 0);
            return (
              <tr
                key={i}
                className="border-b border-[var(--card-border)] hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors"
              >
                <td className="py-2 pr-3 text-[var(--muted)]">{t.date}</td>
                <td className="py-2 pr-3">
                  <span className="font-medium">{t.name || t.ticker}</span>
                  <span className="text-[var(--muted)] ml-1">({t.ticker})</span>
                </td>
                <td className="py-2 pr-3 text-center">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      isBuy
                        ? "bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400"
                        : "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400"
                    }`}
                  >
                    {isBuy ? "매수" : "매도"}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right">{t.quantity.toLocaleString()}</td>
                <td className="py-2 pr-3 text-right">
                  {market === "us"
                    ? "$" + t.price.toLocaleString("en-US", { minimumFractionDigits: 2 })
                    : t.price.toLocaleString("ko-KR") + "원"}
                </td>
                <td
                  className={`py-2 pr-3 text-right ${
                    !hasPnl
                      ? "text-[var(--muted)]"
                      : pnlPositive
                      ? "text-red-500"
                      : "text-blue-500"
                  }`}
                >
                  {fmtPnl(t.pnl_amount, t.pnl_pct, market)}
                </td>
                <td className="py-2 text-[var(--muted)] max-w-[160px] truncate">
                  {t.reason ?? "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DailyPnlBars({ daily_pnl }: { daily_pnl: DailyPnl[] }) {
  if (daily_pnl.length === 0) {
    return (
      <p className="text-sm text-[var(--muted)] text-center py-4">데이터 없음</p>
    );
  }

  const maxAbs = Math.max(...daily_pnl.map((d) => Math.abs(d.pnl)), 1);

  return (
    <div className="space-y-1.5">
      {daily_pnl.slice(-14).map((d) => {
        const barWidth = (Math.abs(d.pnl) / maxAbs) * 100;
        const isPos = d.pnl >= 0;
        return (
          <div key={d.date} className="flex items-center gap-2 text-xs">
            <span className="text-[var(--muted)] w-20 flex-shrink-0">{d.date}</span>
            <div className="flex-1 h-5 bg-gray-100 dark:bg-zinc-800 rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all ${
                  isPos ? "bg-red-400 dark:bg-red-500" : "bg-blue-400 dark:bg-blue-500"
                }`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
            <span
              className={`w-24 text-right flex-shrink-0 ${
                isPos ? "text-red-500" : d.pnl < 0 ? "text-blue-500" : "text-[var(--muted)]"
              }`}
            >
              {isPos ? "+" : ""}
              {d.pnl.toLocaleString()}원
            </span>
            <span className="text-[var(--muted)] w-14 text-right flex-shrink-0">
              {d.trades}건 ({d.wins}W/{d.losses}L)
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function AutonomousPage() {
  const { data, isLoading } = useSWR<AutonomousData>("/api/autonomous", fetcher, {
    refreshInterval: 60000,
  });
  const [market, setMarket] = useState<"kr" | "us">("kr");

  const marketData: MarketData | undefined = data?.[market];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] transition-colors">
      {/* Header */}
      <header className="border-b border-[var(--card-border)] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a
            href="/"
            className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors text-sm"
          >
            ← SIGNALIGHT
          </a>
          <h1 className="text-lg font-bold tracking-tight">자율매매 대시보드</h1>
        </div>
        {marketData?.updated_at && (
          <span className="text-xs text-[var(--muted)]">
            갱신: {marketData.updated_at.replace("T", " ")}
          </span>
        )}
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Market Tab Selector */}
        <div className="flex gap-2">
          <button
            onClick={() => setMarket("kr")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
              market === "kr"
                ? "bg-blue-500 border-blue-500 text-white"
                : "border-[var(--card-border)] text-[var(--muted)] hover:bg-gray-100 dark:hover:bg-zinc-800"
            }`}
          >
            🇰🇷 한국
          </button>
          <button
            onClick={() => setMarket("us")}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
              market === "us"
                ? "bg-blue-500 border-blue-500 text-white"
                : "border-[var(--card-border)] text-[var(--muted)] hover:bg-gray-100 dark:hover:bg-zinc-800"
            }`}
          >
            🇺🇸 미국
          </button>
        </div>

        {isLoading && (
          <div className="space-y-4 animate-pulse">
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 dark:bg-zinc-700 rounded-lg" />
              ))}
            </div>
            <div className="h-48 bg-gray-200 dark:bg-zinc-700 rounded-lg" />
            <div className="h-64 bg-gray-200 dark:bg-zinc-700 rounded-lg" />
          </div>
        )}

        {!isLoading && marketData && (
          <>
            {/* US placeholder notice */}
            {market === "us" && marketData.equity.length === 0 && (
              <div className="rounded-lg px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-300 dark:border-yellow-700 text-yellow-700 dark:text-yellow-400 text-sm">
                미국 자율매매 데이터는 준비 중입니다. DB market 컬럼 분리 후 활성화됩니다.
              </div>
            )}

            {/* Summary Cards */}
            <section>
              <h2 className="text-sm font-semibold text-[var(--muted)] mb-3">성과 요약</h2>
              <SummaryCards data={marketData} market={market} />
            </section>

            {/* Equity Curve */}
            <section className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)]">
              <h2 className="text-sm font-semibold text-[var(--muted)] mb-4">
                에퀴티 커브 ({marketData.equity.length}일)
              </h2>
              <EquityChart equity={marketData.equity} market={market} />
            </section>

            {/* Daily PnL */}
            <section className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)]">
              <h2 className="text-sm font-semibold text-[var(--muted)] mb-4">
                일별 손익 (최근 14일)
              </h2>
              <DailyPnlBars daily_pnl={marketData.daily_pnl} />
            </section>

            {/* Recent Trades */}
            <section className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)]">
              <h2 className="text-sm font-semibold text-[var(--muted)] mb-4">
                최근 거래 ({marketData.trades.length}건)
              </h2>
              <TradesTable trades={marketData.trades} market={market} />
            </section>
          </>
        )}

        <p className="text-[10px] text-[var(--muted)] text-center pb-4">
          본 대시보드는 자율매매 시스템의 모의(dry-run) 운영 결과입니다. 실제 투자 추천이 아닙니다.
        </p>
      </main>
    </div>
  );
}
