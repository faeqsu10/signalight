import { OHLCVData } from "@/lib/yahoo-finance";
import { Signal } from "@/lib/strategy";

interface Props {
  name: string;
  ticker: string;
  ohlcv: OHLCVData[];
  signals: Signal[];
}

export default function PriceInfo({ name, ticker, ohlcv, signals }: Props) {
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
    ? "text-red-400"
    : hasSell
    ? "text-blue-400"
    : "text-gray-500";
  const overallDot = hasBuy
    ? "bg-red-400"
    : hasSell
    ? "bg-blue-400"
    : "bg-gray-500";

  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
      <div>
        <div className="text-gray-400 text-sm">
          {name} {ticker}
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-bold text-white">
            {latest.close.toLocaleString("ko-KR", {
              style: "currency",
              currency: "KRW",
              maximumFractionDigits: 0,
            })}
          </span>
          <span className={`text-lg ${isUp ? "text-red-400" : "text-blue-400"}`}>
            {isUp ? "+" : ""}
            {change.toLocaleString("ko-KR")} ({changePercent >= 0 ? "+" : ""}
            {changePercent.toFixed(2)}%)
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-3 h-3 rounded-full ${overallDot}`} />
        <span className={`text-lg font-semibold ${overallColor}`}>
          {overallSignal}
        </span>
      </div>
    </div>
  );
}
