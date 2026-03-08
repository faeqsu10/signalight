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

  // localStorage에서 매수가 복원
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

  // 매수가 변경 시 손익 계산 (즉시) + API 호출 (디바운스 300ms)
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

    // Recovery API에서 포지션 액션 가져오기 (디바운스)
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

  const pnlColor = pnlPct !== null
    ? pnlPct >= 0 ? "text-red-600 dark:text-red-400" : "text-blue-600 dark:text-blue-400"
    : "text-gray-400 dark:text-zinc-400";

  return (
    <div className="bg-white dark:bg-zinc-800/50 rounded-xl p-4 border border-gray-200 dark:border-zinc-700/50">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-zinc-300 mb-3">
        내 포지션 진단
      </h3>

      <div className="flex gap-2 mb-3">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 dark:text-zinc-500">
            {currency}
          </span>
          <input
            type="number"
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
            placeholder="매수가 입력"
            className="w-full bg-gray-50 dark:bg-zinc-700/50 border border-gray-300 dark:border-zinc-600 rounded-lg pl-7 pr-3 py-2 text-sm text-gray-900 dark:text-zinc-200 placeholder:text-gray-400 dark:placeholder:text-zinc-500 focus:outline-none focus:border-blue-400 dark:focus:border-zinc-400"
          />
        </div>
        {buyPrice && (
          <button
            onClick={handleClear}
            className="px-3 py-2 bg-gray-100 dark:bg-zinc-700/50 border border-gray-300 dark:border-zinc-600 rounded-lg text-xs text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 hover:border-gray-400 dark:hover:border-zinc-500 transition-colors"
          >
            초기화
          </button>
        )}
      </div>

      {pnlPct !== null && (
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-xs text-gray-500 dark:text-zinc-500">손익률</span>
            <span className={`text-lg font-bold ${pnlColor}`}>
              {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </span>
          </div>

          <div className="flex justify-between text-xs text-gray-500 dark:text-zinc-500">
            <span>매수가: {currency}{parseFloat(buyPrice).toLocaleString()}</span>
            <span>현재가: {currency}{currentPrice.toLocaleString()}</span>
          </div>

          {positionAction && (
            <div className="mt-3 p-3 bg-amber-50 dark:bg-zinc-700/30 rounded-lg space-y-1.5">
              <div className="text-sm font-medium text-amber-600 dark:text-amber-300">
                {positionAction.action}
              </div>
              <div className="text-xs text-gray-600 dark:text-zinc-400">{positionAction.reason}</div>
              <div className="text-xs text-gray-400 dark:text-zinc-500 italic">
                {positionAction.caution}
              </div>
            </div>
          )}
        </div>
      )}

      {!buyPrice && (
        <p className="text-xs text-gray-400 dark:text-zinc-600">
          매수가를 입력하면 현재 시그널 기반 맞춤 액션 가이드를 받을 수 있습니다.
        </p>
      )}
    </div>
  );
}
