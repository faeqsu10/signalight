export function calcMovingAverage(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += closes[j];
    const avg = sum / period;
    return isNaN(avg) || !isFinite(avg) ? null : avg;
  });
}

export function calcRSI(closes: number[], period: number = 14): (number | null)[] {
  const result: (number | null)[] = new Array(closes.length).fill(null);
  if (closes.length < period + 1) return result;

  const deltas: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    deltas.push(closes[i] - closes[i - 1]);
  }

  const gains = deltas.map((d) => (d > 0 ? d : 0));
  const losses = deltas.map((d) => (d < 0 ? -d : 0));

  let avgGain = 0;
  let avgLoss = 0;
  for (let j = 0; j < period; j++) {
    avgGain += gains[j];
    avgLoss += losses[j];
  }
  avgGain /= period;
  avgLoss /= period;

  const calc = (gain: number, loss: number) => {
    if (loss === 0) return 100;
    const rs = gain / loss;
    const rsi = 100 - 100 / (1 + rs);
    return isNaN(rsi) || !isFinite(rsi) ? null : rsi;
  };

  result[period] = calc(avgGain, avgLoss);

  for (let i = period; i < deltas.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
    result[i + 1] = calc(avgGain, avgLoss);
  }

  return result;
}

export function calcEMA(data: (number | null)[], span: number): (number | null)[] {
  const firstValidIdx = data.findIndex(v => v !== null);
  if (firstValidIdx === -1) return new Array(data.length).fill(null);

  const result: (number | null)[] = new Array(data.length).fill(null);
  const alpha = 2 / (span + 1);
  
  result[firstValidIdx] = data[firstValidIdx];
  
  for (let i = firstValidIdx + 1; i < data.length; i++) {
    const val = data[i];
    const prevEma = result[i - 1];
    if (val === null || prevEma === null) {
      result[i] = prevEma;
      continue;
    }
    const ema = alpha * val + (1 - alpha) * prevEma;
    result[i] = isNaN(ema) || !isFinite(ema) ? prevEma : ema;
  }
  return result;
}

export interface MACDResult {
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
}

export function calcMACD(
  closes: number[],
  fast: number = 12,
  slow: number = 26,
  signal: number = 9
): MACDResult {
  // EMA expects (number | null)[]
  const closesWithNull: (number | null)[] = closes;
  const emaFast = calcEMA(closesWithNull, fast);
  const emaSlow = calcEMA(closesWithNull, slow);

  const macdLine = emaFast.map((f, i) => {
    const s = emaSlow[i];
    if (f === null || s === null) return null;
    return f - s;
  });
  
  const signalLine = calcEMA(macdLine, signal);
  const histogram = macdLine.map((m, i) => {
    const s = signalLine[i];
    if (m === null || s === null) return null;
    return m - s;
  });

  return { macdLine, signalLine, histogram };
}

export function calcBollingerBands(
  closes: number[],
  period: number = 20,
  numStd: number = 2
): { upper: (number | null)[]; middle: (number | null)[]; lower: (number | null)[] } {
  const middle = calcMovingAverage(closes, period);
  const upper: (number | null)[] = new Array(closes.length).fill(null);
  const lower: (number | null)[] = new Array(closes.length).fill(null);

  for (let i = period - 1; i < closes.length; i++) {
    const mid = middle[i];
    if (mid === null) continue;
    let sumSq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sumSq += (closes[j] - mid) ** 2;
    }
    const std = Math.sqrt(sumSq / period);
    const up = mid + numStd * std;
    const lo = mid - numStd * std;
    upper[i] = isNaN(up) || !isFinite(up) ? null : up;
    lower[i] = isNaN(lo) || !isFinite(lo) ? null : lo;
  }

  return { upper, middle, lower };
}

export function calcVolumeRatio(volumes: number[]): number {
  const n = volumes.length;
  if (n < 21) return 1.0;
  const avgVol = volumes.slice(n - 21, n - 1).reduce((a, b) => a + b, 0) / 20;
  if (avgVol === 0) return 1.0;
  const ratio = volumes[n - 1] / avgVol;
  return isNaN(ratio) || !isFinite(ratio) ? 1.0 : ratio;
}

export function calcOBV(closes: number[], volumes: number[]): number[] {
  const obv = [volumes[0]];
  for (let i = 1; i < closes.length; i++) {
    if (closes[i] > closes[i - 1]) obv.push(obv[i - 1] + volumes[i]);
    else if (closes[i] < closes[i - 1]) obv.push(obv[i - 1] - volumes[i]);
    else obv.push(obv[i - 1]);
  }
  return obv;
}

export function calcStochasticRSI(
  closes: number[],
  period: number = 14,
  smoothK: number = 3,
  smoothD: number = 3,
): { k: (number | null)[]; d: (number | null)[] } {
  const rsi = calcRSI(closes, period);
  const stochRsi: (number | null)[] = new Array(rsi.length).fill(null);

  for (let i = period - 1; i < rsi.length; i++) {
    const window = rsi.slice(i - period + 1, i + 1).filter((v): v is number => v !== null);
    if (window.length < period) continue;
    const min = Math.min(...window);
    const max = Math.max(...window);
    if (max - min === 0) stochRsi[i] = 0;
    else stochRsi[i] = (rsi[i]! - min) / (max - min);
  }

  const k = calcMovingAverage(stochRsi.map(v => v === null ? 0 : v), smoothK).map((v, i) => stochRsi[i] === null ? null : v);
  const d = calcMovingAverage(k.map(v => v === null ? 0 : v), smoothD).map((v, i) => k[i] === null ? null : v);

  return { k, d };
}

export function detectOBVDivergenceStrength(closes: number[], obv: number[]): number {
  const n = closes.length;
  if (n < 10) return 0;
  const closeChange = closes[n - 1] - closes[n - 5];
  const obvChange = obv[n - 1] - obv[n - 5];
  if (closeChange < 0 && obvChange > 0) return 0.5; // Weak divergence
  return 0;
}
