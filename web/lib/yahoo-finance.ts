export interface OHLCVData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * 한국 종목코드(6자리 숫자)인지 판별한다.
 * 한국 종목은 .KS 접미사를 붙여 Yahoo Finance에서 조회.
 */
function toYahooTicker(ticker: string): string {
  return /^\d{6}$/.test(ticker) ? `${ticker}.KS` : ticker;
}

export function isKoreanTicker(ticker: string): boolean {
  return /^\d{6}$/.test(ticker);
}

/** Yahoo Finance API 호출 (429 rate limit 시 1초 대기 후 1회 재시도) */
async function fetchWithRetry(url: string): Promise<Response> {
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0" },
    next: { revalidate: 60 },
  });

  if (res.status === 429) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 60 },
    });
  }

  return res;
}

export async function fetchOHLCV(
  ticker: string,
  days: number = 120
): Promise<OHLCVData[]> {
  const yahooTicker = toYahooTicker(ticker);
  const now = Math.floor(Date.now() / 1000);
  const from = now - days * 24 * 60 * 60;

  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${yahooTicker}?period1=${from}&period2=${now}&interval=1d`;

  const res = await fetchWithRetry(url);

  if (!res.ok) {
    throw new Error(
      `Yahoo Finance OHLCV 조회 실패: ticker=${ticker}, status=${res.status}`
    );
  }

  const json = await res.json();
  const result = json.chart?.result?.[0];
  if (!result) {
    // 장 마감/휴장 등으로 데이터가 없는 경우 빈 배열 반환
    console.warn(`Yahoo Finance OHLCV 데이터 없음 (장 마감/휴장 가능성): ticker=${ticker}`);
    return [];
  }

  const timestamps: number[] = result.timestamp || [];
  const quote = result.indicators?.quote?.[0];
  if (!quote) {
    console.warn(`Yahoo Finance OHLCV quote 데이터 없음: ticker=${ticker}`);
    return [];
  }

  const data: OHLCVData[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (
      quote.open[i] == null ||
      quote.high[i] == null ||
      quote.low[i] == null ||
      quote.close[i] == null
    )
      continue;

    data.push({
      date: new Date(timestamps[i] * 1000).toISOString().split("T")[0],
      open: quote.open[i],
      high: quote.high[i],
      low: quote.low[i],
      close: quote.close[i],
      volume: quote.volume[i] || 0,
    });
  }

  return data;
}

export async function fetchVIX(
  days: number = 120
): Promise<{ date: string; close: number }[]> {
  return fetchMarketData("%5EVIX", days);
}

export async function fetchMarketData(
  ticker: string,
  days: number = 120
): Promise<{ date: string; close: number; change_pct?: number }[]> {
  const now = Math.floor(Date.now() / 1000);
  const from = now - days * 24 * 60 * 60;

  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?period1=${from}&period2=${now}&interval=1d`;

  const res = await fetchWithRetry(url);

  if (!res.ok) {
    throw new Error(`Yahoo Finance ${ticker} 조회 실패: status=${res.status}`);
  }

  const json = await res.json();
  const result = json.chart?.result?.[0];
  if (!result) {
    console.warn(`Yahoo Finance ${ticker} 데이터 없음`);
    return [];
  }

  const timestamps: number[] = result.timestamp || [];
  const quote = result.indicators?.quote?.[0];
  if (!quote) {
    console.warn(`Yahoo Finance ${ticker} quote 데이터 없음`);
    return [];
  }

  const data: { date: string; close: number; change_pct?: number }[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (quote.close[i] == null) continue;

    const prevClose = i > 0 ? quote.close[i - 1] : null;
    const change_pct = prevClose ? ((quote.close[i] - prevClose) / prevClose) * 100 : 0;

    data.push({
      date: new Date(timestamps[i] * 1000).toISOString().split("T")[0],
      close: quote.close[i],
      change_pct: change_pct || 0
    });
  }

  return data;
}
