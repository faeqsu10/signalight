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
                  background: "rgba(10,14,26,0.95)",
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

function SummaryCards({ data, market }: { data: MarketData; market: "kr" | "us" }) {
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

function DailyPnlBars({ daily_pnl, market }: { daily_pnl: DailyPnl[]; market: "kr" | "us" }) {
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
              {market === "us"
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

function TradesTable({ trades, market }: { trades: Trade[]; market: "kr" | "us" }) {
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
                  {market === "us"
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

export default function AutonomousPage() {
  const { data, isLoading } = useSWR<AutonomousData>("/api/autonomous", fetcher, {
    refreshInterval: 60000,
  });
  const [market, setMarket] = useState<"kr" | "us">("kr");

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
      {/* Header */}
      <header
        className="glass-card"
        style={{
          margin: "16px 16px 0",
          borderRadius: 16,
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        {/* Left: Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <a
            href="/"
            style={{
              fontSize: 18,
              fontWeight: 900,
              letterSpacing: "-0.04em",
              color: "var(--foreground)",
              textDecoration: "none",
              background: "linear-gradient(135deg, #6c5ce7, #00d4aa)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            SIGNALIGHT
          </a>
          <span className="badge-accent" style={{ fontSize: 11 }}>자율매매</span>
        </div>

        {/* Center: Market tab selector */}
        <div
          style={{
            display: "flex",
            gap: 6,
            background: "rgba(255,255,255,0.04)",
            border: "1px solid var(--glass-border)",
            borderRadius: 999,
            padding: "4px",
          }}
        >
          {(["kr", "us"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMarket(m)}
              style={{
                padding: "6px 18px",
                borderRadius: 999,
                border: "none",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                transition: "all 0.2s ease",
                background:
                  market === m
                    ? "var(--accent)"
                    : "transparent",
                color: market === m ? "#fff" : "var(--text-dim)",
                boxShadow:
                  market === m
                    ? "0 0 16px rgba(108,92,231,0.5)"
                    : "none",
              }}
            >
              {m === "kr" ? "🇰🇷 KR" : "🇺🇸 US"}
            </button>
          ))}
        </div>

        {/* Right: Timestamp */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {marketData?.updated_at && (
            <>
              <span
                className="pulse-ring"
                style={{ width: 8, height: 8, flexShrink: 0 }}
              />
              <span style={{ fontSize: 11, color: "var(--text-dim)", fontVariantNumeric: "tabular-nums" }}>
                {marketData.updated_at.replace("T", " ").slice(0, 16)}
              </span>
            </>
          )}
        </div>
      </header>

      <main
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
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
            {market === "us" && marketData.equity.length === 0 && (
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
            <section>
              <div style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  성과 요약
                </span>
                <hr className="glass-divider" style={{ flex: 1 }} />
              </div>
              <SummaryCards data={marketData} market={market} />
            </section>

            {/* Equity Curve */}
            <section className="glass-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  에퀴티 커브
                </span>
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  {marketData.equity.length}일 추적
                </span>
              </div>
              <EquityChart equity={marketData.equity} market={market} />
            </section>

            {/* Daily PnL */}
            <section className="glass-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  일별 손익
                </span>
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>최근 14일</span>
              </div>
              <DailyPnlBars daily_pnl={marketData.daily_pnl} market={market} />
            </section>

            {/* Recent Trades */}
            <section className="glass-card" style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  최근 거래
                </span>
                <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                  {marketData.trades.length}건
                </span>
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
