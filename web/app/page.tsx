"use client";

import { useState, useMemo, useEffect } from "react";
import useSWR from "swr";
import { ALL_WATCH_LIST } from "@/lib/constants";
import CandleChart from "@/components/CandleChart";
import RSIChart from "@/components/RSIChart";
import MACDChart from "@/components/MACDChart";
import SignalPanel from "@/components/SignalPanel";
import PriceInfo from "@/components/PriceInfo";
import Tooltip from "@/components/Tooltip";
import ThemeToggle from "@/components/ThemeToggle";
import RecoveryPanel from "@/components/RecoveryPanel";
import PositionCard from "@/components/PositionCard";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const FAVORITES_KEY = "signalight-favorites";

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

function SignalDot({ strength }: { strength: string | undefined }) {
  if (!strength) return null;
  if (strength === "strong_buy" || strength === "buy") {
    return <span className="inline-block w-2 h-2 rounded-full bg-red-500 ml-1 flex-shrink-0" />;
  }
  if (strength === "strong_sell" || strength === "sell") {
    return <span className="inline-block w-2 h-2 rounded-full bg-blue-500 ml-1 flex-shrink-0" />;
  }
  return <span className="inline-block w-2 h-2 rounded-full bg-gray-400 ml-1 flex-shrink-0" />;
}

export default function Home() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [period, setPeriod] = useState(120);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [signalCache, setSignalCache] = useState<Record<string, string>>({});
  const selected = ALL_WATCH_LIST[selectedIdx];

  // Load favorites from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(FAVORITES_KEY);
      if (stored) {
        setFavorites(JSON.parse(stored));
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  function toggleFavorite(ticker: string) {
    setFavorites((prev) => {
      const next = prev.includes(ticker)
        ? prev.filter((t) => t !== ticker)
        : [...prev, ticker];
      try {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  }

  const filteredList = useMemo(() => {
    const base = !searchQuery.trim()
      ? ALL_WATCH_LIST.map((item, i) => ({ ...item, idx: i }))
      : ALL_WATCH_LIST
          .map((item, i) => ({ ...item, idx: i }))
          .filter(
            (item) =>
              item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              item.ticker.toLowerCase().includes(searchQuery.toLowerCase())
          );
    // favorites first
    return [...base].sort((a, b) => {
      const aFav = favorites.includes(a.ticker) ? 0 : 1;
      const bFav = favorites.includes(b.ticker) ? 0 : 1;
      return aFav - bFav;
    });
  }, [searchQuery, favorites]);

  const { data, error, isLoading } = useSWR(
    `/api/stock/${selected.ticker}?period=${period}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  // Cache signal strength when data loads for the current stock
  useEffect(() => {
    if (!data || data.error) return;
    if (data.signalStrength) {
      setSignalCache((prev) => ({ ...prev, [selected.ticker]: data.signalStrength }));
      return;
    }
    // Derive from signals array if signalStrength field is absent
    if (Array.isArray(data.signals)) {
      const buyCount = (data.signals as { type: string }[]).filter((s) => s.type === "BUY").length;
      const sellCount = (data.signals as { type: string }[]).filter((s) => s.type === "SELL").length;
      let derived = "neutral";
      if (buyCount >= 2) derived = "strong_buy";
      else if (buyCount === 1) derived = "buy";
      else if (sellCount >= 2) derived = "strong_sell";
      else if (sellCount === 1) derived = "sell";
      setSignalCache((prev) => ({ ...prev, [selected.ticker]: derived }));
    }
  }, [data, selected.ticker]);

  const { data: scannerData } = useSWR("/api/scanner", fetcher, {
    refreshInterval: 300000, // 5분 간격
  });

  const { data: backtestData } = useSWR(
    `/api/backtest/${selected.ticker}`,
    fetcher,
    { refreshInterval: 600000 } // 10분 간격
  );

  const { data: recoveryData, isLoading: recoveryLoading } = useSWR(
    `/api/stock/${selected.ticker}/recovery?period=${period}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const isFavorite = favorites.includes(selected.ticker);

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
          {/* Star button for current stock */}
          <button
            onClick={() => toggleFavorite(selected.ticker)}
            title={isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
            className="text-lg leading-none text-yellow-400 hover:text-yellow-300 transition-colors focus:outline-none"
            aria-label={isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
          >
            {isFavorite ? "★" : "☆"}
          </button>
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
                {filteredList.map((item) => {
                  const isFav = favorites.includes(item.ticker);
                  const strength = signalCache[item.ticker];
                  return (
                    <button
                      key={item.ticker}
                      onClick={() => {
                        setSelectedIdx(item.idx);
                        setSearchQuery("");
                        setShowSearch(false);
                      }}
                      className="w-full text-left px-3 py-2.5 min-h-[44px] text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center justify-between"
                    >
                      <span className="flex items-center gap-1">
                        {isFav && (
                          <span className="text-yellow-400 text-xs leading-none">★</span>
                        )}
                        <span className={`text-[10px] px-1 py-0.5 rounded ${item.market === "KR" ? "bg-blue-500/20 text-blue-400" : "bg-green-500/20 text-green-400"}`}>
                          {item.market}
                        </span>
                        {item.name}
                        <SignalDot strength={strength} />
                      </span>
                      <span className="text-[var(--muted)] text-xs flex-shrink-0 ml-2">{item.ticker}</span>
                    </button>
                  );
                })}
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
                  market={selected.market}
                />
              </div>
              {data.currentVIX != null && (
                <VIXGauge vix={data.currentVIX} />
              )}
            </div>

            {/* Candle Chart */}
            <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
              <div className="flex gap-2 mb-2">
                {[
                  { label: "1M", days: 30 },
                  { label: "3M", days: 90 },
                  { label: "6M", days: 180 },
                  { label: "1Y", days: 365 },
                ].map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setPeriod(p.days)}
                    className={`px-3 py-1 text-xs rounded-lg border transition-colors ${
                      period === p.days
                        ? "bg-zinc-600 border-zinc-500 text-white"
                        : "bg-zinc-800/50 border-zinc-700 text-zinc-400 hover:border-zinc-500"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
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
                bollingerUpper={data.bollingerUpper}
                bollingerLower={data.bollingerLower}
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

            {/* Recovery Analysis + Position Card */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <RecoveryPanel
                recovery={recoveryData?.recovery ?? null}
                loading={recoveryLoading}
              />
              <PositionCard
                ticker={selected.ticker}
                currentPrice={data.ohlcv?.[data.ohlcv.length - 1]?.close ?? 0}
                market={selected.market}
              />
            </div>
          </>
        )}

        {data?.error && (
          <div className="text-center py-20 text-red-500">{data.error}</div>
        )}

        {/* Backtest Summary */}
        {backtestData && !backtestData.error && (
          <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
            <h3 className="text-sm font-semibold text-[var(--muted)] mb-3">백테스트 (최근 1년)</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4 text-center">
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
