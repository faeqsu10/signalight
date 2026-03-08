"use client";

import type { RecoveryAnalysis } from "@/lib/recovery";

interface RecoveryPanelProps {
  recovery: RecoveryAnalysis | null;
  loading?: boolean;
}

function ScoreGauge({ score }: { score: number }) {
  const pct = (score / 10) * 100;
  const color =
    score >= 7 ? "#22c55e" : score >= 4 ? "#eab308" : "#ef4444";

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-3 bg-zinc-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-lg font-bold" style={{ color }}>
        {score.toFixed(1)}
      </span>
      <span className="text-xs text-zinc-400">/10</span>
    </div>
  );
}

function CheckItem({ name, passed, detail }: { name: string; passed: boolean; detail: string }) {
  return (
    <div className="flex items-start gap-2 py-1.5">
      <span className={`text-sm mt-0.5 ${passed ? "text-green-400" : "text-zinc-500"}`}>
        {passed ? "\u2713" : "\u2717"}
      </span>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-medium ${passed ? "text-green-300" : "text-zinc-400"}`}>
          {name}
        </div>
        <div className="text-xs text-zinc-500 truncate">{detail}</div>
      </div>
    </div>
  );
}

export default function RecoveryPanel({ recovery, loading }: RecoveryPanelProps) {
  if (loading) {
    return (
      <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50 animate-pulse">
        <div className="h-5 bg-zinc-700 rounded w-40 mb-3" />
        <div className="h-3 bg-zinc-700 rounded w-full mb-4" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-8 bg-zinc-700/50 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!recovery) return null;

  return (
    <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
      <h3 className="text-sm font-semibold text-zinc-300 mb-3">
        회복 시그널 체크리스트
      </h3>

      <ScoreGauge score={recovery.score} />

      <p className="text-xs text-zinc-400 mt-2 mb-3">{recovery.interpretation}</p>

      <div className="divide-y divide-zinc-700/30">
        {recovery.checks.map((check) => (
          <CheckItem
            key={check.name}
            name={check.name}
            passed={check.passed}
            detail={check.detail}
          />
        ))}
      </div>

      <p className="text-[10px] text-zinc-600 mt-3 leading-tight">
        {recovery.disclaimer}
      </p>
    </div>
  );
}
