"use client";

import Link from "next/link";
import { useState, useMemo, useEffect, useRef } from "react";
import useSWR from "swr";
import { ALL_WATCH_LIST } from "@/lib/constants";
import CandleChart from "@/components/CandleChart";
import RSIChart from "@/components/RSIChart";
import MACDChart from "@/components/MACDChart";
import SignalPanel from "@/components/SignalPanel";
import PriceInfo from "@/components/PriceInfo";
import Tooltip from "@/components/Tooltip";
import RecoveryPanel from "@/components/RecoveryPanel";
import PositionCard from "@/components/PositionCard";
import DisclosurePanel from "@/components/DisclosurePanel";
import LLMAnalysisPanel from "@/components/LLMAnalysisPanel";
import SectionHeader from "@/components/SectionHeader";
import SignalStatusBanner from "@/components/SignalStatusBanner";
import SignalsWorkspaceHeader from "@/components/SignalsWorkspaceHeader";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const FAVORITES_KEY = "signalight-favorites";

interface ScanResult {
  ticker: string;
  name: string;
  price: number;
  reason: string;
}

function VIXGauge({ vix }: { vix: number }) {
  let glowColor = "var(--buy)";
  let textColor = "var(--buy)";
  let label = "보통";
  let borderColor = "rgba(0,212,170,0.3)";

  if (vix >= 30) {
    glowColor = "var(--sell)";
    textColor = "var(--sell)";
    borderColor = "rgba(255,71,87,0.3)";
    label = "극단적 공포";
  } else if (vix >= 25) {
    glowColor = "var(--hold)";
    textColor = "var(--hold)";
    borderColor = "rgba(255,165,2,0.3)";
    label = "공포";
  } else if (vix <= 12) {
    glowColor = "var(--buy)";
    textColor = "var(--buy)";
    borderColor = "rgba(0,212,170,0.3)";
    label = "극단적 탐욕";
  }

  return (
    <div
      className="glass-card flex flex-col items-center min-w-[130px] px-5 py-3"
      style={{
        border: `1px solid ${borderColor}`,
        boxShadow: `0 0 20px ${glowColor}22`,
      }}
    >
      <span className="text-xs mb-1 flex items-center gap-1" style={{ color: "var(--text-dim)" }}>
        VIX 공포지수
        <Tooltip
          content={
            <div>
              <p className="font-semibold mb-1">VIX (공포지수)</p>
              <p className="mb-2">시장 참여자들의 공포/탐욕 수준을 나타내는 지수입니다.</p>
              <table className="w-full text-[10px]">
                <tbody>
                  <tr><td style={{ color: "var(--sell)" }} className="pr-2">30+</td><td>극단적 공포 (역발상 매수 기회)</td></tr>
                  <tr><td style={{ color: "var(--hold)" }} className="pr-2">25~30</td><td>공포 구간 (주의 필요)</td></tr>
                  <tr><td style={{ color: "var(--text-dim)" }} className="pr-2">12~25</td><td>정상 범위</td></tr>
                  <tr><td style={{ color: "var(--buy)" }} className="pr-2">~12</td><td>극단적 탐욕 (과열 경고)</td></tr>
                </tbody>
              </table>
            </div>
          }
        />
      </span>
      <span className="text-2xl font-bold" style={{ color: textColor }}>{vix.toFixed(1)}</span>
      <span className="text-xs mt-0.5" style={{ color: textColor }}>{label}</span>
    </div>
  );
}

function ScannerCategory({
  title,
  items,
  emptyText,
  tooltip,
}: {
  title: string;
  items: ScanResult[];
  emptyText: string;
  tooltip?: React.ReactNode;
}) {
  return (
    <div
      className="rounded-2xl p-4"
      style={{
        background: "rgba(255,255,255,0.018)",
        border: "1px solid rgba(255,255,255,0.05)",
      }}
    >
      <h4 className="text-sm font-semibold mb-3 flex items-center" style={{ color: "var(--accent)" }}>
        {title}
        {tooltip && <Tooltip content={tooltip} />}
      </h4>
      {items.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--text-dim)" }}>{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.ticker} className="flex items-center justify-between text-sm">
              <div>
                <span className="font-medium" style={{ color: "var(--foreground)" }}>{item.name}</span>
                <span className="ml-1 text-xs" style={{ color: "var(--text-dim)" }}>({item.ticker})</span>
              </div>
              <div className="text-right">
                <span
                  className="text-[10px] px-2 py-0.5 rounded-full"
                  style={{
                    background: "rgba(246,197,68,0.12)",
                    color: "var(--accent)",
                    border: "1px solid rgba(246,197,68,0.18)",
                  }}
                >
                  {item.reason}
                </span>
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
  const [period, setPeriod] = useState(120);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [signalCache, setSignalCache] = useState<Record<string, string>>({});
  const [compareIdx, setCompareIdx] = useState<number | null>(null);
  const [showComparePicker, setShowComparePicker] = useState(false);
  const [scannerMarket, setScannerMarket] = useState<"KR" | "US">("KR");
  const selected = ALL_WATCH_LIST[selectedIdx];
  const compareStock = compareIdx !== null ? ALL_WATCH_LIST[compareIdx] : null;

  const [notifPermission, setNotifPermission] = useState<NotificationPermission>("default");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(Notification.permission);
    }
  }, []);

  async function requestNotifPermission() {
    if (!("Notification" in window)) return;
    const perm = await Notification.requestPermission();
    setNotifPermission(perm);
  }

  const prevSignalsRef = useRef<string>("");

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
    return [...base].sort((a, b) => {
      const aFav = favorites.includes(a.ticker) ? 0 : 1;
      const bFav = favorites.includes(b.ticker) ? 0 : 1;
      return aFav - bFav;
    });
  }, [searchQuery, favorites]);

  const compareCandidates = useMemo(
    () => filteredList.filter((item) => item.idx !== selectedIdx),
    [filteredList, selectedIdx]
  );

  const { data, error, isLoading, mutate } = useSWR(
    `/api/stock/${selected.ticker}?period=${period}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  useEffect(() => {
    if (!data || data.error) return;
    if (data.signalStrength) {
      setSignalCache((prev) => ({ ...prev, [selected.ticker]: data.signalStrength }));
      return;
    }
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

  useEffect(() => {
    if (!data || data.error || notifPermission !== "granted") return;

    const buyCount = (data.signals as { type: string }[]).filter(s => s.type === "BUY").length;
    const sellCount = (data.signals as { type: string }[]).filter(s => s.type === "SELL").length;
    const currentKey = `${selected.ticker}-buy${buyCount}-sell${sellCount}`;

    if (prevSignalsRef.current && prevSignalsRef.current !== currentKey) {
      if (buyCount > 0) {
        new Notification(`${selected.name} 매수 시그널`, {
          body: `매수 시그널 ${buyCount}개 활성`,
          icon: "/favicon.ico",
        });
      } else if (sellCount > 0) {
        new Notification(`${selected.name} 매도 시그널`, {
          body: `매도 시그널 ${sellCount}개 활성`,
          icon: "/favicon.ico",
        });
      }
    }
    prevSignalsRef.current = currentKey;
  }, [data, selected.ticker, selected.name, notifPermission]);

  const { data: scannerData } = useSWR(`/api/scanner?market=${scannerMarket}`, fetcher, {
    refreshInterval: 300000,
  });

  const { data: backtestData } = useSWR(
    `/api/backtest/${selected.ticker}`,
    fetcher,
    { refreshInterval: 600000 }
  );

  const { data: recoveryData, isLoading: recoveryLoading } = useSWR(
    `/api/stock/${selected.ticker}/recovery?period=${period}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: disclosureData, isLoading: disclosureLoading } = useSWR(
    selected.market === "KR" ? `/api/stock/${selected.ticker}/disclosure` : null,
    fetcher,
    { refreshInterval: 300000 }
  );

  const { data: compareData } = useSWR(
    compareStock ? `/api/stock/${compareStock.ticker}?period=${period}` : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  const isFavorite = favorites.includes(selected.ticker);

  return (
    <div className="min-h-screen" style={{ color: "var(--foreground)" }}>
      <SignalsWorkspaceHeader
        selectedName={selected.name}
        selectedTicker={selected.ticker}
        hasData={Boolean(data && !data.error)}
        isFavorite={isFavorite}
        compareActive={compareIdx !== null}
        favorites={favorites}
        compareCandidates={compareCandidates}
        searchResults={filteredList}
        signalCache={signalCache}
        searchQuery={searchQuery}
        showSearch={showSearch}
        showComparePicker={showComparePicker}
        mounted={mounted}
        notifPermission={notifPermission}
        onToggleFavorite={() => toggleFavorite(selected.ticker)}
        onToggleCompare={() => {
          if (compareIdx !== null) {
            setCompareIdx(null);
            setShowComparePicker(false);
          } else {
            setShowComparePicker((v) => !v);
          }
        }}
        onCloseCompare={() => setShowComparePicker(false)}
        onSelectCompare={(idx) => {
          setCompareIdx(idx);
          setShowComparePicker(false);
        }}
        onSearchQueryChange={(value) => {
          setSearchQuery(value);
          setShowSearch(true);
        }}
        onSearchOpen={() => setShowSearch(true)}
        onSearchClose={() => setShowSearch(false)}
        onSelectTicker={(idx) => {
          setSelectedIdx(idx);
          setSearchQuery("");
          setShowSearch(false);
        }}
        onRequestNotifications={requestNotifPermission}
      />

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {isLoading && (
          <div className="space-y-6 animate-pulse">
            <div
              className="h-12 rounded-xl"
              style={{ background: "var(--glass)", border: "1px solid var(--glass-border)" }}
            />
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 rounded" style={{ background: "var(--glass)" }} />
                <div className="h-10 w-56 rounded" style={{ background: "var(--glass)" }} />
              </div>
              <div className="h-20 w-32 rounded-xl" style={{ background: "var(--glass)" }} />
            </div>
            <div className="glass-card p-4">
              <div className="h-4 w-24 rounded mb-3" style={{ background: "var(--glass)" }} />
              <div className="h-[300px] rounded-lg" style={{ background: "var(--glass)" }} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[0, 1].map(i => (
                <div key={i} className="glass-card p-4">
                  <div className="h-4 w-16 rounded mb-3" style={{ background: "var(--glass)" }} />
                  <div className="h-[150px] rounded" style={{ background: "var(--glass)" }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="text-center py-20">
            <p className="mb-4" style={{ color: "var(--sell)" }}>데이터를 불러올 수 없습니다.</p>
            <button
              onClick={() => mutate()}
              className="px-5 py-2 rounded-xl text-sm font-medium transition-colors"
              style={{ background: "var(--accent)", color: "#fff" }}
            >
              재시도
            </button>
          </div>
        )}

        {data && !data.error && (
          <>
            <section className="space-y-4">
              <SectionHeader
                eyebrow="Selected Asset"
                title={`${selected.name} 상세 분석`}
                description="선택한 종목의 신호, AI 해석, 차트, 모멘텀 지표를 한 흐름으로 읽는 구간입니다."
              />

            <SignalStatusBanner signals={data.signals as { type: string }[]} />

            {/* Gemini AI Analysis Panel */}
            <LLMAnalysisPanel 
              analysis={data.llmAnalysis} 
              sentiment={data.sentiment}
              loading={isLoading} 
            />
            </section>

            {/* Comparison Panel */}
            {compareStock && compareData && !compareData.error && (() => {
              const selClose = data.ohlcv?.[data.ohlcv.length - 1]?.close ?? 0;
              const selPrev = data.ohlcv?.[data.ohlcv.length - 2]?.close ?? selClose;
              const selChange = selPrev ? ((selClose - selPrev) / selPrev) * 100 : 0;
              const selBuy = (data.signals as { type: string }[]).filter((s) => s.type === "BUY").length;
              const selSell = (data.signals as { type: string }[]).filter((s) => s.type === "SELL").length;
              const selStrength = selBuy >= 2 ? "강력매수" : selBuy === 1 ? "매수" : selSell >= 2 ? "강력매도" : selSell === 1 ? "매도" : "중립";
              const selStrengthColor = selBuy > 0 ? "var(--buy)" : selSell > 0 ? "var(--sell)" : "var(--text-dim)";

              const cmpClose = compareData.ohlcv?.[compareData.ohlcv.length - 1]?.close ?? 0;
              const cmpPrev = compareData.ohlcv?.[compareData.ohlcv.length - 2]?.close ?? cmpClose;
              const cmpChange = cmpPrev ? ((cmpClose - cmpPrev) / cmpPrev) * 100 : 0;
              const cmpBuy = (compareData.signals as { type: string }[]).filter((s) => s.type === "BUY").length;
              const cmpSell = (compareData.signals as { type: string }[]).filter((s) => s.type === "SELL").length;
              const cmpStrength = cmpBuy >= 2 ? "강력매수" : cmpBuy === 1 ? "매수" : cmpSell >= 2 ? "강력매도" : cmpSell === 1 ? "매도" : "중립";
              const cmpStrengthColor = cmpBuy > 0 ? "var(--buy)" : cmpSell > 0 ? "var(--sell)" : "var(--text-dim)";

              const fmtPrice = (price: number, market: string) =>
                market === "KR"
                  ? price.toLocaleString("ko-KR") + "원"
                  : "$" + price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

              return (
                <div className="glass-card p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold" style={{ color: "var(--text-dim)" }}>
                      종목 비교: {selected.name} vs {compareStock.name}
                    </h3>
                    <button
                      onClick={() => setCompareIdx(null)}
                      className="text-xs transition-colors"
                      style={{ color: "var(--text-dim)" }}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--foreground)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--text-dim)")}
                    >
                      닫기
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-center text-sm">
                    <div className="space-y-1">
                      <div className="font-semibold truncate">{selected.name}</div>
                      <div className="text-xs" style={{ color: "var(--text-dim)" }}>{selected.ticker}</div>
                      <div className="text-2xl font-bold">{fmtPrice(selClose, selected.market)}</div>
                      <div className="text-sm font-medium" style={{ color: selChange >= 0 ? "var(--buy)" : "var(--sell)" }}>
                        {selChange >= 0 ? "+" : ""}{selChange.toFixed(2)}%
                      </div>
                      <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                        매수 {selBuy} / 매도 {selSell}
                      </div>
                      <span className="text-xs font-semibold" style={{ color: selStrengthColor }}>{selStrength}</span>
                    </div>
                    <div className="space-y-1">
                      <div className="font-semibold truncate">{compareStock.name}</div>
                      <div className="text-xs" style={{ color: "var(--text-dim)" }}>{compareStock.ticker}</div>
                      <div className="text-2xl font-bold">{fmtPrice(cmpClose, compareStock.market)}</div>
                      <div className="text-sm font-medium" style={{ color: cmpChange >= 0 ? "var(--buy)" : "var(--sell)" }}>
                        {cmpChange >= 0 ? "+" : ""}{cmpChange.toFixed(2)}%
                      </div>
                      <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                        매수 {cmpBuy} / 매도 {cmpSell}
                      </div>
                      <span className="text-xs font-semibold" style={{ color: cmpStrengthColor }}>{cmpStrength}</span>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Price Info + VIX */}
            <section className="space-y-4">
              <SectionHeader
                eyebrow="Market Read"
                title="가격 흐름과 변동성"
                description="현재 가격, 공포지수, 캔들 흐름을 먼저 보고 이후의 기술 지표로 내려가는 구조로 정리했습니다."
              />
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
            <div
              className="glass-card p-5"
              style={{
                borderRadius: 20,
                background:
                  "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
              }}
            >
              <div className="flex gap-2 mb-3">
                {[
                  { label: "1M", days: 30 },
                  { label: "3M", days: 90 },
                  { label: "6M", days: 180 },
                  { label: "1Y", days: 365 },
                ].map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setPeriod(p.days)}
                    className="px-3 py-1 text-xs rounded-lg transition-colors"
                    style={{
                      background: period === p.days ? "var(--accent)" : "var(--glass)",
                      border: `1px solid ${period === p.days ? "var(--accent)" : "var(--glass-border)"}`,
                      color: period === p.days ? "#fff" : "var(--text-dim)",
                    }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <h3 className="text-sm font-semibold mb-2 flex items-center" style={{ color: "var(--text-dim)" }}>
                캔들차트
                <Tooltip
                  content={
                    <div>
                      <p className="font-semibold mb-1">캔들차트 + 이동평균선</p>
                      <p className="mb-2 opacity-80">하루의 시가·고가·저가·종가를 봉 하나로 보여줍니다. 이동평균선은 최근 N일 평균 가격을 이은 선입니다.</p>
                      <table className="w-full text-[10px]">
                        <tbody>
                          <tr><td style={{ color: "var(--buy)" }} className="pr-2">초록 봉</td><td>상승일 — 종가가 시가보다 높음</td></tr>
                          <tr><td style={{ color: "var(--sell)" }} className="pr-2">빨간 봉</td><td>하락일 — 종가가 시가보다 낮음</td></tr>
                          <tr><td className="text-yellow-500 pr-2">노란 선</td><td>10일 이동평균 (단기 추세)</td></tr>
                          <tr><td className="text-purple-400 pr-2">보라 선</td><td>50일 이동평균 (장기 추세)</td></tr>
                          <tr><td style={{ color: "var(--text-dim)" }} className="pr-2">점선</td><td>볼린저밴드 상·하단 (변동성 범위)</td></tr>
                        </tbody>
                      </table>
                      <p className="mt-2 opacity-70">💡 단기선이 장기선을 위로 뚫으면 골든크로스(매수 신호), 아래로 내려가면 데드크로스(매도 신호)라고 합니다.</p>
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
                signalHistory={data.signalHistory ?? []}
              />
            </div>
            </section>

            {/* RSI + MACD */}
            <section className="space-y-4">
              <SectionHeader
                eyebrow="Momentum"
                title="기술 지표와 신호 해석"
                description="RSI와 MACD는 서로 다른 속도로 추세 변화를 잡습니다. 아래에서 시그널 카드와 함께 읽도록 묶었습니다."
              />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                className="glass-card p-5"
                style={{
                  borderRadius: 20,
                  background:
                    "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
                }}
              >
                <h3 className="text-sm font-semibold mb-2 flex items-center" style={{ color: "var(--text-dim)" }}>
                  RSI ({data.currentRSI?.toFixed(1) ?? "-"})
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">RSI (상대강도지수)</p>
                        <p className="mb-2 opacity-80">최근 상승/하락의 힘을 0~100으로 나타내는 지표입니다. 낮을수록 많이 떨어진 상태, 높을수록 많이 오른 상태입니다.</p>
                        <table className="w-full text-[10px]">
                          <tbody>
                            <tr><td style={{ color: "var(--sell)" }} className="pr-2">70 이상</td><td>과매수 — 너무 올라서 조정 가능성</td></tr>
                            <tr><td style={{ color: "var(--hold)" }} className="pr-2">40~60</td><td>중립 — 뚜렷한 방향 없음</td></tr>
                            <tr><td style={{ color: "var(--buy)" }} className="pr-2">30 이하</td><td>과매도 — 많이 떨어져서 반등 가능성</td></tr>
                          </tbody>
                        </table>
                        <p className="mt-2 opacity-70">💡 RSI가 30 아래에서 다시 올라오기 시작하면 반등 신호로 봅니다. 차트의 빨간 점선이 70, 파란 점선이 30 기준선입니다.</p>
                      </div>
                    }
                  />
                </h3>
                <RSIChart ohlcv={data.ohlcv} rsiValues={data.rsiValues} />
              </div>
              <div
                className="glass-card p-5"
                style={{
                  borderRadius: 20,
                  background:
                    "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
                }}
              >
                <h3 className="text-sm font-semibold mb-2 flex items-center" style={{ color: "var(--text-dim)" }}>
                  MACD
                  <Tooltip
                    content={
                      <div>
                        <p className="font-semibold mb-1">MACD (이동평균수렴확산)</p>
                        <p className="mb-2 opacity-80">단기(12일)와 장기(26일) 이동평균의 차이를 보여주는 지표입니다. 추세 전환점을 포착하는 데 사용합니다.</p>
                        <table className="w-full text-[10px]">
                          <tbody>
                            <tr><td style={{ color: "#22d3ee" }} className="pr-2">MACD선</td><td>단기-장기 평균 차이 (파란선)</td></tr>
                            <tr><td style={{ color: "#f97316" }} className="pr-2">시그널선</td><td>MACD의 9일 평균 (주황선)</td></tr>
                            <tr><td style={{ color: "var(--text-dim)" }} className="pr-2">히스토그램</td><td>두 선의 차이를 막대로 표시</td></tr>
                          </tbody>
                        </table>
                        <p className="mt-2 opacity-70">💡 MACD선이 시그널선을 위로 돌파하면 골든크로스(매수), 아래로 내려가면 데드크로스(매도)입니다. 히스토그램이 커지면 추세가 강해지는 것입니다.</p>
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
            </section>

            {/* Warnings */}
            {data.warnings && (data.warnings as string[]).length > 0 && (
              <div
                className="rounded-xl px-4 py-3 text-xs space-y-0.5"
                style={{
                  background: "rgba(255,165,2,0.08)",
                  border: "1px solid rgba(255,165,2,0.25)",
                  color: "var(--hold)",
                }}
              >
                {(data.warnings as string[]).map((w: string, i: number) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            )}

            {/* Recovery Analysis + Position Card */}
            <section className="space-y-4">
              <SectionHeader
                eyebrow="Execution"
                title="회복 가능성과 포지션 판단"
                description="실제 대응에 가까운 체크리스트와 포지션 카드, 공시 영역을 마지막 액션 구간으로 모았습니다."
              />
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

            {/* Disclosure Panel */}
            {selected.market === "KR" && (
              <DisclosurePanel
                disclosures={disclosureData?.disclosures ?? null}
                loading={disclosureLoading}
              />
            )}
            </section>
          </>
        )}

        {data?.error && (
          <div className="text-center py-20">
            <p className="mb-4" style={{ color: "var(--sell)" }}>{data.error}</p>
            <button
              onClick={() => mutate()}
              className="px-5 py-2 rounded-xl text-sm font-medium transition-colors"
              style={{ background: "var(--accent)", color: "#fff" }}
            >
              재시도
            </button>
          </div>
        )}

        {/* Backtest Summary */}
        {backtestData && !backtestData.error && (
          <section
            className="glass-card p-5"
            style={{
              borderRadius: 20,
              background:
                "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
            }}
          >
            <h3 className="text-sm font-semibold mb-4 flex items-center" style={{ color: "var(--text-dim)" }}>
              백테스트 (최근 1년)
              <Tooltip
                content={
                  <div>
                    <p className="font-semibold mb-1">백테스트란?</p>
                    <p className="opacity-80">과거 1년간 데이터에 현재 전략을 적용했을 때 어떤 성과가 나왔을지 시뮬레이션한 결과입니다.</p>
                    <table className="w-full text-[10px] mt-2">
                      <tbody>
                        <tr><td className="pr-2" style={{ color: "var(--buy)" }}>총 수익률</td><td>전체 기간 누적 수익률</td></tr>
                        <tr><td className="pr-2" style={{ color: "var(--sell)" }}>MDD</td><td>최고점 대비 최대 하락폭 (위험도)</td></tr>
                        <tr><td className="pr-2">승률</td><td>이익 거래 비율 (높을수록 안정적)</td></tr>
                        <tr><td className="pr-2">거래 수</td><td>매수·매도 시그널 발생 횟수</td></tr>
                      </tbody>
                    </table>
                    <p className="mt-2 opacity-70">💡 과거 성과가 미래 수익을 보장하지 않습니다. MDD가 낮고 승률이 높을수록 안정적인 전략입니다.</p>
                  </div>
                }
              />
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4 text-center">
              <div>
                <div
                  className="text-xl font-bold"
                  style={{ color: backtestData.totalReturnPct >= 0 ? "var(--buy)" : "var(--sell)" }}
                >
                  {backtestData.totalReturnPct >= 0 ? "+" : ""}{backtestData.totalReturnPct}%
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>총 수익률</div>
              </div>
              <div>
                <div className="text-xl font-bold" style={{ color: "var(--sell)" }}>
                  -{backtestData.maxDrawdownPct}%
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>MDD</div>
              </div>
              <div>
                <div className="text-xl font-bold" style={{ color: "var(--foreground)" }}>
                  {backtestData.winRate}%
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>승률</div>
              </div>
              <div>
                <div className="text-xl font-bold" style={{ color: "var(--foreground)" }}>
                  {backtestData.totalTrades}회
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>거래 수</div>
              </div>
            </div>
          </section>
        )}

        {/* Screener Section */}
        {scannerData && (
          <section
            className="glass-card space-y-4"
            style={{
              borderRadius: 20,
              padding: 20,
              background:
                "linear-gradient(180deg, rgba(14,24,39,0.94) 0%, rgba(10,18,31,0.98) 100%)",
            }}
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-[0.24em]"
                  style={{ color: "var(--accent)" }}
                >
                  Screeners
                </p>
                <h2 className="mt-2 text-2xl font-bold" style={{ color: "var(--foreground)" }}>
                  기술적 조건으로 빠르게 걸러보기
                </h2>
                <p className="mt-2 text-sm max-w-2xl leading-6" style={{ color: "var(--text-dim)" }}>
                  골든크로스, RSI 과매도, 거래량 급증 조건을 같은 시각 언어로 정리했습니다.
                  홈 전체와 톤을 맞추면서도 액션성은 유지하는 구간입니다.
                </p>
              </div>
              <div className="flex p-1 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}>
                <button
                  onClick={() => setScannerMarket("KR")}
                  className={`px-3 py-1 text-xs rounded-lg transition-all duration-200 ${
                    scannerMarket === "KR" 
                      ? "bg-accent text-white shadow-lg" 
                      : "text-dim hover:text-foreground"
                  }`}
                  style={{
                    backgroundColor: scannerMarket === "KR" ? "var(--accent)" : "transparent",
                    color: scannerMarket === "KR" ? "#fff" : "var(--text-dim)"
                  }}
                >
                  KOREA
                </button>
                <button
                  onClick={() => setScannerMarket("US")}
                  className={`px-3 py-1 text-xs rounded-lg transition-all duration-200 ${
                    scannerMarket === "US" 
                      ? "bg-buy text-white shadow-lg" 
                      : "text-dim hover:text-foreground"
                  }`}
                  style={{
                    backgroundColor: scannerMarket === "US" ? "var(--buy)" : "transparent",
                    color: scannerMarket === "US" ? "#fff" : "var(--text-dim)"
                  }}
                >
                  USA
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ScannerCategory
                title="골든크로스"
                items={scannerData.goldenCross ?? []}
                emptyText="해당 종목 없음"
                tooltip={
                  <div>
                    <p className="font-semibold mb-1">골든크로스란?</p>
                    <p className="opacity-80">단기 이동평균선(10일)이 장기 이동평균선(50일)을 아래에서 위로 돌파하는 것입니다.</p>
                    <p className="mt-1 opacity-70">💡 상승 추세 전환의 대표적 신호로, 많은 투자자가 매수 타이밍으로 활용합니다.</p>
                  </div>
                }
              />
              <ScannerCategory
                title="RSI 과매도"
                items={scannerData.rsiOversold ?? []}
                emptyText="해당 종목 없음"
                tooltip={
                  <div>
                    <p className="font-semibold mb-1">RSI 과매도란?</p>
                    <p className="opacity-80">RSI가 30 이하로 내려간 종목입니다. 최근 하락이 과도해서 반등 가능성이 있다고 봅니다.</p>
                    <p className="mt-1 opacity-70">💡 단, RSI가 낮다고 반드시 오르는 것은 아닙니다. 다른 지표와 함께 봐야 신뢰도가 높습니다.</p>
                  </div>
                }
              />
              <ScannerCategory
                title="거래량 급증"
                items={scannerData.volumeSurge ?? []}
                emptyText="해당 종목 없음"
                tooltip={
                  <div>
                    <p className="font-semibold mb-1">거래량 급증이란?</p>
                    <p className="opacity-80">최근 거래량이 20일 평균 대비 2배 이상 늘어난 종목입니다. 큰 관심이 몰리고 있다는 뜻입니다.</p>
                    <p className="mt-1 opacity-70">💡 거래량이 많아야 가격 움직임에 신뢰도가 생깁니다. 호재/악재 뉴스와 함께 확인하세요.</p>
                  </div>
                }
              />
            </div>
            <p className="text-xs text-center" style={{ color: "var(--text-dim)" }}>
              본 정보는 기술적 지표 기반 스크리닝 결과이며, 투자 추천이 아닙니다.
            </p>
          </section>
        )}

        {/* Disclaimer */}
        <div
          className="glass-card p-4 text-xs text-center"
          style={{ color: "var(--text-dim)" }}
        >
          본 서비스는 참고용 기술적 분석 정보만을 제공하며, 투자 판단 및 그에 따른 책임은 이용자 본인에게 있습니다.
        </div>
      </main>
    </div>
  );
}
