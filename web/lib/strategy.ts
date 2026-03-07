import { calcMovingAverage, calcRSI, calcMACD, calcVolumeRatio } from "./indicators";
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

export interface AnalysisResult {
  signals: Signal[];
  currentRSI: number | null;
  currentVIX: number | null;
  volumeRatio: number;
  confluenceScore: number;
  shortMA: (number | null)[];
  longMA: (number | null)[];
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
  rsiValues: (number | null)[];
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

  const signals: Signal[] = [];
  const n = closes.length;
  let buyCount = 0;
  let sellCount = 0;

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
      shortMA,
      longMA,
      macdLine,
      signalLine,
      histogram,
      rsiValues,
    };
  }

  // 1. MA Cross
  const prevShort = shortMA[n - 2];
  const prevLong = longMA[n - 2];
  const curShort = shortMA[n - 1];
  const curLong = longMA[n - 1];

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
        detail: `골든크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 상향 돌파`,
      });
      buyCount++;
    } else if (prevShort >= prevLong && curShort < curLong) {
      signals.push({
        type: "sell",
        label: "이동평균",
        detail: `데드크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 하향 돌파`,
      });
      sellCount++;
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
      buyCount++;
    } else if (currentRSI >= RSI_OVERBOUGHT) {
      signals.push({
        type: "sell",
        label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매수 (${RSI_OVERBOUGHT} 이상)`,
      });
      sellCount++;
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
      buyCount++;
    } else if (prevMACD >= prevSignal && curMACD < curSignal) {
      signals.push({
        type: "sell",
        label: "MACD",
        detail: "MACD 라인이 시그널 라인 하향 돌파",
      });
      sellCount++;
    } else {
      signals.push({
        type: "neutral",
        label: "MACD",
        detail: "대기",
      });
    }
  }

  // 4. VIX (공포지수)
  if (currentVIX !== null) {
    if (currentVIX >= VIX_EXTREME_FEAR) {
      signals.push({
        type: "buy",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 공포 (${VIX_EXTREME_FEAR} 이상, 역발상 매수)`,
      });
      buyCount++;
    } else if (currentVIX >= VIX_FEAR) {
      signals.push({
        type: "buy",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 공포 구간 (${VIX_FEAR} 이상)`,
      });
      buyCount++;
    } else if (currentVIX <= VIX_EXTREME_GREED) {
      signals.push({
        type: "sell",
        label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 탐욕 (${VIX_EXTREME_GREED} 이하, 과열 주의)`,
      });
      sellCount++;
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
      buyCount++;
    } else if (allForeignSell && allInstitutionalSell) {
      signals.push({
        type: "sell",
        label: "수급",
        detail: `외인+기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매도`,
      });
      sellCount++;
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

  return {
    signals,
    currentRSI,
    currentVIX,
    volumeRatio,
    confluenceScore: Math.max(buyCount, sellCount),
    shortMA,
    longMA,
    macdLine,
    signalLine,
    histogram,
    rsiValues,
  };
}
