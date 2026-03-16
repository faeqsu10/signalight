'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

type StockData = {
  symbol: string;
  name: string;
  currentPrice: number;
  high52w: number;
  highDate: string;
  dropPct: number;
};

type BigTechDropPanelProps = {
  variant?: 'preview' | 'full';
};

function getGaugeFill(dropPct: number) {
  if (dropPct >= 30) return 'linear-gradient(90deg, #ffd84d 0%, #ffbe1b 100%)';
  if (dropPct >= 20) return 'linear-gradient(90deg, #ffd25c 0%, #ff9d41 100%)';
  if (dropPct >= 10) return 'linear-gradient(90deg, #ffb35b 0%, #ff8d3a 100%)';
  return 'linear-gradient(90deg, #ff8d3a 0%, #ff9e42 100%)';
}

function discountLabel(dropPct: number) {
  if (dropPct >= 30) return 'Deep Value';
  if (dropPct >= 20) return 'Watch Zone';
  if (dropPct >= 10) return 'Pullback';
  return 'Near High';
}

export default function BigTechDropPanel({ variant = 'full' }: BigTechDropPanelProps) {
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

  if (variant === 'preview') {
    const leader = data[0];
    const secondary = data.slice(1, 4);

    return (
      <Link
        href="/bigtech"
        className="block"
        aria-label="빅테크 할인율 상세 페이지로 이동"
      >
        <section
          className="glass-card overflow-hidden transition-transform duration-200 hover:-translate-y-0.5"
          style={{
            borderRadius: 20,
            padding: 20,
            background: 'var(--panel-surface-strong)',
          }}
        >
          <div className="flex flex-col gap-5 lg:flex-row lg:items-stretch">
            <div className="rounded-2xl px-5 py-5 lg:w-[46%]" style={{
              background: 'linear-gradient(135deg, rgba(255,207,51,0.1), rgba(255,142,60,0.04) 45%, transparent 90%)',
              border: '1px solid var(--panel-border-strong)',
            }}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold tracking-[0.24em] uppercase" style={{ color: 'var(--accent)' }}>
                    Featured Scanner
                  </p>
                  <h3 className="mt-2 text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
                    빅테크 할인율
                  </h3>
                </div>
                <span
                  className="rounded-full px-3 py-1 text-xs font-semibold"
                  style={{
                    color: 'var(--foreground)',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  상세 보기 →
                </span>
              </div>
              <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-dim)' }}>
                고점 대비 할인 폭이 큰 빅테크를 한 화면에서 비교하고, 전용 페이지에서 전체 종목을
                깊게 확인할 수 있습니다.
              </p>

              <div className="mt-6 rounded-2xl px-4 py-4" style={{
                background: 'var(--panel-muted)',
                border: '1px solid var(--panel-border-strong)',
              }}>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>{leader.name}</span>
                      <span
                        className="text-[11px] px-2 py-1 rounded-md font-medium"
                        style={{
                          color: 'rgba(255,255,255,0.42)',
                          background: 'rgba(255,255,255,0.04)',
                        }}
                      >
                        {leader.symbol}
                      </span>
                    </div>
                    <p className="mt-1 text-xs" style={{ color: 'var(--text-dim)' }}>
                      현재가 ${leader.currentPrice.toFixed(2)} · 최고가 ${leader.high52w.toFixed(2)}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold tracking-tight" style={{ color: 'var(--foreground)' }}>
                      -{leader.dropPct.toFixed(2)}%
                    </div>
                    <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>
                      가장 큰 할인 폭
                    </p>
                    <span
                      className="mt-2 inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold"
                      style={{
                        color: 'var(--accent)',
                        background: 'rgba(246,197,68,0.08)',
                        border: '1px solid rgba(246,197,68,0.16)',
                      }}
                    >
                      {discountLabel(leader.dropPct)}
                    </span>
                  </div>
                </div>
                <div
                  className="relative mt-4 h-4 overflow-hidden"
                  style={{
                    borderRadius: 999,
                    background: 'rgba(138, 156, 181, 0.14)',
                  }}
                >
                  <div
                    className="absolute inset-y-0 left-0"
                    style={{
                      width: `${Math.min(100, (leader.dropPct / 50) * 100)}%`,
                      background: getGaugeFill(leader.dropPct),
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="flex-1 rounded-2xl px-4 py-4" style={{
              background: 'var(--panel-muted)',
              border: '1px solid var(--panel-border-strong)',
            }}>
              <div className="flex items-center justify-between gap-3 mb-4">
                <h4 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
                  빠르게 보기
                </h4>
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>
                  상위 {Math.min(data.length, 4)}종목
                </span>
              </div>
              <div className="space-y-4">
                {secondary.map((stock) => (
                  <div
                    key={stock.symbol}
                    className="space-y-2 rounded-2xl px-3 py-3"
                    style={{
                      background: 'var(--panel-muted)',
                      border: '1px solid var(--panel-border-strong)',
                    }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium" style={{ color: 'var(--foreground)' }}>{stock.name}</span>
                        <span className="text-[11px]" style={{ color: 'var(--text-dim)' }}>
                          {stock.symbol}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
                          -{stock.dropPct.toFixed(2)}%
                        </span>
                        <p className="text-[10px]" style={{ color: 'var(--text-dim)' }}>
                          {discountLabel(stock.dropPct)}
                        </p>
                      </div>
                    </div>
                    <div
                      className="relative h-3 overflow-hidden"
                      style={{ borderRadius: 999, background: 'rgba(138, 156, 181, 0.14)' }}
                    >
                      <div
                        className="absolute inset-y-0 left-0"
                        style={{
                          width: `${Math.min(100, (stock.dropPct / 50) * 100)}%`,
                          background: getGaugeFill(stock.dropPct),
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </Link>
    );
  }

  return (
    <section
      className="glass-card overflow-hidden"
      style={{
        borderRadius: 20,
        padding: 20,
        background: 'var(--panel-surface-strong)',
      }}
    >
      <div
        className="mb-6 rounded-2xl px-5 py-4"
        style={{
          background:
            'linear-gradient(135deg, rgba(255,207,51,0.08), rgba(255,142,60,0.02) 45%, transparent 80%)',
          border: '1px solid var(--panel-border-strong)',
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-xl font-bold" style={{ color: 'var(--foreground)' }}>
              <span>💰</span> 빅테크 할인율 스캐너 (분할 매수 타점)
            </h3>
            <p className="mt-2 text-sm leading-6" style={{ color: 'var(--text-dim)' }}>
              52주 최고가 대비 할인 폭을 한눈에 보여주는 스캐너입니다. 길고 밝은 게이지일수록
              분할 매수 후보로 볼 수 있는 구간에 더 가까워집니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span
              className="rounded-full px-2.5 py-1"
              style={{
                color: 'var(--foreground)',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.05)',
              }}
            >
              Drawdown Ranking
            </span>
            <span
              className="rounded-full px-2.5 py-1"
              style={{
                color: 'var(--accent)',
                background: 'rgba(246,197,68,0.08)',
                border: '1px solid rgba(246,197,68,0.12)',
              }}
            >
              Action Zones
            </span>
          </div>
        </div>
      </div>
      
      <div className="space-y-6">
        {data.map((stock) => {
          const gaugePercent = Math.min(100, (stock.dropPct / 50) * 100);
          const fill = getGaugeFill(stock.dropPct);

          return (
            <article
              key={stock.symbol}
              className="flex flex-col gap-3 rounded-2xl px-4 py-4"
              style={{
                background: 'var(--panel-muted)',
                border: '1px solid var(--panel-border-strong)',
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
                  <p className="mt-1 text-[10px]" style={{ color: 'var(--text-dim)' }}>
                    {discountLabel(stock.dropPct)}
                  </p>
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
