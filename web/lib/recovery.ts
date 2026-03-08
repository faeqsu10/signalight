/**
 * 회복 시그널 분석 모듈 (TypeScript 포팅).
 *
 * Python signals/recovery.py와 동일 로직.
 * '예측'이 아닌 '현황 판단' 원칙.
 */
import { calcRSI, calcBollingerBands, calcOBV, calcVolumeRatio } from "./indicators";
import { RSI_PERIOD, RSI_OVERSOLD, INVESTOR_CONSEC_DAYS } from "./constants";
import type { SignalStrength } from "./strategy";

// ---------- 상수 ----------

export const RECOVERY_RSI_EXTREME = 20;
export const RECOVERY_VOLUME_SPIKE = 3.0;

// ---------- 타입 ----------

export interface RecoveryCheck {
  name: string;
  passed: boolean;
  weight: number;
  detail: string;
}

export interface RecoveryAnalysis {
  score: number;
  checks: RecoveryCheck[];
  interpretation: string;
  disclaimer: string;
}

export type DrawdownContext = "MARKET_WIDE" | "SECTOR_WIDE" | "INDIVIDUAL";

export interface PositionAction {
  action: string;
  reason: string;
  caution: string;
}

// ---------- 헬퍼 ----------

function detectVolumeSpike(
  volumes: number[],
  threshold: number = RECOVERY_VOLUME_SPIKE,
  period: number = 20,
): boolean {
  if (volumes.length < period + 1) return false;
  const window = volumes.slice(-(period + 1), -1);
  const avg = window.reduce((s, v) => s + v, 0) / period;
  if (avg === 0) return false;
  return volumes[volumes.length - 1] / avg >= threshold;
}

function detectObvDivergence(
  closes: number[],
  obv: number[],
  lookback: number = 20,
): boolean {
  if (closes.length < lookback || obv.length < lookback) return false;

  const recentCloses = closes.slice(-lookback);
  const recentObv = obv.slice(-lookback);
  const half = Math.floor(lookback / 2);

  const firstHalfCloseMin = Math.min(...recentCloses.slice(0, half));
  const secondHalfCloseMin = Math.min(...recentCloses.slice(half));
  const firstHalfObvMin = Math.min(...recentObv.slice(0, half));
  const secondHalfObvMin = Math.min(...recentObv.slice(half));

  return secondHalfCloseMin < firstHalfCloseMin && secondHalfObvMin > firstHalfObvMin;
}

function interpretScore(score: number): string {
  if (score >= 9.0) return "강한 회복 신호 — 다수 바닥 지표 확인됨. 단, 추세 전환 확인 필요.";
  if (score >= 6.0) return "복수 바닥 신호 — 일부 회복 조건 충족. 추가 확인 필요.";
  if (score >= 3.0) return "초기 바닥 신호 — 일부 지표만 확인. 아직 하락 중일 수 있음.";
  return "회복 신호 미감지 — 바닥 형성 증거 부족. 추가 하락 가능성 있음.";
}

// ---------- 시장 맥락 분류 ----------

export function classifyDrawdownContext(
  stockChangePct: number,
  marketChangePct: number,
): DrawdownContext {
  if (marketChangePct < -10 && Math.abs(marketChangePct) >= Math.abs(stockChangePct) * 0.6) {
    return "MARKET_WIDE";
  } else if (marketChangePct < -5) {
    return "SECTOR_WIDE";
  }
  return "INDIVIDUAL";
}

// ---------- 포지션 액션 가이드 ----------

export function getPositionAction(
  signalStrength: SignalStrength,
  pnlPct: number,
): PositionAction {
  const isBuy = signalStrength === "strong_buy" || signalStrength === "buy";
  const isSell = signalStrength === "sell" || signalStrength === "strong_sell";

  if (pnlPct <= -30 && isBuy) {
    return {
      action: "분할 추가 매수 검토",
      reason: `큰 손실(${pnlPct.toFixed(1)}%) 상태이나 회복 시그널 감지. 물타기 가능.`,
      caution: "전체 포트폴리오 비중 확인 필수. 한 종목 과집중 주의.",
    };
  } else if (pnlPct <= -30 && isSell) {
    return {
      action: "손절 검토",
      reason: `큰 손실(${pnlPct.toFixed(1)}%) + 추가 하락 신호. 손실 확대 방지 고려.`,
      caution: "감정적 결정 주의. 펀더멘탈 변화 여부 확인.",
    };
  } else if (pnlPct <= -30) {
    return {
      action: "관망 (홀딩)",
      reason: `큰 손실(${pnlPct.toFixed(1)}%) 상태이나 명확한 방향 신호 없음.`,
      caution: "추가 매수/매도 모두 보류. 추세 전환 확인 후 행동.",
    };
  } else if (pnlPct <= -10 && isBuy) {
    return {
      action: "분할 추가 매수 검토",
      reason: `손실(${pnlPct.toFixed(1)}%) 상태이나 매수 신호. 평단가 낮출 기회.`,
      caution: "전체 포트폴리오 비중 확인.",
    };
  } else if (pnlPct <= -10 && isSell) {
    return {
      action: "일부 손절 검토",
      reason: `손실(${pnlPct.toFixed(1)}%) + 매도 신호. 추가 하락 가능성.`,
      caution: "전량 매도보다 일부 정리 후 관찰 권장.",
    };
  } else if (pnlPct <= -10) {
    return {
      action: "관망 (홀딩)",
      reason: `손실(${pnlPct.toFixed(1)}%) 중. 뚜렷한 방향 없음.`,
      caution: "인내심 필요. 손절가 사전 설정 권장.",
    };
  } else if (isBuy) {
    return {
      action: "보유 유지 또는 추가 매수",
      reason: `손익(${pnlPct.toFixed(1)}%) + 매수 신호.`,
      caution: "비중 과대 주의.",
    };
  } else if (isSell) {
    return {
      action: "일부 익절/손절 검토",
      reason: `손익(${pnlPct.toFixed(1)}%) + 매도 신호.`,
      caution: "전체 매도보다 분할 매도 권장.",
    };
  }
  return {
    action: "보유 유지",
    reason: `손익(${pnlPct.toFixed(1)}%). 뚜렷한 방향 없음.`,
    caution: "별도 행동 불필요.",
  };
}

// ---------- 6항목 체크리스트 분석 ----------

export function analyzeRecovery(
  closes: number[],
  volumes: number[],
  investorData?: { date: string; foreignNet: number; institutionalNet: number }[] | null,
): RecoveryAnalysis {
  const checks: RecoveryCheck[] = [];
  const n = closes.length;

  const rsiValues = calcRSI(closes, RSI_PERIOD);
  const { lower: bbLower } = calcBollingerBands(closes, 20, 2);
  const obv = calcOBV(closes, volumes);

  const currentRSI = rsiValues[n - 1];
  const prevRSI = n >= 2 ? rsiValues[n - 2] : null;

  // 1. RSI 극단 과매도 (< 20)
  const rsiExtreme = currentRSI !== null && currentRSI <= RECOVERY_RSI_EXTREME;
  checks.push({
    name: "RSI 극단 과매도",
    passed: rsiExtreme,
    weight: 1.5,
    detail: currentRSI !== null
      ? `RSI ${currentRSI.toFixed(1)}${rsiExtreme ? " — 극단 과매도 구간" : " — 정상 범위"}`
      : "RSI 데이터 부족",
  });

  // 2. RSI 과매도 이탈
  const rsiEscape = prevRSI !== null && currentRSI !== null
    && prevRSI <= RSI_OVERSOLD && currentRSI > RSI_OVERSOLD;
  checks.push({
    name: "RSI 과매도 이탈",
    passed: rsiEscape,
    weight: 1.5,
    detail: prevRSI !== null && currentRSI !== null
      ? rsiEscape
        ? `RSI ${prevRSI.toFixed(1)} → ${currentRSI.toFixed(1)} (과매도 이탈 확인)`
        : `RSI ${currentRSI.toFixed(1)} — 과매도 이탈 미확인`
      : "RSI 데이터 부족",
  });

  // 3. BB 하단밴드 복귀
  let bbRecovery = false;
  let bbDetail = "볼린저밴드 데이터 부족";
  if (bbLower[n - 1] !== null && n >= 5) {
    const recentTouched = Array.from({ length: Math.min(5, n - 1) }, (_, i) => i + 1)
      .some((i) => bbLower[n - 1 - i] !== null && closes[n - 1 - i] <= bbLower[n - 1 - i]!);
    const currentAbove = closes[n - 1] > bbLower[n - 1]!;
    bbRecovery = recentTouched && currentAbove;
    bbDetail = bbRecovery
      ? "하단밴드 터치 후 반등 확인"
      : recentTouched ? "하단밴드 터치 중 — 아직 반등 미확인" : "하단밴드 미접촉 — 해당 없음";
  }
  checks.push({ name: "BB 하단밴드 복귀", passed: bbRecovery, weight: 1.5, detail: bbDetail });

  // 4. 거래량 급증 (투매)
  const volSpike = detectVolumeSpike(volumes, RECOVERY_VOLUME_SPIKE);
  const volRatio = calcVolumeRatio(volumes);
  checks.push({
    name: "거래량 급증 (투매)",
    passed: volSpike,
    weight: 1.5,
    detail: `거래량 비율 ${volRatio.toFixed(1)}x${volSpike ? " — 투매 수준 급증" : " — 정상 범위"}`,
  });

  // 5. OBV 상승 다이버전스
  const obvDiv = detectObvDivergence(closes, obv, 20);
  checks.push({
    name: "OBV 상승 다이버전스",
    passed: obvDiv,
    weight: 1.5,
    detail: obvDiv ? "OBV 상승 다이버전스 감지" : "OBV 다이버전스 미감지",
  });

  // 6. 기관 매수 전환
  let instBuy = false;
  let instDetail = "수급 데이터 없음";
  if (investorData && investorData.length >= INVESTOR_CONSEC_DAYS) {
    const recent = investorData.slice(0, INVESTOR_CONSEC_DAYS);
    instBuy = recent.every((d) => d.institutionalNet > 0);
    instDetail = instBuy
      ? `기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매수 전환`
      : "기관 연속 순매수 미확인";
  }
  checks.push({ name: "기관 매수 전환", passed: instBuy, weight: 1.0, detail: instDetail });

  // 점수 (0-10 정규화)
  const maxWeight = checks.reduce((s, c) => s + c.weight, 0);
  const rawScore = checks.filter((c) => c.passed).reduce((s, c) => s + c.weight, 0);
  const score = maxWeight > 0 ? (rawScore / maxWeight) * 10 : 0;

  return {
    score: Math.round(score * 10) / 10,
    checks,
    interpretation: interpretScore(score),
    disclaimer: "본 분석은 기술적 지표 기반 현황 판단이며, 투자 추천이 아닙니다. 투자 결정은 본인 책임입니다.",
  };
}
