"use client";

import { useState } from "react";
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

export default function Home() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const selected = WATCH_LIST[selectedIdx];

  const { data, error, isLoading } = useSWR(
    `/api/stock/${selected.ticker}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] transition-colors">
      {/* Header */}
      <header className="border-b border-[var(--card-border)] px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">SIGNALIGHT</h1>
        <div className="flex items-center gap-3">
          <select
            value={selectedIdx}
            onChange={(e) => setSelectedIdx(Number(e.target.value))}
            className="bg-[var(--select-bg)] border border-[var(--select-border)] rounded-lg px-3 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-gray-400 dark:focus:ring-gray-600 transition-colors"
          >
            {WATCH_LIST.map((item, i) => (
              <option key={item.ticker} value={i}>
                {item.name}
              </option>
            ))}
          </select>
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
                          <tr><td className="text-yellow-500 pr-2">빠른 선</td><td>5일 이동평균</td></tr>
                          <tr><td className="text-orange-400 pr-2">느린 선</td><td>20일 이동평균</td></tr>
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
      </main>
    </div>
  );
}
