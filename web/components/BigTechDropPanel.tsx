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
        if (Array.isArray(d)) {
          setData(d);
        } else {
          console.error('Invalid data received:', d);
          setData([]);
        }
        setLoading(false);
      })
      .catch(e => {
        console.error(e);
        setData([]);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div
        className="glass-card animate-pulse overflow-hidden"
        style={{ borderRadius: 20 }}
      >
        <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--foreground)' }}>
          💰 빅테크 할인율 스캐너 (분할 매수 타점)
        </h3>
        <div className="space-y-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div
              key={i}
              className="h-12 rounded-2xl"
              style={{ background: 'rgba(255,255,255,0.04)' }}
            ></div>
          ))}
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return null; // 데이터가 없거나 에러 시 패널을 숨김
  }

  return (
    <section
      className="glass-card overflow-hidden"
      style={{
        borderRadius: 20,
        padding: 20,
        background:
          'linear-gradient(180deg, rgba(17,27,43,0.96) 0%, rgba(11,18,31,0.98) 100%)',
      }}
    >
      <div
        className="mb-6 rounded-2xl px-5 py-4"
        style={{
          background:
            'linear-gradient(135deg, rgba(255,207,51,0.08), rgba(255,142,60,0.02) 45%, transparent 80%)',
          border: '1px solid rgba(255,255,255,0.04)',
        }}
      >
        <h3 className="text-xl font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
          <span>💰</span> 빅테크 할인율 스캐너 (분할 매수 타점)
        </h3>
        <p className="mt-2 text-sm leading-6" style={{ color: 'var(--text-dim)' }}>
          52주 최고가 대비 할인 폭을 한눈에 보여주는 스캐너입니다. 길고 밝은 게이지일수록
          분할 매수 후보로 볼 수 있는 구간에 더 가까워집니다.
        </p>
      </div>
      
      <div className="space-y-6">
        {data.map((stock) => {
          const gaugePercent = Math.min(100, (stock.dropPct / 50) * 100);
          let fill = 'linear-gradient(90deg, #ff8d3a 0%, #ff9e42 100%)';
          if (stock.dropPct >= 30) fill = 'linear-gradient(90deg, #ffd84d 0%, #ffbe1b 100%)';
          else if (stock.dropPct >= 20) fill = 'linear-gradient(90deg, #ffd25c 0%, #ff9d41 100%)';
          else if (stock.dropPct >= 10) fill = 'linear-gradient(90deg, #ffb35b 0%, #ff8d3a 100%)';

          return (
            <article
              key={stock.symbol}
              className="flex flex-col gap-2 rounded-2xl px-4 py-3"
              style={{
                background: 'rgba(255,255,255,0.015)',
                border: '1px solid rgba(255,255,255,0.04)',
              }}
            >
              <div className="flex justify-between items-end gap-3">
                <div className="flex items-center gap-2">
                  <span className="font-bold" style={{ color: 'var(--foreground)' }}>{stock.name}</span>
                  <span
                    className="text-[11px] px-2 py-1 rounded-md font-medium"
                    style={{
                      color: 'rgba(255,255,255,0.38)',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.05)',
                    }}
                  >
                    {stock.symbol}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-3xl font-bold tracking-tight" style={{ color: 'var(--foreground)' }}>
                    -{stock.dropPct.toFixed(2)}%
                  </span>
                </div>
              </div>
              
              <div
                className="relative h-4 overflow-hidden"
                style={{
                  borderRadius: 999,
                  background: 'rgba(138, 156, 181, 0.14)',
                }}
              >
                <div 
                  className="absolute top-0 left-0 h-full transition-all duration-1000 ease-out"
                  style={{
                    width: `${gaugePercent}%`,
                    background: fill,
                    boxShadow: stock.dropPct >= 20 ? '0 0 24px rgba(255, 207, 51, 0.2)' : 'none',
                  }}
                ></div>
                {[20, 40, 60, 80].map(marker => (
                  <div 
                    key={marker}
                    className="absolute top-0 h-full"
                    style={{ left: `${marker}%` }}
                  >
                    <div
                      className="h-full"
                      style={{ borderLeft: '1px solid rgba(3, 10, 20, 0.28)' }}
                    ></div>
                  </div>
                ))}
              </div>
              
              <div className="flex justify-between text-xs gap-3" style={{ color: 'var(--text-dim)' }}>
                <span>최고가: ${stock.high52w.toFixed(2)} ({stock.highDate})</span>
                <span>현재가: ${stock.currentPrice.toFixed(2)}</span>
              </div>
            </article>
          );
        })}
      </div>
      
      <div
        className="mt-6 pt-4 text-xs"
        style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          color: 'var(--text-dim)',
        }}
      >
        * 게이지가 길어지고 밝은 골드 톤에 가까울수록 고점 대비 많이 하락한 상태를 의미합니다. <br/>
        * 눈금은 각각 -10%, -20%, -30%, -40% 하락 지점을 나타냅니다.
      </div>
    </section>
  );
}
