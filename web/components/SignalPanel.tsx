import { Signal } from "@/lib/strategy";

interface Props {
  signals: Signal[];
}

const typeStyles = {
  buy: "text-red-500",
  sell: "text-blue-500",
  neutral: "text-[var(--muted)]",
};

const typeLabels = {
  buy: "매수",
  sell: "매도",
  neutral: "대기",
};

export default function SignalPanel({ signals }: Props) {
  return (
    <div className="bg-[var(--card)] rounded-lg p-4 border border-[var(--card-border)] transition-colors">
      <h3 className="text-sm font-semibold text-[var(--muted)] mb-3">시그널 현황</h3>
      <div className="space-y-2">
        {signals.map((s, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span
              className={`inline-block w-12 text-center rounded px-1 py-0.5 text-xs font-bold ${
                s.type === "buy"
                  ? "bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400"
                  : s.type === "sell"
                  ? "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-500"
              }`}
            >
              {typeLabels[s.type]}
            </span>
            <span className="text-[var(--muted)]">{s.label}:</span>
            <span className={typeStyles[s.type]}>{s.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
