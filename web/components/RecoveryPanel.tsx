"use client";

import type { RecoveryAnalysis } from "@/lib/recovery";

interface RecoveryPanelProps {
  recovery: RecoveryAnalysis | null;
  loading?: boolean;
}

function ScoreGauge({ score }: { score: number }) {
  const pct = (score / 10) * 100;
  const color =
    score >= 7 ? "var(--buy)" : score >= 4 ? "var(--hold)" : "var(--sell)";

  return (
    <div className="flex items-center gap-3">
      <div
        className="flex-1 h-2.5 rounded-full overflow-hidden"
        style={{ background: "var(--chip-surface)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}` }}
        />
      </div>
      <span className="text-lg font-bold" style={{ color }}>
        {score.toFixed(1)}
      </span>
      <span className="text-xs" style={{ color: "var(--text-dim)" }}>/10</span>
    </div>
  );
}

function CheckItem({ name, passed, detail }: { name: string; passed: boolean; detail: string }) {
  return (
    <div className="flex items-start gap-2 py-1.5">
      <span
        className="text-sm mt-0.5 flex-shrink-0"
        style={{ color: passed ? "var(--buy)" : "var(--text-dim)" }}
      >
        {passed ? "\u2713" : "\u2717"}
      </span>
      <div className="flex-1 min-w-0">
        <div
          className="text-sm font-medium"
          style={{ color: passed ? "var(--buy)" : "var(--text-dim)" }}
        >
          {name}
        </div>
        <div className="text-xs truncate" style={{ color: "var(--text-dim)", opacity: 0.7 }}>
          {detail}
        </div>
      </div>
    </div>
  );
}

export default function RecoveryPanel({ recovery, loading }: RecoveryPanelProps) {
  if (loading) {
    return (
      <div
        className="glass-card p-4 animate-pulse"
      >
        <div className="h-5 rounded w-40 mb-3" style={{ background: "var(--glass)" }} />
        <div className="h-2.5 rounded w-full mb-4" style={{ background: "var(--glass)" }} />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-8 rounded" style={{ background: "var(--glass)" }} />
          ))}
        </div>
      </div>
    );
  }

  if (!recovery) return null;

  return (
    <div
      className="glass-card p-5"
      style={{
        borderRadius: 20,
        background: "var(--panel-surface-strong)",
      }}
    >
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--accent)" }}>
        회복 시그널 체크리스트
      </h3>

      <ScoreGauge score={recovery.score} />

      <p className="text-xs mt-2 mb-3" style={{ color: "var(--text-dim)" }}>
        {recovery.interpretation}
      </p>

      <div
        className="divide-y rounded-2xl px-3 py-1 mt-4"
        style={{ background: "var(--panel-muted)", border: "1px solid var(--panel-border-strong)", borderColor: "var(--panel-border-strong)" }}
      >
        {recovery.checks.map((check) => (
          <CheckItem
            key={check.name}
            name={check.name}
            passed={check.passed}
            detail={check.detail}
          />
        ))}
      </div>

      <p className="text-[10px] mt-3 leading-tight" style={{ color: "var(--text-dim)", opacity: 0.5 }}>
        {recovery.disclaimer}
      </p>
    </div>
  );
}
