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
            {/* Price Info */}
            <PriceInfo
              name={selected.name}
              ticker={selected.ticker}
              ohlcv={data.ohlcv}
              signals={data.signals}
            />

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
