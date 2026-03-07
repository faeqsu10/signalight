export function calcMovingAverage(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += closes[j];
    return sum / period;
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

  // Wilder's Smoothing: first value is SMA, then EMA with alpha=1/period
  let avgGain = 0;
  let avgLoss = 0;
  for (let j = 0; j < period; j++) {
    avgGain += gains[j];
    avgLoss += losses[j];
  }
  avgGain /= period;
  avgLoss /= period;

  if (avgLoss === 0) {
    result[period] = 100;
  } else {
    result[period] = 100 - 100 / (1 + avgGain / avgLoss);
  }

  for (let i = period; i < deltas.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;

    if (avgLoss === 0) {
      result[i + 1] = 100;
    } else {
      result[i + 1] = 100 - 100 / (1 + avgGain / avgLoss);
    }
  }

  return result;
}

export function calcEMA(data: number[], span: number): number[] {
  const alpha = 2 / (span + 1);
  const result: number[] = [data[0]];
  for (let i = 1; i < data.length; i++) {
    result.push(alpha * data[i] + (1 - alpha) * result[i - 1]);
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
  const emaFast = calcEMA(closes, fast);
  const emaSlow = calcEMA(closes, slow);

  const macdLine = emaFast.map((f, i) => f - emaSlow[i]);
  const signalLine = calcEMA(macdLine, signal);
  const histogram = macdLine.map((m, i) => m - signalLine[i]);

  return { macdLine, signalLine, histogram };
}

export function calcATR(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number = 14,
): (number | null)[] {
  const result: (number | null)[] = new Array(closes.length).fill(null);
  if (closes.length < period + 1) return result;

  // True Range
  const tr: number[] = [highs[0] - lows[0]];
  for (let i = 1; i < closes.length; i++) {
    const tr1 = highs[i] - lows[i];
    const tr2 = Math.abs(highs[i] - closes[i - 1]);
    const tr3 = Math.abs(lows[i] - closes[i - 1]);
    tr.push(Math.max(tr1, tr2, tr3));
  }

  // Seed: SMA of first `period` TR values (starting from index 1)
  let atr = 0;
  for (let i = 1; i <= period; i++) atr += tr[i];
  atr /= period;
  result[period] = atr;

  // Wilder's smoothing
  for (let i = period + 1; i < closes.length; i++) {
    atr = (atr * (period - 1) + tr[i]) / period;
    result[i] = atr;
  }

  return result;
}

export function calcVolumeRatio(volumes: number[], period: number = 20): number {
  if (volumes.length < period) return 1.0;
  const window = volumes.slice(-period);
  const avg = window.reduce((sum, v) => sum + v, 0) / period;
  if (avg === 0) return 1.0;
  return volumes[volumes.length - 1] / avg;
}
