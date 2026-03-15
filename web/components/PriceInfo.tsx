import { OHLCVData } from "@/lib/yahoo-finance";
import { Signal } from "@/lib/strategy";
import Tooltip from "./Tooltip";

interface Props {
  name: string;
  ticker: string;
  ohlcv: OHLCVData[];
  signals: Signal[];
  market?: "KR" | "US";
}

export default function PriceInfo({ name, ticker, ohlcv, signals, market = "KR" }: Props) {
  if (ohlcv.length < 2) return null;

  const latest = ohlcv[ohlcv.length - 1];
  const prev = ohlcv[ohlcv.length - 2];
  const change = latest.close - prev.close;
  const changePercent = (change / prev.close) * 100;
  const isUp = change >= 0;

  const hasBuy = signals.some((s) => s.type === "buy");
  const hasSell = signals.some((s) => s.type === "sell");
  const overallSignal = hasBuy ? "매수" : hasSell ? "매도" : "대기";
  const overallColor = hasBuy
    ? "var(--buy)"
    : hasSell
    ? "var(--sell)"
    : "var(--text-dim)";
  const overallDotColor = hasBuy
    ? "var(--buy)"
    : hasSell
    ? "var(--sell)"
    : "var(--text-dim)";
  const overallGlow = hasBuy
    ? "0 0 8px var(--buy)"
    : hasSell
    ? "0 0 8px var(--sell)"
    : "none";

  return (
    <div
      className="glass-card p-5"
      style={{
        borderRadius: 20,
        background:
          "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
      }}
    >
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: "var(--accent)" }}>
              Live Price
            </span>
            <span
              className="text-[11px] px-2 py-1 rounded-full"
              style={{
                color: "var(--text-dim)",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.05)",
              }}
            >
              {ticker}
            </span>
          </div>
          <div className="text-sm mb-1" style={{ color: "var(--text-dim)" }}>
            {name}
          </div>
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="price-big">
              {market === "US"
                ? latest.close.toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                    minimumFractionDigits: 2,
                  })
                : latest.close.toLocaleString("ko-KR", {
                    style: "currency",
                    currency: "KRW",
                    maximumFractionDigits: 0,
                  })}
            </span>
            <span
              className="text-lg font-medium"
              style={{ color: isUp ? "var(--buy)" : "var(--sell)" }}
            >
              {isUp ? "+" : ""}
              {change.toLocaleString("ko-KR")} ({changePercent >= 0 ? "+" : ""}
              {changePercent.toFixed(2)}%)
            </span>
          </div>
        </div>
        <div
          className="flex items-center gap-2 rounded-2xl px-4 py-3"
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.05)",
          }}
        >
          <span
            className="w-3 h-3 rounded-full"
            style={{
              background: overallDotColor,
              boxShadow: overallGlow,
            }}
          />
          <span className="text-lg font-semibold" style={{ color: overallColor }}>
            {overallSignal}
          </span>
          <Tooltip
            content={
              <div>
                <p className="font-semibold mb-1">종합 시그널</p>
                <p className="opacity-80">모든 기술적 지표(이동평균, RSI, MACD, 볼린저밴드, 거래량 등)를 종합한 최종 판단입니다.</p>
                <p className="mt-1 opacity-70">💡 매수/매도 시그널이 하나라도 있으면 해당 방향으로 표시됩니다. 매수와 매도가 동시에 있으면 매수가 우선합니다.</p>
              </div>
            }
          />
        </div>
      </div>
    </div>
  );
}
