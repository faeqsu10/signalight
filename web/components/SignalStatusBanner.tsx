type SignalItem = { type: string };

export default function SignalStatusBanner({ signals }: { signals: SignalItem[] }) {
  const buySignals = signals.filter((s) => s.type === "BUY").length;
  const sellSignals = signals.filter((s) => s.type === "SELL").length;

  if (buySignals > 0 && buySignals >= sellSignals) {
    return (
      <div
        className="w-full rounded-xl px-4 py-3 text-center text-sm font-semibold"
        style={{
          background: "rgba(0,212,170,0.1)",
          border: "1px solid rgba(0,212,170,0.3)",
          color: "var(--buy)",
        }}
      >
        매수 시그널 {buySignals}개 활성
      </div>
    );
  }

  if (sellSignals > 0) {
    return (
      <div
        className="w-full rounded-xl px-4 py-3 text-center text-sm font-semibold"
        style={{
          background: "rgba(255,71,87,0.1)",
          border: "1px solid rgba(255,71,87,0.3)",
          color: "var(--sell)",
        }}
      >
        매도 시그널 {sellSignals}개 활성
      </div>
    );
  }

  return (
    <div
      className="w-full rounded-xl px-4 py-3 text-center text-sm font-semibold"
      style={{
        background: "var(--glass)",
        border: "1px solid var(--glass-border)",
        color: "var(--text-dim)",
      }}
    >
      시그널 없음
    </div>
  );
}
