"use client";

import { LLMAnalysis, Sentiment } from "@/lib/db";
import Tooltip from "./Tooltip";

interface Props {
  analysis: LLMAnalysis | null;
  sentiment?: Sentiment | null;
  loading?: boolean;
}

export default function LLMAnalysisPanel({ analysis, sentiment, loading }: Props) {
  if (loading) {
    return (
      <div
        className="glass-card p-5 animate-pulse"
        style={{
          borderRadius: 20,
          background:
            "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
        }}
      >
        <div className="h-4 w-32 bg-gray-700 rounded mb-4"></div>
        <div className="h-20 bg-gray-700 rounded"></div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div
        className="glass-card p-5 flex flex-col items-center justify-center text-center"
        style={{
          borderRadius: 20,
          background:
            "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--text-dim)" }}>
          이 종목에 대한 AI 분석 데이터가 아직 없습니다.
        </p>
        <p className="text-[10px] mt-1" style={{ color: "var(--text-dim)" }}>
          백엔드 스케줄러가 분석을 진행하면 여기에 표시됩니다.
        </p>
      </div>
    );
  }

  const getVerdictStyles = (verdict: string) => {
    const v = verdict.toUpperCase();
    if (v.includes("BUY") || v.includes("매수")) {
      return { color: "var(--buy)", bg: "rgba(0,212,170,0.1)", label: "매수 권장" };
    }
    if (v.includes("SELL") || v.includes("매도")) {
      return { color: "var(--sell)", bg: "rgba(255,71,87,0.1)", label: "매도 권장" };
    }
    return { color: "var(--hold)", bg: "rgba(255,165,2,0.1)", label: "관망/중립" };
  };

  const styles = getVerdictStyles(analysis.verdict);
  const formattedDate = new Date(analysis.created_at).toLocaleString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="space-y-4">
      <div
        className="glass-card p-5 overflow-hidden relative"
        style={{
          borderRadius: 20,
          background:
            "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold flex items-center gap-1.5" style={{ color: "var(--accent)" }}>
            <span className="text-lg">✨</span> Gemini AI 종합 분석
            <Tooltip content="Google Gemini 1.5 Pro 모델이 기술적 지표, 시장 상황, 뉴스 등을 종합하여 도출한 결론입니다." />
          </h3>
          <span className="text-[10px]" style={{ color: "var(--text-dim)" }}>
            {formattedDate} 분석 ({analysis.model})
          </span>
        </div>

        <div className="flex flex-col md:flex-row gap-6">
          {/* Verdict Circle */}
          <div className="flex flex-col items-center justify-center min-w-[120px]">
            <div 
              className="w-20 h-20 rounded-full flex flex-col items-center justify-center border-2 mb-2"
              style={{ borderColor: styles.color, background: styles.bg, boxShadow: `0 0 15px ${styles.color}33` }}
            >
              <span className="text-xs font-bold" style={{ color: styles.color }}>{styles.label}</span>
              <span className="text-xl font-black" style={{ color: styles.color }}>{analysis.confidence}%</span>
            </div>
            <span className="text-[10px]" style={{ color: "var(--text-dim)" }}>신뢰도 점수</span>
          </div>

          {/* Reasoning */}
          <div className="flex-1">
            <div className="text-sm leading-relaxed" style={{ color: "var(--foreground)" }}>
              <div className="font-semibold mb-2 flex items-center gap-1">
                 <span style={{ color: "var(--accent)" }}>●</span> 분석 근거
              </div>
              <p className="whitespace-pre-wrap text-xs md:text-sm opacity-90">
                {analysis.reasoning}
              </p>
            </div>
          </div>
        </div>

        {/* Background decoration */}
        <div 
          className="absolute -right-4 -bottom-4 opacity-10 pointer-events-none"
          style={{ fontSize: "80px" }}
        >
          ✨
        </div>
      </div>

    {/* News Sentiment Section */}
      {sentiment && (
        <div 
          className="glass-card p-4 border-l-4"
          style={{ 
            borderLeftColor: sentiment.sentiment.includes("긍정") ? "var(--buy)" : 
                            sentiment.sentiment.includes("부정") ? "var(--sell)" : "var(--hold)",
            borderRadius: 20,
            background:
              "linear-gradient(180deg, rgba(16,26,43,0.94) 0%, rgba(10,18,31,0.98) 100%)",
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-bold flex items-center gap-1.5">
              📰 뉴스 감성 분석
              <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                sentiment.sentiment.includes("긍정") ? "bg-buy/10 text-buy" : 
                sentiment.sentiment.includes("부정") ? "bg-sell/10 text-sell" : "bg-hold/10 text-hold"
              }`}>
                {sentiment.sentiment} ({Math.round(sentiment.confidence * 100)}%)
              </span>
            </h4>
            <span className="text-[10px] opacity-40">
              {new Date(sentiment.created_at).toLocaleDateString()}
            </span>
          </div>
          <p className="text-xs mb-3 opacity-80 leading-relaxed">
            {sentiment.summary}
          </p>
          <div className="space-y-1.5">
            {(() => {
              try {
                const headlines = JSON.parse(sentiment.headlines_json);
                return Array.isArray(headlines) ? headlines.slice(0, 3).map((h: string, i: number) => (
                  <div key={i} className="text-[10px] flex items-start gap-2 opacity-60 hover:opacity-100 transition-opacity">
                    <span className="mt-1 flex-shrink-0">•</span>
                    <span className="truncate">{h}</span>
                  </div>
                )) : null;
              } catch {
                return null;
              }
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
