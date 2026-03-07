import { calcMovingAverage, calcRSI, calcMACD } from "./indicators";
import {
  SHORT_MA,
  LONG_MA,
  RSI_PERIOD,
  RSI_OVERSOLD,
  RSI_OVERBOUGHT,
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
  shortMA: (number | null)[];
  longMA: (number | null)[];
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
  rsiValues: (number | null)[];
}

export function analyze(closes: number[]): AnalysisResult {
  const shortMA = calcMovingAverage(closes, SHORT_MA);
  const longMA = calcMovingAverage(closes, LONG_MA);
  const rsiValues = calcRSI(closes, RSI_PERIOD);
  const { macdLine, signalLine, histogram } = calcMACD(closes);

  const signals: Signal[] = [];
  const n = closes.length;

  if (n < LONG_MA) {
    return {
      signals,
      currentRSI: null,
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
    } else if (prevShort >= prevLong && curShort < curLong) {
      signals.push({
        type: "sell",
        label: "이동평균",
        detail: `데드크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 하향 돌파`,
      });
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
    } else if (currentRSI >= RSI_OVERBOUGHT) {
      signals.push({
        type: "sell",
        label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매수 (${RSI_OVERBOUGHT} 이상)`,
      });
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
    } else if (prevMACD >= prevSignal && curMACD < curSignal) {
      signals.push({
        type: "sell",
        label: "MACD",
        detail: "MACD 라인이 시그널 라인 하향 돌파",
      });
    } else {
      signals.push({
        type: "neutral",
        label: "MACD",
        detail: "대기",
      });
    }
  }

  return {
    signals,
    currentRSI,
    shortMA,
    longMA,
    macdLine,
    signalLine,
    histogram,
    rsiValues,
  };
}
