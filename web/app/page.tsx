"use client";

import { useState } from "react";
import useSWR from "swr";
import { WATCH_LIST } from "@/lib/constants";
import CandleChart from "@/components/CandleChart";
import RSIChart from "@/components/RSIChart";
import MACDChart from "@/components/MACDChart";
import SignalPanel from "@/components/SignalPanel";
import PriceInfo from "@/components/PriceInfo";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function VIXGauge({ vix }: { vix: number }) {
  let bg = "bg-gray-800";
  let text = "text-gray-400";
  let label = "보통";

  if (vix >= 30) {
    bg = "bg-red-900/60";
    text = "text-red-400";
    label = "극단적 공포";
  } else if (vix >= 25) {
    bg = "bg-yellow-900/60";
    text = "text-yellow-400";
    label = "공포";
  } else if (vix <= 12) {
    bg = "bg-green-900/60";
    text = "text-green-400";
    label = "극단적 탐욕";
  }

  return (
    <div
      className={`${bg} rounded-lg px-4 py-2 border border-gray-700 flex flex-col items-center min-w-[120px]`}
    >
      <span className="text-xs text-gray-500 mb-1">VIX 공포지수</span>
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
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">SIGNALIGHT</h1>
        <select
          value={selectedIdx}
          onChange={(e) => setSelectedIdx(Number(e.target.value))}
          className="bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-gray-600"
        >
          {WATCH_LIST.map((item, i) => (
            <option key={item.ticker} value={i}>
              {item.name}
            </option>
          ))}
        </select>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {isLoading && (
          <div className="text-center py-20 text-gray-500">
            데이터 로딩 중...
          </div>
        )}

        {error && (
          <div className="text-center py-20 text-red-400">
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
            <div className="bg-[#141414] rounded-lg p-4 border border-gray-800">
              <CandleChart
                ohlcv={data.ohlcv}
                shortMA={data.shortMA}
                longMA={data.longMA}
              />
            </div>

            {/* RSI + MACD */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-[#141414] rounded-lg p-4 border border-gray-800">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">
                  RSI ({data.currentRSI?.toFixed(1) ?? "-"})
                </h3>
                <RSIChart ohlcv={data.ohlcv} rsiValues={data.rsiValues} />
              </div>
              <div className="bg-[#141414] rounded-lg p-4 border border-gray-800">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">
                  MACD
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
          <div className="text-center py-20 text-red-400">{data.error}</div>
        )}
      </main>
    </div>
  );
}
