import { Signal } from "@/lib/strategy";
import Tooltip from "./Tooltip";

interface Props {
  signals: Signal[];
}

export default function SignalPanel({ signals }: Props) {
  return (
    <div className="glass-card p-4">
      <h3 className="text-sm font-semibold mb-3 flex items-center" style={{ color: "var(--text-dim)" }}>
        시그널 현황
        <Tooltip
          content={
            <div>
              <p className="font-semibold mb-1">시그널이란?</p>
              <p className="opacity-80">여러 기술적 지표를 종합 분석하여 매수/매도/대기 판단을 내린 결과입니다.</p>
              <table className="w-full text-[10px] mt-2">
                <tbody>
                  <tr><td style={{ color: "var(--buy)" }} className="pr-2">매수</td><td>지표가 상승 가능성을 시사</td></tr>
                  <tr><td style={{ color: "var(--sell)" }} className="pr-2">매도</td><td>지표가 하락 가능성을 시사</td></tr>
                  <tr><td style={{ color: "var(--text-dim)" }} className="pr-2">대기</td><td>뚜렷한 방향이 없는 상태</td></tr>
                </tbody>
              </table>
              <p className="mt-2 opacity-70">💡 같은 방향의 시그널이 많이 모일수록(합류 점수가 높을수록) 신뢰도가 높습니다.</p>
            </div>
          }
        />
      </h3>
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
