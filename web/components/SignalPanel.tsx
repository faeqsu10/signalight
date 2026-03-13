import { Signal } from "@/lib/strategy";

interface Props {
  signals: Signal[];
}

export default function SignalPanel({ signals }: Props) {
  return (
    <div className="glass-card p-4">
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-dim)" }}>시그널 현황</h3>
      <div className="space-y-2">
        {signals.map((s, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span
              className="inline-block w-12 text-center rounded px-1 py-0.5 text-xs font-bold flex-shrink-0"
              style={
                s.type === "buy"
                  ? {
                      background: "rgba(0,212,170,0.15)",
                      color: "var(--buy)",
                      border: "1px solid rgba(0,212,170,0.25)",
                    }
                  : s.type === "sell"
                  ? {
                      background: "rgba(255,71,87,0.15)",
                      color: "var(--sell)",
                      border: "1px solid rgba(255,71,87,0.25)",
                    }
                  : {
                      background: "var(--glass)",
                      color: "var(--text-dim)",
                      border: "1px solid var(--glass-border)",
                    }
              }
            >
              {s.type === "buy" ? "매수" : s.type === "sell" ? "매도" : "대기"}
            </span>
            <span style={{ color: "var(--text-dim)" }}>{s.label}:</span>
            <span
              style={{
                color:
                  s.type === "buy"
                    ? "var(--buy)"
                    : s.type === "sell"
                    ? "var(--sell)"
                    : "var(--text-dim)",
              }}
            >
              {s.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
