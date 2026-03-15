import {
  calcMovingAverage, calcRSI, calcMACD, calcVolumeRatio,
  calcBollingerBands, calcOBV, calcStochasticRSI, detectOBVDivergenceStrength,
} from "./indicators";
import {
  SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
  VIX_EXTREME_FEAR, VIX_FEAR, VIX_EXTREME_GREED, INVESTOR_CONSEC_DAYS,
  STOCH_RSI_PERIOD, STOCH_RSI_SMOOTH_K, STOCH_RSI_SMOOTH_D,
  STOCH_RSI_OVERSOLD, STOCH_RSI_OVERBOUGHT,
} from "./constants";

export type SignalType = "buy" | "sell" | "neutral";

export interface Signal {
  type: SignalType;
  label: string;
  detail: string;
  strength?: number;
}

export type SignalStrength = "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell";
export type MarketRegime = "uptrend" | "downtrend" | "sideways";

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
  confluenceMixed: boolean;
  signalStrength: SignalStrength;
  marketRegime: MarketRegime;
  shortMA: (number | null)[];
  longMA: (number | null)[];
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
  rsiValues: (number | null)[];
  bollingerUpper: (number | null)[];
  bollingerLower: (number | null)[];
  signalHistory: SignalHistoryEntry[];
  stochRSIK: number | null;
  stochRSID: number | null;
}

function detectMarketRegime(
  closes: number[],
  shortMA: (number | null)[],
  longMA: (number | null)[],
  rsiValue: number | null,
): MarketRegime {
  const n = closes.length;
  const price = closes[n - 1];
  const curShort = shortMA[n - 1];
  const curLong = longMA[n - 1];

  if (curShort === null || curLong === null) return "sideways";

  if (price > curLong && curShort > curLong && (rsiValue === null || rsiValue > 50)) {
    return "uptrend";
  } else if (price < curLong && curShort < curLong && (rsiValue === null || rsiValue < 50)) {
    return "downtrend";
  }
  return "sideways";
}

function regimeWeight(regime: MarketRegime, signalType: string): number {
  if (regime === "uptrend") return signalType === "buy" ? 1.2 : 0.8;
  if (regime === "downtrend") return signalType === "sell" ? 1.2 : 0.8;
  return 1.0;
}

function continuousRSIScore(rsiValue: number): number {
  if (rsiValue <= 20) return 1.0;
  if (rsiValue <= RSI_OVERSOLD) return 0.5 + 0.5 * (RSI_OVERSOLD - rsiValue) / (RSI_OVERSOLD - 20);
  if (rsiValue >= 80) return 1.0;
  if (rsiValue >= RSI_OVERBOUGHT) return 0.5 + 0.5 * (rsiValue - RSI_OVERBOUGHT) / (80 - RSI_OVERBOUGHT);
  return 0;
}

function continuousBBScore(price: number, bbLower: number, bbUpper: number): number {
  const bbRange = bbUpper - bbLower;
  if (bbRange <= 0) return 0;
  const pctB = (price - bbLower) / bbRange;

  if (pctB <= 0) return 1.0;       // buy: lower band break
  if (pctB < 0.2) return 0.3 + 0.4 * (0.2 - pctB) / 0.2;  // buy: near lower
  if (pctB >= 1.0) return -1.0;    // sell: upper band break
  if (pctB > 0.8) return -(0.3 + 0.4 * (pctB - 0.8) / 0.2); // sell: near upper
  return 0;
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
  const obv = volumes ? calcOBV(closes, volumes) : null;
  const { k: stochK, d: stochD } = calcStochasticRSI(
    closes, STOCH_RSI_PERIOD, STOCH_RSI_SMOOTH_K, STOCH_RSI_SMOOTH_D,
  );

  const signals: Signal[] = [];
  const n = closes.length;
  let buyScore = 0;
  let sellScore = 0;

  const currentVIX = vixData && vixData.length > 0 ? vixData[vixData.length - 1].close : null;
  const currentRSI = rsiValues[n - 1];
  const currentStochK = stochK[n - 1];
  const currentStochD = stochD[n - 1];

  if (n < LONG_MA) {
    return {
      signals, currentRSI, currentVIX, volumeRatio,
      confluenceScore: 0, confluenceMixed: false, signalStrength: "neutral", marketRegime: "sideways",
      shortMA, longMA, macdLine, signalLine, histogram, rsiValues,
      bollingerUpper, bollingerLower, signalHistory: [],
      stochRSIK: currentStochK, stochRSID: currentStochD,
    };
  }

  // Market regime detection
  const regime = detectMarketRegime(closes, shortMA, longMA, currentRSI);

  // 1. MA Cross (continuous)
  const prevShort = shortMA[n - 2];
  const prevLong = longMA[n - 2];
  const curShort = shortMA[n - 1];
  const curLong = longMA[n - 1];

  const volNote = volumeRatio >= 1.5
    ? " [거래량 확인 ↑]"
    : volumeRatio < 0.5 ? " [거래량 부족 주의]" : "";

  if (prevShort !== null && prevLong !== null && curShort !== null && curLong !== null) {
    if (prevShort <= prevLong && curShort > curLong) {
      const score = 1.0 * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "이동평균",
        detail: `골든크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 상향 돌파${volNote}`,
        strength: Math.round(score * 100) / 100,
      });
      buyScore += score;
    } else if (prevShort >= prevLong && curShort < curLong) {
      const score = 1.0 * regimeWeight(regime, "sell");
      signals.push({
        type: "sell", label: "이동평균",
        detail: `데드크로스 - 단기(${SHORT_MA}일)이 장기(${LONG_MA}일) 하향 돌파${volNote}`,
        strength: Math.round(score * 100) / 100,
      });
      sellScore += score;
    } else {
      // Trend alignment bonus
      const lastClose = closes[n - 1];
      if (curShort > curLong && lastClose > curShort) {
        buyScore += 0.4 * regimeWeight(regime, "buy");
        signals.push({ type: "neutral", label: "이동평균", detail: `상승 정렬 (${SHORT_MA}일 MA > ${LONG_MA}일 MA)` });
      } else if (curShort < curLong && lastClose < curShort) {
        sellScore += 0.4 * regimeWeight(regime, "sell");
        signals.push({ type: "neutral", label: "이동평균", detail: `하락 정렬 (${SHORT_MA}일 MA < ${LONG_MA}일 MA)` });
      } else {
        signals.push({
          type: "neutral", label: "이동평균",
          detail: curShort > curLong
            ? `대기 (${SHORT_MA}일 MA > ${LONG_MA}일 MA)`
            : `대기 (${SHORT_MA}일 MA < ${LONG_MA}일 MA)`,
        });
      }
    }
  }

  // 2. RSI (continuous)
  let rsiFiredBuy = false;
  let rsiFiredSell = false;
  if (currentRSI !== null) {
    const rsiScore = continuousRSIScore(currentRSI);
    if (rsiScore > 0 && currentRSI <= RSI_OVERSOLD) {
      const weighted = rsiScore * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매도 (강도: ${rsiScore.toFixed(1)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
      rsiFiredBuy = true;
    } else if (currentRSI <= 40) {
      // RSI 35~40: graduated buy signal (데드존 해소)
      const gradStrength = 0.3 * (40 - currentRSI) / (40 - RSI_OVERSOLD);
      const weighted = gradStrength * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 근접 과매도 (강도: ${gradStrength.toFixed(2)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
      rsiFiredBuy = true;
    } else if (rsiScore > 0 && currentRSI >= RSI_OVERBOUGHT) {
      const weighted = rsiScore * regimeWeight(regime, "sell");
      signals.push({
        type: "sell", label: "RSI",
        detail: `${currentRSI.toFixed(1)} - 과매수 (강도: ${rsiScore.toFixed(1)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      sellScore += weighted;
      rsiFiredSell = true;
    } else {
      signals.push({ type: "neutral", label: "RSI", detail: `${currentRSI.toFixed(1)} - 중립` });
    }
  }

  // 3. MACD (continuous)
  const prevMACD = macdLine[n - 2];
  const prevSignal = signalLine[n - 2];
  const curMACD = macdLine[n - 1];
  const curSignal = signalLine[n - 1];

  if (prevMACD !== null && prevSignal !== null && curMACD !== null && curSignal !== null) {
    if (prevMACD <= prevSignal && curMACD > curSignal) {
      const score = 1.0 * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "MACD", detail: "MACD 라인이 시그널 라인 상향 돌파",
        strength: Math.round(score * 100) / 100,
      });
      buyScore += score;
    } else if (prevMACD >= prevSignal && curMACD < curSignal) {
      const score = 1.0 * regimeWeight(regime, "sell");
      signals.push({
        type: "sell", label: "MACD", detail: "MACD 라인이 시그널 라인 하향 돌파",
        strength: Math.round(score * 100) / 100,
      });
      sellScore += score;
    } else {
      // Histogram direction bonus
      const curHist = histogram[n - 1];
      const prevHist = histogram[n - 2];
      if (curHist !== null && prevHist !== null) {
        if (curHist > 0 && curHist > prevHist) {
          buyScore += 0.3 * regimeWeight(regime, "buy");
        } else if (curHist < 0 && curHist < prevHist) {
          sellScore += 0.3 * regimeWeight(regime, "sell");
        }
      }
      signals.push({ type: "neutral", label: "MACD", detail: "대기" });
    }
  }

  // 4. Bollinger Bands (continuous %B)
  const bbUpper = bollingerUpper[n - 1];
  const bbLower = bollingerLower[n - 1];
  const lastClose = closes[n - 1];
  if (bbLower !== null && bbUpper !== null) {
    const bbScore = continuousBBScore(lastClose, bbLower, bbUpper);
    if (bbScore > 0) {
      const weighted = bbScore * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "볼린저밴드",
        detail: `현재가(${lastClose.toFixed(0)}) ≤ 하단밴드(${bbLower.toFixed(0)}), 반등 가능성 (강도: ${bbScore.toFixed(1)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
    } else if (bbScore < 0) {
      const absScore = Math.abs(bbScore);
      const weighted = absScore * regimeWeight(regime, "sell");
      signals.push({
        type: "sell", label: "볼린저밴드",
        detail: `현재가(${lastClose.toFixed(0)}) ≥ 상단밴드(${bbUpper.toFixed(0)}), 과열 주의 (강도: ${absScore.toFixed(1)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      sellScore += weighted;
    } else {
      signals.push({ type: "neutral", label: "볼린저밴드", detail: "밴드 내 정상 범위" });
    }
  }

  // 5. OBV Divergence
  if (obv) {
    const obvStrength = detectOBVDivergenceStrength(closes, obv);
    if (obvStrength > 0) {
      const weighted = obvStrength * 0.8 * regimeWeight(regime, "buy");
      signals.push({
        type: "buy", label: "OBV",
        detail: `가격 하락 중 OBV 상승 — 매집 가능성 (강도: ${obvStrength.toFixed(1)})`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
    }
  }

  // 6. Stochastic RSI
  if (currentStochK !== null) {
    if (currentStochK <= STOCH_RSI_OVERSOLD) {
      const raw = 0.5 + 0.5 * (STOCH_RSI_OVERSOLD - currentStochK) / STOCH_RSI_OVERSOLD;
      let stochWeighted = Math.min(1.0, raw) * regimeWeight(regime, "buy");
      if (rsiFiredBuy) stochWeighted *= 0.5;
      signals.push({
        type: "buy", label: "StochRSI",
        detail: `K=${currentStochK.toFixed(1)} - 과매도 (${STOCH_RSI_OVERSOLD} 이하)`,
        strength: Math.round(stochWeighted * 100) / 100,
      });
      buyScore += stochWeighted;
    } else if (currentStochK >= STOCH_RSI_OVERBOUGHT) {
      const raw = 0.5 + 0.5 * (currentStochK - STOCH_RSI_OVERBOUGHT) / (100 - STOCH_RSI_OVERBOUGHT);
      let stochWeighted = Math.min(1.0, raw) * regimeWeight(regime, "sell");
      if (rsiFiredSell) stochWeighted *= 0.5;
      signals.push({
        type: "sell", label: "StochRSI",
        detail: `K=${currentStochK.toFixed(1)} - 과매수 (${STOCH_RSI_OVERBOUGHT} 이상)`,
        strength: Math.round(stochWeighted * 100) / 100,
      });
      sellScore += stochWeighted;
    } else {
      signals.push({
        type: "neutral", label: "StochRSI",
        detail: `K=${currentStochK.toFixed(1)} - 중립`,
      });
    }
  }

  // 7. VIX
  if (currentVIX !== null) {
    if (currentVIX >= VIX_EXTREME_FEAR) {
      signals.push({
        type: "buy", label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 공포 (${VIX_EXTREME_FEAR} 이상, 역발상 매수)`,
        strength: 1.0,
      });
      buyScore += 1.0;
    } else if (currentVIX >= VIX_FEAR) {
      signals.push({
        type: "buy", label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 공포 구간 (${VIX_FEAR} 이상)`,
        strength: 0.7,
      });
      buyScore += 0.7;
    } else if (currentVIX <= VIX_EXTREME_GREED) {
      signals.push({
        type: "sell", label: "VIX",
        detail: `${currentVIX.toFixed(1)} - 극단적 탐욕 (${VIX_EXTREME_GREED} 이하, 과열 주의)`,
        strength: 1.0,
      });
      sellScore += 1.0;
    } else {
      signals.push({ type: "neutral", label: "VIX", detail: `${currentVIX.toFixed(1)} - 보통` });
    }
  }

  // 8. Foreign/Institutional (OR separation)
  if (investorData && investorData.length >= INVESTOR_CONSEC_DAYS) {
    const recent = investorData.slice(0, INVESTOR_CONSEC_DAYS);

    const allForeignBuy = recent.every((d) => d.foreignNet > 0);
    const allForeignSell = recent.every((d) => d.foreignNet < 0);
    const allInstBuy = recent.every((d) => d.institutionalNet > 0);
    const allInstSell = recent.every((d) => d.institutionalNet < 0);

    // Foreign individual (0.75)
    if (allForeignBuy) {
      const weighted = 0.75 * regimeWeight(regime, "buy");
      const netSum = recent.reduce((s, d) => s + d.foreignNet, 0);
      signals.push({
        type: "buy", label: "외인",
        detail: `외국인 ${INVESTOR_CONSEC_DAYS}일 연속 순매수 (${netSum > 0 ? "+" : ""}${netSum.toLocaleString()}주)`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
    } else if (allForeignSell) {
      const weighted = 0.75 * regimeWeight(regime, "sell");
      const netSum = recent.reduce((s, d) => s + d.foreignNet, 0);
      signals.push({
        type: "sell", label: "외인",
        detail: `외국인 ${INVESTOR_CONSEC_DAYS}일 연속 순매도 (${netSum > 0 ? "+" : ""}${netSum.toLocaleString()}주)`,
        strength: Math.round(weighted * 100) / 100,
      });
      sellScore += weighted;
    } else {
      signals.push({ type: "neutral", label: "외인", detail: "뚜렷한 패턴 없음" });
    }

    // Institutional individual (0.75)
    if (allInstBuy) {
      const weighted = 0.75 * regimeWeight(regime, "buy");
      const netSum = recent.reduce((s, d) => s + d.institutionalNet, 0);
      signals.push({
        type: "buy", label: "기관",
        detail: `기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매수 (${netSum > 0 ? "+" : ""}${netSum.toLocaleString()}주)`,
        strength: Math.round(weighted * 100) / 100,
      });
      buyScore += weighted;
    } else if (allInstSell) {
      const weighted = 0.75 * regimeWeight(regime, "sell");
      const netSum = recent.reduce((s, d) => s + d.institutionalNet, 0);
      signals.push({
        type: "sell", label: "기관",
        detail: `기관 ${INVESTOR_CONSEC_DAYS}일 연속 순매도 (${netSum > 0 ? "+" : ""}${netSum.toLocaleString()}주)`,
        strength: Math.round(weighted * 100) / 100,
      });
      sellScore += weighted;
    } else {
      signals.push({ type: "neutral", label: "기관", detail: "뚜렷한 패턴 없음" });
    }
  }

  // Signal history (MA cross + MACD cross scan for chart markers)
  const signalHistory: SignalHistoryEntry[] = [];
  for (let i = 1; i < n; i++) {
    const pS = shortMA[i - 1], pL = longMA[i - 1], cS = shortMA[i], cL = longMA[i];
    if (pS !== null && pL !== null && cS !== null && cL !== null) {
      if (pS <= pL && cS > cL) signalHistory.push({ index: i, type: "buy", name: "골든크로스" });
      else if (pS >= pL && cS < cL) signalHistory.push({ index: i, type: "sell", name: "데드크로스" });
    }
    const pM = macdLine[i - 1], pSig = signalLine[i - 1], cM = macdLine[i], cSig = signalLine[i];
    if (pM !== null && pSig !== null && cM !== null && cSig !== null) {
      if (pM <= pSig && cM > cSig) signalHistory.push({ index: i, type: "buy", name: "MACD" });
      else if (pM >= pSig && cM < cSig) signalHistory.push({ index: i, type: "sell", name: "MACD" });
    }
  }

  // Confluence score
  const isMixed = buyScore > 0 && sellScore > 0 && Math.abs(buyScore - sellScore) < 0.5;
  const confluenceMixed = isMixed;
  const confluenceScore = isMixed
    ? Math.round(Math.abs(buyScore - sellScore) * 10) / 10
    : Math.round(Math.max(buyScore, sellScore) * 10) / 10;

  // Signal strength classification
  const netScore = buyScore - sellScore;
  let signalStrength: SignalStrength;
  if (netScore >= 3.5) signalStrength = "strong_buy";
  else if (netScore >= 1.5) signalStrength = "buy";
  else if (netScore <= -3.5) signalStrength = "strong_sell";
  else if (netScore <= -1.5) signalStrength = "sell";
  else signalStrength = "neutral";

  return {
    signals, currentRSI, currentVIX, volumeRatio, confluenceScore, confluenceMixed,
    signalStrength, marketRegime: regime,
    shortMA, longMA, macdLine, signalLine, histogram, rsiValues,
    bollingerUpper, bollingerLower, signalHistory,
    stochRSIK: currentStochK, stochRSID: currentStochD,
  };
}
