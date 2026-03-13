"use client";

import { useState, useEffect } from "react";
import type { PositionAction } from "@/lib/recovery";

interface PositionCardProps {
  ticker: string;
  currentPrice: number;
  market: "KR" | "US";
  onBuyPriceChange?: (price: number | null) => void;
}

export default function PositionCard({
  ticker,
  currentPrice,
  market,
  onBuyPriceChange,
}: PositionCardProps) {
  const [buyPrice, setBuyPrice] = useState<string>("");
  const [positionAction, setPositionAction] = useState<PositionAction | null>(null);
  const [pnlPct, setPnlPct] = useState<number | null>(null);

  const currency = market === "KR" ? "\u20A9" : "$";
  const storageKey = `signalight-buyPrice-${ticker}`;

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      setBuyPrice(saved);
    } else {
      setBuyPrice("");
      setPositionAction(null);
      setPnlPct(null);
    }
  }, [storageKey]);

  useEffect(() => {
    const price = parseFloat(buyPrice);
    if (!buyPrice || isNaN(price) || price <= 0) {
      setPositionAction(null);
      setPnlPct(null);
      onBuyPriceChange?.(null);
      return;
    }

    localStorage.setItem(storageKey, buyPrice);
    const pnl = ((currentPrice - price) / price) * 100;
    setPnlPct(pnl);
    onBuyPriceChange?.(price);

    const timer = setTimeout(() => {
      fetch(`/api/stock/${ticker}/recovery?buyPrice=${price}`)
        .then((r) => r.json())
        .then((data) => {
          if (data.positionAction) {
            setPositionAction(data.positionAction);
          }
        })
        .catch(() => {});
    }, 300);

    return () => clearTimeout(timer);
  }, [buyPrice, currentPrice, ticker, storageKey, onBuyPriceChange]);

  const handleClear = () => {
    setBuyPrice("");
    localStorage.removeItem(storageKey);
    setPositionAction(null);
    setPnlPct(null);
    onBuyPriceChange?.(null);
  };

  const pnlColor =
    pnlPct !== null
      ? pnlPct >= 0
        ? "var(--buy)"
        : "var(--sell)"
      : "var(--text-dim)";

  return (
    <div className="glass-card p-4">
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-dim)" }}>
        내 포지션 진단
      </h3>

      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <span
            className="absolute left-3 top-1/2 -translate-y-1/2 text-xs"
            style={{ color: "var(--text-dim)" }}
          >
            {currency}
          </span>
          <input
            type="number"
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
            placeholder="매수가 입력"
            className="w-full rounded-xl pl-7 pr-3 py-2 text-sm focus:outline-none"
            style={{ color: "var(--foreground)" }}
          />
        </div>
        {buyPrice && (
          <button
            onClick={handleClear}
            className="px-3 py-2 rounded-xl text-xs transition-colors"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--glass-border)",
              color: "var(--text-dim)",
            }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--foreground)")}
            onMouseLeave={e => (e.currentTarget.style.color = "var(--text-dim)")}
          >
            초기화
          </button>
        )}
      </div>

      {pnlPct !== null && (
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>손익률</span>
            <span className="text-xl font-bold" style={{ color: pnlColor }}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </span>
          </div>

          <div className="flex justify-between text-xs" style={{ color: "var(--text-dim)" }}>
            <span>매수가: {currency}{parseFloat(buyPrice).toLocaleString()}</span>
            <span>현재가: {currency}{currentPrice.toLocaleString()}</span>
          </div>

          {positionAction && (
            <div
              className="mt-3 p-3 rounded-xl space-y-1.5"
              style={{
                background: "rgba(255,165,2,0.08)",
                border: "1px solid rgba(255,165,2,0.2)",
              }}
            >
              <div className="text-sm font-medium" style={{ color: "var(--hold)" }}>
                {positionAction.action}
              </div>
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                {positionAction.reason}
              </div>
              <div className="text-xs italic" style={{ color: "var(--text-dim)", opacity: 0.7 }}>
                {positionAction.caution}
              </div>
            </div>
          )}
        </div>
      )}

      {!buyPrice && (
        <p className="text-xs" style={{ color: "var(--text-dim)", opacity: 0.6 }}>
          매수가를 입력하면 현재 시그널 기반 맞춤 액션 가이드를 받을 수 있습니다.
        </p>
      )}
    </div>
  );
}
