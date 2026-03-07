"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { WATCH_LIST } from "@/lib/constants";
import CandleChart from "@/components/CandleChart";
import RSIChart from "@/components/RSIChart";
import MACDChart from "@/components/MACDChart";
import SignalPanel from "@/components/SignalPanel";
import PriceInfo from "@/components/PriceInfo";
import Tooltip from "@/components/Tooltip";
import ThemeToggle from "@/components/ThemeToggle";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface ScanResult {
  ticker: string;
  name: string;
  price: number;
  reason: string;
}

function VIXGauge({ vix }: { vix: number }) {
  let bg = "bg-gray-200 dark:bg-gray-800";
  let text = "text-gray-600 dark:text-gray-400";
  let label = "보통";

  if (vix >= 30) {
    bg = "bg-red-100 dark:bg-red-900/60";
    text = "text-red-600 dark:text-red-400";
    label = "극단적 공포";
  } else if (vix >= 25) {
    bg = "bg-yellow-100 dark:bg-yellow-900/60";
    text = "text-yellow-600 dark:text-yellow-400";
    label = "공포";
  } else if (vix <= 12) {
    bg = "bg-green-100 dark:bg-green-900/60";
    text = "text-green-600 dark:text-green-400";
    label = "극단적 탐욕";
  }

  return (
    <div
      className={`${bg} rounded-lg px-4 py-2 border border-[var(--card-border)] flex flex-col items-center min-w-[120px] transition-colors`}
    >
      <span className="text-xs text-[var(--muted)] mb-1 flex items-center">
        VIX 공포지수
        <Tooltip
          content={
            <div>
              <p className="font-semibold mb-1">VIX (공포지수)</p>
              <p className="mb-2">시장 참여자들의 공포/탐욕 수준을 나타내는 지수입니다.</p>
              <table className="w-full text-[10px]">
                <tbody>
                  <tr><td className="text-red-500 pr-2">30+</td><td>극단적 공포 (역발상 매수 기회)</td></tr>
                  <tr><td className="text-yellow-500 pr-2">25~30</td><td>공포 구간 (주의 필요)</td></tr>
                  <tr><td className="text-[var(--muted)] pr-2">12~25</td><td>정상 범위</td></tr>
                  <tr><td className="text-green-500 pr-2">~12</td><td>극단적 탐욕 (과열 경고)</td></tr>
                </tbody>
              </table>
            </div>
          }
        />
      </span>
      <span className={`text-2xl font-bold ${text}`}>{vix.toFixed(1)}</span>
      <span className={`text-xs ${text}`}>{label}</span>
    </div>
  );
}

function ScannerCategory({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: ScanResult[];
  emptyText: string;
}) {
  return (
    <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
      <h4 className="text-sm font-semibold text-[var(--muted)] mb-3">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--muted)]">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.ticker} className="flex items-center justify-between text-sm">
              <div>
                <span className="font-medium">{item.name}</span>
                <span className="text-[var(--muted)] ml-1 text-xs">({item.ticker})</span>
              </div>
              <div className="text-right">
                <span className="text-xs text-[var(--muted)]">{item.reason}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Home() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const selected = WATCH_LIST[selectedIdx];

  const filteredList = useMemo(() => {
    if (!searchQuery.trim()) return WATCH_LIST.map((item, i) => ({ ...item, idx: i }));
    const q = searchQuery.toLowerCase();
    return WATCH_LIST
      .map((item, i) => ({ ...item, idx: i }))
      .filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          item.ticker.includes(q)
      );
  }, [searchQuery]);

  const { data, error, isLoading } = useSWR(
    `/api/stock/${selected.ticker}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: scannerData } = useSWR("/api/scanner", fetcher, {
    refreshInterval: 300000, // 5분 간격
  });

  const { data: backtestData } = useSWR(
    `/api/backtest/${selected.ticker}`,
    fetcher,
    { refreshInterval: 600000 } // 10분 간격
  );

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] transition-colors">
      {/* Header */}
      <header className="border-b border-[var(--card-border)] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight">SIGNALIGHT</h1>
          {data && !data.error && (
            <span className="text-xs text-[var(--muted)]">
              {new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} 기준
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="text"
              placeholder="종목 검색..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowSearch(true);
              }}
              onFocus={() => setShowSearch(true)}
              className="bg-[var(--select-bg)] border border-[var(--select-border)] rounded-lg px-3 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-gray-400 dark:focus:ring-gray-600 transition-colors w-36 sm:w-48"
            />
            {showSearch && filteredList.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--card)] border border-[var(--card-border)] rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
                {filteredList.map((item) => (
                  <button
                    key={item.ticker}
                    onClick={() => {
                      setSelectedIdx(item.idx);
                      setSearchQuery("");
                      setShowSearch(false);
                    }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex justify-between"
                  >
                    <span>{item.name}</span>
                    <span className="text-[var(--muted)] text-xs">{item.ticker}</span>
                  </button>
                ))}
              </div>
            )}
            {/* Backdrop to close search */}
            {showSearch && (
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowSearch(false)}
              />
            )}
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {isLoading && (
          <div className="text-center py-20 text-[var(--muted)]">
            데이터 로딩 중...
          </div>
        )}

        {error && (
          <div className="text-center py-20 text-red-500">
            데이터를 불러올 수 없습니다.
          </div>
        )}

        {data && !data.error && (
          <>
            {/* Signal Banner */}
            {(() => {
              const buySignals = (data.signals as { type: string }[]).filter((s) => s.type === "BUY").length;
              const sellSignals = (data.signals as { type: string }[]).filter((s) => s.type === "SELL").length;
              if (buySignals > 0 && buySignals >= sellSignals) {
                return (
                  <div className="w-full rounded-lg px-4 py-3 bg-red-500/15 border border-red-500/30 text-red-600 dark:text-red-400 text-center font-semibold text-sm">
                    매수 시그널 {buySignals}개 활성
                  </div>
                );
              }
              if (sellSignals > 0) {
                return (
                  <div className="w-full rounded-lg px-4 py-3 bg-blue-500/15 border border-blue-500/30 text-blue-600 dark:text-blue-400 text-center font-semibold text-sm">
                    매도 시그널 {sellSignals}개 활성
                  </div>
                );
              }
              return (
                <div className="w-full rounded-lg px-4 py-3 bg-gray-500/10 border border-gray-500/20 text-[var(--muted)] text-center font-semibold text-sm">
                  시그널 없음
                </div>
              );
            })()}

            {/* Price Info + VIX */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div className="flex-1">
                <PriceInfo
                  name={selected.name}
                  ticker={selected.ticker}
                  ohlcv={data.ohlcv}
                  signals={data.signals}
                />
              </div>
              {data.currentVIX != null && (
                <VIXGauge vix={data.currentVIX} />
              )}
            </div>

            {/* Candle Chart */}
            <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
              <h3 className="text-sm font-semibold text-[var(--muted)] mb-2 flex items-center">
                캔들차트
                <Tooltip
                  content={
                    <div>
                      <p className="font-semibold mb-1">캔들차트 + 이동평균선</p>
                      <table className="w-full text-[10px]">
                        <tbody>
                          <tr><td className="text-red-500 pr-2">빨간 봉</td><td>상승일 (시가 &lt; 종가)</td></tr>
                          <tr><td className="text-blue-500 pr-2">파란 봉</td><td>하락일 (시가 &gt; 종가)</td></tr>
                          <tr><td className="text-yellow-500 pr-2">빠른 선</td><td>10일 이동평균</td></tr>
                          <tr><td className="text-orange-400 pr-2">느린 선</td><td>50일 이동평균</td></tr>
                          <tr><td className="text-[var(--muted)] pr-2">교차</td><td>골든크로스(매수) / 데드크로스(매도)</td></tr>
                        </tbody>
                      </table>
                    </div>
                  }
                />
              </h3>
              <CandleChart
                ohlcv={data.ohlcv}
                shortMA={data.shortMA}
                longMA={data.longMA}
              />
            </div>

            {/* RSI + MACD */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
                <h3 className="text-sm font-semibold text-[var(--muted)] mb-2 flex items-center">
                  RSI ({data.currentRSI?.toFixed(1) ?? "-"})
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">RSI (상대강도지수)</p>
                        <p className="mb-2">주가가 과매수/과매도 상태인지 0~100으로 나타냅니다.</p>
                        <table className="w-full text-[10px]">
                          <tbody>
                            <tr><td className="text-blue-500 pr-2">70+</td><td>과매수 (너무 올랐음, 매도 고려)</td></tr>
                            <tr><td className="text-[var(--muted)] pr-2">30~70</td><td>중립 구간</td></tr>
                            <tr><td className="text-red-500 pr-2">~30</td><td>과매도 (너무 떨어짐, 매수 기회)</td></tr>
                          </tbody>
                        </table>
                      </div>
                    }
                  />
                </h3>
                <RSIChart ohlcv={data.ohlcv} rsiValues={data.rsiValues} />
              </div>
              <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
                <h3 className="text-sm font-semibold text-[var(--muted)] mb-2 flex items-center">
                  MACD
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">MACD (이동평균수렴확산)</p>
                        <p className="mb-2">단기/장기 추세의 힘 차이로 전환점을 포착합니다.</p>
                        <table className="w-full text-[10px]">
                          <tbody>
                            <tr><td className="text-red-500 pr-2">상향돌파</td><td>MACD가 시그널선 위로 → 매수</td></tr>
                            <tr><td className="text-blue-500 pr-2">하향돌파</td><td>MACD가 시그널선 아래로 → 매도</td></tr>
                            <tr><td className="text-[var(--muted)] pr-2">히스토그램</td><td>두 선의 차이 (막대그래프)</td></tr>
                          </tbody>
                        </table>
                      </div>
                    }
                  />
                </h3>
                <MACDChart
                  ohlcv={data.ohlcv}
                  macdLine={data.macdLine}
                  signalLine={data.signalLine}
                  histogram={data.histogram}
                />
              </div>
            </div>

            {/* Signal Panel */}
            <SignalPanel signals={data.signals} />
          </>
        )}

        {data?.error && (
          <div className="text-center py-20 text-red-500">{data.error}</div>
        )}

        {/* Backtest Summary */}
        {backtestData && !backtestData.error && (
          <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
            <h3 className="text-sm font-semibold text-[var(--muted)] mb-3">백테스트 (최근 1년)</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
              <div>
                <div className={`text-lg font-bold ${backtestData.totalReturnPct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                  {backtestData.totalReturnPct >= 0 ? "+" : ""}{backtestData.totalReturnPct}%
                </div>
                <div className="text-xs text-[var(--muted)]">총 수익률</div>
              </div>
              <div>
                <div className="text-lg font-bold text-blue-500">
                  -{backtestData.maxDrawdownPct}%
                </div>
                <div className="text-xs text-[var(--muted)]">MDD</div>
              </div>
              <div>
                <div className="text-lg font-bold">{backtestData.winRate}%</div>
                <div className="text-xs text-[var(--muted)]">승률</div>
              </div>
              <div>
                <div className="text-lg font-bold">{backtestData.totalTrades}회</div>
                <div className="text-xs text-[var(--muted)]">거래 수</div>
              </div>
            </div>
          </div>
        )}

        {/* Screener Section */}
        {scannerData && (
          <section className="space-y-4">
            <h2 className="text-lg font-bold">종목 스크리너</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ScannerCategory
                title="골든크로스"
                items={scannerData.goldenCross ?? []}
                emptyText="해당 종목 없음"
              />
              <ScannerCategory
                title="RSI 과매도"
                items={scannerData.rsiOversold ?? []}
                emptyText="해당 종목 없음"
              />
              <ScannerCategory
                title="거래량 급증"
                items={scannerData.volumeSurge ?? []}
                emptyText="해당 종목 없음"
              />
            </div>
            <p className="text-xs text-[var(--muted)] text-center mt-2">
              본 정보는 기술적 지표 기반 스크리닝 결과이며, 투자 추천이 아닙니다.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
