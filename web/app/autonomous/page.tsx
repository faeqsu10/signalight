"use client";
import useSWR from "swr";
import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import Tooltip from "@/components/Tooltip";
import SectionHeader from "@/components/SectionHeader";
import WorkspaceHero from "@/components/WorkspaceHero";

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

interface CurrentPosition {
  ticker: string;
  name: string;
  phase: number;
  entry_price: number;
  entry_date: string;
  stop_loss: number;
  target1: number;
  target2: number;
  highest_close: number;
  weight_pct: number;
  remaining_pct: number;
}

interface MarketData {
  equity: EquityPoint[];
  daily_pnl: DailyPnl[];
  trades: Trade[];
  current_positions: CurrentPosition[];
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
  us_meanrev: MarketData;
}

type MarketKey = "kr" | "us" | "us_meanrev";

function fmtAmount(amount: number, market: MarketKey) {
  if (market !== "kr") {
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

function fmtPnl(amount: number | null, pct: number | null, market: MarketKey) {
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

function EquityChart({ equity, market }: { equity: EquityPoint[]; market: MarketKey }) {
  if (equity.length === 0) {
    return (
      <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ color: "var(--text-dim)", fontSize: 14 }}>데이터 없음</span>
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
      {/* Overall return badge */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <span
          className={isPositive ? "badge-buy" : "badge-sell"}
          style={{ fontSize: 12, fontWeight: 700 }}
        >
          {isPositive ? "+" : ""}{overallPct.toFixed(2)}% 누적
        </span>
      </div>
      {/* Bars */}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 160, position: "relative" }}>
        {equity.map((e, i) => {
          const heightPct = ((e.total - minVal) / range) * 80 + 10;
          const isUp = i === 0 || e.total >= equity[i - 1].total;
          return (
            <div
              key={e.date}
              style={{ flex: 1, height: "100%", display: "flex", flexDirection: "column", justifyContent: "flex-end", position: "relative" }}
              className="group"
            >
              <div
                style={{
                  height: `${heightPct}%`,
                  background: isUp ? "var(--buy)" : "var(--sell)",
                  borderRadius: 3,
                  opacity: 0.85,
                  transition: "opacity 0.15s",
                  boxShadow: isUp
                    ? "0 0 4px rgba(0,212,170,0.3)"
                    : "0 0 4px rgba(255,71,87,0.3)",
                }}
                onMouseEnter={(ev) => {
                  (ev.currentTarget as HTMLElement).style.opacity = "1";
                }}
                onMouseLeave={(ev) => {
                  (ev.currentTarget as HTMLElement).style.opacity = "0.85";
                }}
              />
              {/* Tooltip */}
              <div
                style={{
                  position: "absolute",
                  bottom: "calc(100% + 6px)",
                  left: "50%",
                  transform: "translateX(-50%)",
                  background: "var(--dropdown-bg)",
                  border: "1px solid var(--glass-border)",
                  backdropFilter: "blur(12px)",
                  borderRadius: 8,
                  padding: "6px 10px",
                  whiteSpace: "nowrap",
                  fontSize: 11,
                  color: "var(--foreground)",
                  pointerEvents: "none",
                  display: "none",
                  zIndex: 20,
                  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
                }}
                className="group-hover:!block"
              >
                <div style={{ color: "var(--text-dim)", marginBottom: 2 }}>{e.date}</div>
                <div style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmtAmount(e.total, market)}</div>
                <div style={{ color: "var(--text-dim)" }}>포지션 {e.positions}개</div>
              </div>
            </div>
          );
        })}
      </div>
      {/* X axis labels */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{equity[0].date}</span>
        <span style={{ fontSize: 10, color: "var(--text-dim)" }}>{equity[equity.length - 1].date}</span>
      </div>
    </div>
  );
}

function SummaryCards({ data, market }: { data: MarketData; market: MarketKey }) {
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
      color: "var(--foreground)",
      size: "1.6rem",
    },
    {
      label: "수익률",
      value: returnPct != null ? `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(2)}%` : "-",
      color:
        returnPct != null
          ? returnPct >= 0
            ? "var(--buy)"
            : "var(--sell)"
          : "var(--foreground)",
      size: "1.4rem",
    },
    {
      label: "MDD",
      value: `-${summary.max_drawdown.toFixed(2)}%`,
      color: "var(--sell)",
      size: "1.4rem",
    },
    {
      label: "거래 수",
      value: `${summary.total_trades}회`,
      color: "var(--foreground)",
      size: "1.4rem",
    },
    {
      label: "승률",
      value: summary.total_trades > 0 ? `${summary.win_rate}%` : "-",
      color:
        summary.win_rate >= 55
          ? "var(--buy)"
          : summary.win_rate >= 45
          ? "var(--hold)"
          : "var(--sell)",
      size: "1.4rem",
    },
    {
      label: "총 손익",
      value: fmtAmount(summary.total_pnl, market),
      color: summary.total_pnl >= 0 ? "var(--buy)" : "var(--sell)",
      size: "1.4rem",
    },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 12,
      }}
    >
      {cards.map((c) => (
        <div
          key={c.label}
          className="glass-card"
          style={{ padding: "16px 12px", textAlign: "center" }}
        >
          <div
            style={{
              fontSize: c.size,
              fontWeight: 800,
              color: c.color,
              fontVariantNumeric: "tabular-nums",
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {c.value}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "var(--text-dim)",
              marginTop: 5,
              fontWeight: 500,
            }}
          >
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function DailyPnlBars({ daily_pnl, market }: { daily_pnl: DailyPnl[]; market: MarketKey }) {
  if (daily_pnl.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-dim)", fontSize: 13 }}>
        데이터 없음
      </div>
    );
  }

  const maxAbs = Math.max(...daily_pnl.map((d) => Math.abs(d.pnl)), 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {daily_pnl.slice(-14).map((d) => {
        const barWidth = (Math.abs(d.pnl) / maxAbs) * 100;
        const isPos = d.pnl >= 0;
        return (
          <div key={d.date} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12 }}>
            <span style={{ color: "var(--text-dim)", width: 80, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
              {d.date}
            </span>
            <div
              style={{
                flex: 1,
                height: 20,
                background: "rgba(255,255,255,0.04)",
                borderRadius: 4,
                overflow: "hidden",
                border: "1px solid var(--glass-border)",
              }}
            >
              <div
                style={{
                  width: `${barWidth}%`,
                  height: "100%",
                  background: isPos ? "var(--buy)" : "var(--sell)",
                  borderRadius: 3,
                  transition: "width 0.4s ease",
                  boxShadow: isPos
                    ? "0 0 8px rgba(0,212,170,0.4)"
                    : "0 0 8px rgba(255,71,87,0.4)",
                }}
              />
            </div>
            <span
              style={{
                width: 96,
                textAlign: "right",
                flexShrink: 0,
                fontVariantNumeric: "tabular-nums",
                fontWeight: 600,
                color: isPos ? "var(--buy)" : d.pnl < 0 ? "var(--sell)" : "var(--text-dim)",
              }}
            >
              {isPos ? "+" : ""}
              {market !== "kr"
                ? "$" + d.pnl.toLocaleString("en-US")
                : d.pnl.toLocaleString() + "원"}
            </span>
            <span style={{ color: "var(--text-dim)", width: 72, textAlign: "right", flexShrink: 0 }}>
              {d.trades}건 {d.wins}W/{d.losses}L
            </span>
          </div>
        );
      })}
    </div>
  );
}

function TradesTable({ trades, market }: { trades: Trade[]; market: MarketKey }) {
  if (trades.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "32px 0" }}>
        <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.4 }}>📋</div>
        <p style={{ color: "var(--text-dim)", fontSize: 13 }}>거래 내역 없음</p>
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="glass-table" style={{ minWidth: 560 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>날짜</th>
            <th style={{ textAlign: "left" }}>종목</th>
            <th style={{ textAlign: "center" }}>방향</th>
            <th style={{ textAlign: "right" }}>수량</th>
            <th style={{ textAlign: "right" }}>가격</th>
            <th style={{ textAlign: "right" }}>손익</th>
            <th style={{ textAlign: "left" }}>사유</th>
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
              <tr key={i}>
                <td style={{ color: "var(--text-dim)", fontVariantNumeric: "tabular-nums" }}>{t.date}</td>
                <td>
                  <span style={{ fontWeight: 600 }}>{t.name || t.ticker}</span>
                  <span style={{ color: "var(--text-dim)", marginLeft: 4, fontSize: 11 }}>
                    ({t.ticker})
                  </span>
                </td>
                <td style={{ textAlign: "center" }}>
                  <span className={isBuy ? "badge-buy" : "badge-sell"}>
                    {isBuy ? "매수" : "매도"}
                  </span>
                </td>
                <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {t.quantity.toLocaleString()}
                </td>
                <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {market !== "kr"
                    ? "$" + t.price.toLocaleString("en-US", { minimumFractionDigits: 2 })
                    : t.price.toLocaleString("ko-KR") + "원"}
                </td>
                <td
                  style={{
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: 600,
                    color: !hasPnl
                      ? "var(--text-dim)"
                      : pnlPositive
                      ? "var(--buy)"
                      : "var(--sell)",
                  }}
                >
                  {fmtPnl(t.pnl_amount, t.pnl_pct, market)}
                </td>
                <td
                  style={{
                    color: "var(--text-dim)",
                    maxWidth: 160,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
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

function CurrentPositionsPanel({ positions, market }: { positions: CurrentPosition[]; market: MarketKey }) {
  if (positions.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-dim)", fontSize: 13 }}>
        현재 보유 종목 없음
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
      {positions.map((pos) => (
        <div key={`${pos.ticker}-${pos.entry_date}`} className="glass-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
            <div>
              <div style={{ fontWeight: 700 }}>{pos.name}</div>
              <div style={{ color: "var(--text-dim)", fontSize: 12 }}>{pos.ticker}</div>
            </div>
            <span className="badge-hold">{pos.weight_pct.toFixed(1)}%</span>
          </div>
          <div style={{ marginTop: 12, display: "grid", gap: 6, fontSize: 12 }}>
            <div style={{ color: "var(--text-dim)" }}>진입가 {fmtAmount(pos.entry_price, market)}</div>
            <div style={{ color: "var(--text-dim)" }}>목표1 {fmtAmount(pos.target1, market)} / 손절 {fmtAmount(pos.stop_loss, market)}</div>
            <div style={{ color: "var(--text-dim)" }}>잔여 {pos.remaining_pct.toFixed(1)}% / 진입일 {pos.entry_date}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function AutonomousPage() {
  const { data, isLoading } = useSWR<AutonomousData>("/api/autonomous", fetcher, {
    refreshInterval: 60000,
  });
  const [market, setMarketState] = useState<MarketKey>(() => {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.replace("#", "");
      if (hash === "us") return "us";
      if (hash === "us_meanrev") return "us_meanrev";
    }
    return "kr";
  });

  const setMarket = (m: MarketKey) => {
    setMarketState(m);
    window.location.hash = m;
  };

  const marketData: MarketData | undefined = data?.[market];

  return (
    <div
      style={{
        minHeight: "100vh",
        color: "var(--foreground)",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
      }}
    >
      <WorkspaceHero
        eyebrow="Autonomous"
        title="AUTONOMOUS OPERATIONS"
        description="KR·US 운용 상태, 에퀴티, 일별 손익, 최근 체결을 한 흐름으로 점검합니다."
        badges={[
          market === "kr" ? "KR Runtime" : market === "us" ? "US Swing Runtime" : "US MeanRev Runtime",
          marketData?.updated_at
            ? `Last Sync ${marketData.updated_at.replace("T", " ").slice(0, 16)}`
            : "Waiting for Snapshot",
        ]}
        actions={[
          { href: "/", label: "Overview" },
          { href: "/signals", label: "KR Signals" },
        ]}
        aside={
          <div className="space-y-5">
            <div>
              <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
                Market Scope
              </p>
              <div
                className="mt-3 inline-flex rounded-full p-1"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid var(--glass-border)",
                }}
              >
                {([
                  ["kr", "KR 전략"],
                  ["us", "US 스윙"],
                  ["us_meanrev", "US 평균회귀"],
                ] as const).map(([m, label]) => (
                  <button
                    key={m}
                    onClick={() => setMarket(m)}
                    className="rounded-full px-4 py-2 text-sm font-semibold transition-colors"
                    style={{
                      background: market === m ? "var(--accent)" : "transparent",
                      color: market === m ? "#08111d" : "var(--text-dim)",
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
                  Console Utilities
                </p>
                <p className="mt-1 text-xs leading-5" style={{ color: "var(--text-dim)" }}>
                  테마 전환과 최신 스냅샷 기준 시각을 같이 둬서 운영 화면 성격을 유지합니다.
                </p>
              </div>
              <ThemeToggle />
            </div>
          </div>
        }
      />

      <main
        className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-8"
      >
        {/* Loading skeleton */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
              }}
            >
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="glass-card"
                  style={{
                    height: 76,
                    animation: "pulse 1.5s ease-in-out infinite",
                    opacity: 0.5,
                  }}
                />
              ))}
            </div>
            <div
              className="glass-card"
              style={{ height: 220, animation: "pulse 1.5s ease-in-out infinite", opacity: 0.5 }}
            />
            <div
              className="glass-card"
              style={{ height: 280, animation: "pulse 1.5s ease-in-out infinite", opacity: 0.5 }}
            />
          </div>
        )}

        {!isLoading && !marketData && (
          <div
            className="glass-card"
            style={{ textAlign: "center", padding: "60px 20px" }}
          >
            <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>📊</div>
            <p style={{ color: "var(--text-dim)", fontSize: 14 }}>
              데이터를 불러올 수 없습니다. API를 확인해주세요.
            </p>
          </div>
        )}

        {!isLoading && marketData && (
          <>
            {/* US placeholder notice */}
            {(market === "us" || market === "us_meanrev") && marketData.equity.length === 0 && (
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: 12,
                  background: "rgba(255,165,2,0.1)",
                  border: "1px solid rgba(255,165,2,0.3)",
                  color: "var(--hold)",
                  fontSize: 13,
                }}
              >
                미국 자율매매 데이터는 준비 중입니다. DB market 컬럼 분리 후 활성화됩니다.
              </div>
            )}

            {/* Summary Cards */}
            <section className="space-y-4">
              <SectionHeader
                eyebrow="Performance"
                title="Performance Board"
                description="총 자산, 누적 수익률, MDD, 승률을 한 번에 확인합니다."
              />
              <SummaryCards data={marketData} market={market} />
            </section>

            <section className="glass-card space-y-4" style={{ padding: 20 }}>
              <SectionHeader
                eyebrow="Holdings"
                title="Current Positions"
                description="현재 보유 종목, 진입가, 목표가와 잔여 비중을 확인합니다."
              />
              <CurrentPositionsPanel positions={marketData.current_positions} market={market} />
            </section>

            {/* Equity Curve */}
            <section className="glass-card space-y-4" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <SectionHeader
                  eyebrow="Equity"
                  title="Equity Curve"
                  description="총 자산 흐름과 변동 폭을 확인합니다."
                />
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-dim)" }}>
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">에퀴티 커브란?</p>
                        <p className="opacity-80">날마다 총 자산(현금 + 보유 종목 평가)이 어떻게 변했는지 보여주는 그래프입니다.</p>
                        <p className="mt-1 opacity-70">💡 우상향이면 수익, 우하향이면 손실 구간입니다. 꺾이는 지점이 매매 타이밍과 관련 있습니다.</p>
                      </div>
                    }
                  />
                  <span>
                    {marketData.equity.length}일 추적
                  </span>
                </div>
              </div>
              <EquityChart equity={marketData.equity} market={market} />
            </section>

            {/* Daily PnL */}
            <section className="glass-card space-y-4" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <SectionHeader
                  eyebrow="Daily PnL"
                  title="Daily PnL"
                  description="최근 손익 리듬을 빠르게 확인합니다."
                />
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-dim)" }}>
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">일별 손익이란?</p>
                        <p className="opacity-80">매일 실현된 손익을 막대그래프로 보여줍니다. 초록색은 이익, 빨간색은 손실입니다.</p>
                        <p className="mt-1 opacity-70">💡 매도가 완료되어야 손익이 확정됩니다. 보유 중인 종목의 미실현 손익은 포함되지 않습니다.</p>
                      </div>
                    }
                  />
                  <span>최근 14일</span>
                </div>
              </div>
              <DailyPnlBars daily_pnl={marketData.daily_pnl} market={market} />
            </section>

            {/* Recent Trades */}
            <section className="glass-card space-y-4" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <SectionHeader
                  eyebrow="Execution"
                  title="Recent Trades"
                  description="실행 로그와 최근 체결을 추적합니다."
                />
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-dim)" }}>
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">최근 거래란?</p>
                        <p className="opacity-80">자율매매 봇이 실행한 최근 매수·매도 내역입니다.</p>
                        <table className="w-full text-[10px] mt-2">
                          <tbody>
                            <tr><td style={{ color: "var(--buy)" }} className="pr-2">매수(BUY)</td><td>시그널 기반으로 종목을 산 기록</td></tr>
                            <tr><td style={{ color: "var(--sell)" }} className="pr-2">매도(SELL)</td><td>손절/익절/시그널로 종목을 판 기록</td></tr>
                            <tr><td className="pr-2">합류점수</td><td>여러 지표가 같은 방향을 가리킨 정도</td></tr>
                            <tr><td className="pr-2">simulated</td><td>모의투자 (실제 돈 아님)</td></tr>
                          </tbody>
                        </table>
                      </div>
                    }
                  />
                  <span>
                    {marketData.trades.length}건
                  </span>
                </div>
              </div>
              <TradesTable trades={marketData.trades} market={market} />
            </section>
          </>
        )}

        {/* Footer disclaimer */}
        <p
          style={{
            fontSize: 11,
            color: "var(--text-dim)",
            textAlign: "center",
            padding: "8px 0 16px",
            opacity: 0.6,
          }}
        >
          본 대시보드는 자율매매 시스템의 모의(dry-run) 운영 결과입니다. 실제 투자 추천이 아닙니다.
        </p>
      </main>
    </div>
  );
}
