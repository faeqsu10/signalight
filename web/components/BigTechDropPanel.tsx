'use client';

import React, { useEffect, useState } from 'react';

type StockData = {
  symbol: string;
  name: string;
  currentPrice: number;
  high52w: number;
  highDate: string;
  dropPct: number;
};

export default function BigTechDropPanel() {
  const [data, setData] = useState<StockData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/watchlist/bigtech')
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        console.error(e);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 shadow-lg border border-gray-800 animate-pulse">
        <h3 className="text-xl font-bold mb-4 text-white">💰 빅테크 할인율 스캐너 (분할 매수 타점)</h3>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="h-12 bg-gray-800 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-6 shadow-lg border border-gray-800">
      <h3 className="text-xl font-bold mb-6 text-white flex items-center gap-2">
        <span>💰</span> 빅테크 할인율 스캐너 (분할 매수 타점)
      </h3>
      
      <div className="space-y-6">
        {data.map((stock) => {
          // 최대 50% 하락을 기준으로 게이지를 채움
          const gaugePercent = Math.min(100, (stock.dropPct / 50) * 100);
          
          // 하락률에 따른 색상 변화 (많이 떨어질수록 초록색/매수기회 느낌)
          let colorClass = "bg-red-500";
          if (stock.dropPct >= 30) colorClass = "bg-emerald-500";
          else if (stock.dropPct >= 20) colorClass = "bg-yellow-400";
          else if (stock.dropPct >= 10) colorClass = "bg-orange-400";

          return (
            <div key={stock.symbol} className="flex flex-col gap-2">
              <div className="flex justify-between items-end">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-gray-200">{stock.name}</span>
                  <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">{stock.symbol}</span>
                </div>
                <div className="text-right">
                  <span className="text-xl font-bold text-white">-{stock.dropPct.toFixed(2)}%</span>
                </div>
              </div>
              
              {/* Gauge Bar */}
              <div className="relative h-4 bg-gray-800 rounded-full overflow-hidden">
                <div 
                  className={`absolute top-0 left-0 h-full ${colorClass} transition-all duration-1000 ease-out`}
                  style={{ width: `${gaugePercent}%` }}
                ></div>
                {/* 눈금 마커 (-10, -20, -30, -40) */}
                {[20, 40, 60, 80].map(marker => (
                  <div 
                    key={marker}
                    className="absolute top-0 h-full border-l border-gray-900/50"
                    style={{ left: `${marker}%` }}
                  ></div>
                ))}
              </div>
              
              <div className="flex justify-between text-xs text-gray-400">
                <span>최고가: ${stock.high52w.toFixed(2)} ({stock.highDate})</span>
                <span>현재가: ${stock.currentPrice.toFixed(2)}</span>
              </div>
            </div>
          );
        })}
      </div>
      
      <div className="mt-6 pt-4 border-t border-gray-800 text-xs text-gray-500">
        * 게이지가 길어지고 초록색에 가까울수록 고점 대비 많이 하락한 상태(바겐세일)를 의미합니다. <br/>
        * 눈금은 각각 -10%, -20%, -30%, -40% 하락 지점을 나타냅니다.
      </div>
    </div>
  );
}