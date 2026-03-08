import { calcMovingAverage, calcRSI, calcMACD, calcVolumeRatio, calcBollingerBands } from "./indicators";
import {
  SHORT_MA,
  LONG_MA,
  RSI_PERIOD,
  RSI_OVERSOLD,
  RSI_OVERBOUGHT,
  VIX_EXTREME_FEAR,
  VIX_FEAR,
  VIX_EXTREME_GREED,
  INVESTOR_CONSEC_DAYS,
} from "./constants";

export type SignalType = "buy" | "sell" | "neutral";

export interface Signal {
  type: SignalType;
  label: string;
  detail: string;
}

export type SignalStrength = "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell";

export interface SignalHistoryEntry {
  index: number;
  type: "buy" | "sell";
  name: string;
}

export interface AnalysisResult {
  signals: Signal[];
  currentRSI: number | null;
  currentVIX: number | null;
  volumeRatio: number;
  confluenceScore: number;
  signalStrength: SignalStrength;
  shortMA: (number | null)[];
  longMA: (number | null)[];
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
  rsiValues: (number | null)[];
  bollingerUpper: (number | null)[];
  bollingerLower: (number | null)[];
  signalHistory: SignalHistoryEntry[];
}

export function analyze(
  closes: number[],
  vixData?: { date: string; close: number }[] | null,
  investorData?: { date: string; foreignNet: number; institutionalNet: number }[] | null,
  volumes?: number[] | null,
): AnalysisResult {
  const shortMA = calcMovingAverage(closes, SHORT_MA);
  const longMA = calcMovingAverage(closes, LONG_MA);
  const rsiValues = calcRSI(closes, RSI_PERIOD);
  const { macdLine, signalLine, histogram } = calcMACD(closes);
  const volumeRatio = volumes ? calcVolumeRatio(volumes) : 1.0;
  const { upper: bollingerUpper, lower: bollingerLower } = calcBollingerBands(closes, 20, 2);

  const signals: Signal[] = [];
  const n = closes.length;
  let buyScore = 0;
  let sellScore = 0;

  // VIX 현재값 추출
  const currentVIX =
    vixData && vixData.length > 0
      ? vixData[vixData.length - 1].close
      : null;

  if (n < LONG_MA) {
    return {
      signals,
      currentRSI: null,
      currentVIX,
      volumeRatio,
      confluenceScore: 0,
      signalStrength: "neutral" as SignalStrength,
      shortMA,
      longMA,
      macdLine,
      signalLine,
      histogram,
      rsiValues,
      bollingerUpper,
      bollingerLower,
      signalHistory: [],
    };
  }

  // 1. MA Cross
  const prevShort = shortMA[n - 2];
  const prevLong = longMA[n - 2];
  const curShort = shortMA[n - 1];
  const curLong = longMA[n - 1];

  const volNote = volumeRatio >= 1.5
    ? " [거래량 확인 ↑]"
    : volumeRatio < 0.5
      ? " [거래량 부족 주의]"
      : "";

  if (
    prevShort !== null &&
    prevLong !== null &&
    curShort !== null &&
    curLong !== null
  ) {
    if (prevShort <= prevLong && curShort > curLong) {
      signals.push({
        type: "buy",
        label: "이동평균",
        detail: `골든크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 상향 돌파${volNote}`,
      });
      buyScore++;
    } else if (prevShort >= prevLong && curShort < curLong) {
      signals.push({
        type: "sell",
        label: "이동평균",
        detail: `데드크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 하향 돌파${volNote}`,
      });
      sellScore++;
    } else {
      signals.push({
        type: "neutral",
        label: "이동평균",
        detail:
          curShort > curLong
            ? `대기 (${SHORT_MA}일 MA > ${LONG_MA}일 MA)`
            : `대기 (${SHORT_MA}일 MA < ${LONG_MA}일 MA)`,
      });
    }
  }

  // 2. RSI
  const currentRSI = rsiValues[n - 1];
  if (currentRSI !== null) {
    if (currentRSI <= RSI_OVERSOLD) {
      signals.push({
        type: "buy",
        label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매도 (${RSI_OVERSOLD} 이하)`,
      });
      buyScore++;
    } else if (currentRSI >= RSI_OVERBOUGHT) {
      signals.push({
        type: "sell",
        label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매수 (${RSI_OVERBOUGHT} 이상)`,
      });
      sellScore++;
    } else {
      signals.push({
        type: "neutral",
        label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 중립`,
      });
    }
  }

  // 3. MACD
  const prevMACD = macdLine[n - 2];
  const prevSignal = signalLine[n - 2];
  const curMACD = macdLine[n - 1];
  const curSignal = signalLine[n - 1];

  if (
    prevMACD !== null &&
    prevSignal !== null &&
    curMACD !== null &&
    curSignal !== null
  ) {
    if (prevMACD <= prevSignal && curMACD > curSignal) {
      signals.push({
        type: "buy",
        label: "MACD",
        detail: "MACD 라인이 시그널 라인 상향 돌파",
      });
      buyScore++;
    } else if (prevMACD >= prevSignal && curMACD < curSignal) {
      signals.push({
        type: "sell",
        label: "MACD",
        detail: "MACD 라인이 시그널 라인 하향 돌파",
      });
      sellScore++;
    } else {
      signals.push({
        type: "neutral",
        label: "MACD",
        detail: "대기",
      });
    }
  }

  // 4. 볼린저밴드
  const bbUpper = bollingerUpper[n - 1];
  const bbLower = bollingerLower[n - 1];
  const lastClose = closes[n - 1];
  if (bbLower !== null && bbUpper !== null) {
    if (lastClose <= bbLower) {
      signals.push({
        type: "buy",
        label: "볼린저밴드",
        detail: `현재가(${lastClose.toFixed(0)}) <= 하단밴드(${bbLower.toFixed(0)}), 반등 가능성`,
      });
      buyScore++;
    } else if (lastClose >= bbUpper) {
      signals.push({
        type: "sell",
        label: "볼린저밴드",
        detail: `현재가(${lastClose.toFixed(0)}) >= 상단밴드(${bbUpper.toFixed(0)}), 과열 주의`,
      });
      sellScore++;
    } else {
      signals.push({
        type: "neutral",
        label: "볼린저밴드",
        detail: `밴드 내 정상 범위`,
      });
    }
  }

  // 5. VIX (공포지수)
  if (currentVIX !== null) {
    if (currentVIX >= VIX_EXTREME_FEAR) {
      signals.push({
        type: "buy",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 공포 (${VIX_EXTREME_FEAR} 이상, 역발상 매수)`,
      });
      buyScore++;
    } else if (currentVIX >= VIX_FEAR) {
      signals.push({
        type: "buy",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 공포 구간 (${VIX_FEAR} 이상)`,
      });
      buyScore++;
    } else if (currentVIX <= VIX_EXTREME_GREED) {
      signals.push({
        type: "sell",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 탐욕 (${VIX_EXTREME_GREED} 이하, 과열 주의)`,
      });
      sellScore++;
    } else {
      signals.push({
        type: "neutral",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 보통`,
      });
    }
  }

  // 5. 외인/기관 매매동향
  if (investorData && investorData.length >= INVESTOR_CONSEC_DAYS) {
    const recent = investorData.slice(0, INVESTOR_CONSEC_DAYS);

    const allForeignBuy = recent.every((d) => d.foreignNet > 0);
    const allInstitutionalBuy = recent.every((d) => d.institutionalNet > 0);
    const allForeignSell = recent.every((d) => d.foreignNet < 0);
    const allInstitutionalSell = recent.every((d) => d.institutionalNet < 0);

    if (allForeignBuy && allInstitutionalBuy) {
      signals.push({
        type: "buy",
        label: "수급",
        detail: `외인+기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매수`,
      });
      buyScore += 1.5; // 수급 시그널 가중치
    } else if (allForeignSell && allInstitutionalSell) {
      signals.push({
        type: "sell",
        label: "수급",
        detail: `외인+기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매도`,
      });
      sellScore += 1.5; // 수급 시그널 가중치
    } else if (allForeignBuy || allInstitutionalBuy) {
      const who = allForeignBuy ? "외국인" : "기관";
      signals.push({
        type: "neutral",
        label: "수급",
        detail: `${who} ${INVESTOR_CONSEC_DAYS}일 연속 순매수`,
      });
    } else if (allForeignSell || allInstitutionalSell) {
      const who = allForeignSell ? "외국인" : "기관";
      signals.push({
        type: "neutral",
        label: "수급",
        detail: `${who} ${INVESTOR_CONSEC_DAYS}일 연속 순매도`,
      });
    } else {
      signals.push({
        type: "neutral",
        label: "수급",
        detail: "뚜렷한 수급 패턴 없음",
      });
    }
  }

  // Build signal history by scanning all data points for MA cross and MACD cross
  const signalHistory: SignalHistoryEntry[] = [];
  for (let i = 1; i < n; i++) {
    const pShort = shortMA[i - 1];
    const pLong = longMA[i - 1];
    const cShort = shortMA[i];
    const cLong = longMA[i];
    if (pShort !== null && pLong !== null && cShort !== null && cLong !== null) {
      if (pShort <= pLong && cShort > cLong) {
        signalHistory.push({ index: i, type: "buy", name: "골든크로스" });
      } else if (pShort >= pLong && cShort < cLong) {
        signalHistory.push({ index: i, type: "sell", name: "데드크로스" });
      }
    }
    const pMACD = macdLine[i - 1];
    const pSig = signalLine[i - 1];
    const cMACD = macdLine[i];
    const cSig = signalLine[i];
    if (pMACD !== null && pSig !== null && cMACD !== null && cSig !== null) {
      if (pMACD <= pSig && cMACD > cSig) {
        signalHistory.push({ index: i, type: "buy", name: "MACD" });
      } else if (pMACD >= pSig && cMACD < cSig) {
        signalHistory.push({ index: i, type: "sell", name: "MACD" });
      }
    }
  }

  const confluenceScore = (buyScore > 0 && buyScore === sellScore) ? 0 : Math.max(buyScore, sellScore);

  // 신호 강도 분류 (가중 점수 기반)
  const netScore = buyScore - sellScore;
  let signalStrength: SignalStrength;
  if (netScore >= 3.0) signalStrength = "strong_buy";
  else if (netScore >= 1.5) signalStrength = "buy";
  else if (netScore <= -3.0) signalStrength = "strong_sell";
  else if (netScore <= -1.5) signalStrength = "sell";
  else signalStrength = "neutral";

  return {
    signals,
    currentRSI,
    currentVIX,
    volumeRatio,
    confluenceScore,
    signalStrength,
    shortMA,
    longMA,
    macdLine,
    signalLine,
    histogram,
    rsiValues,
    bollingerUpper,
    bollingerLower,
    signalHistory,
  };
}
