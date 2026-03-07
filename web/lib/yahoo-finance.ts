export interface OHLCVData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export async function fetchOHLCV(
  ticker: string,
  days: number = 120
): Promise<OHLCVData[]> {
  const ksTicker = `${ticker}.KS`;
  const now = Math.floor(Date.now() / 1000);
  const from = now - days * 24 * 60 * 60;

  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ksTicker}?period1=${from}&period2=${now}&interval=1d`;

  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0",
    },
    next: { revalidate: 60 },
  });

  if (!res.ok) {
    throw new Error(`Yahoo Finance API error: ${res.status}`);
  }

  const json = await res.json();
  const result = json.chart?.result?.[0];
  if (!result) throw new Error("No data returned");

  const timestamps: number[] = result.timestamp || [];
  const quote = result.indicators?.quote?.[0];
  if (!quote) throw new Error("No quote data");

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
