import { NextResponse } from 'next/server';
import { fetchOHLCV } from "@/lib/yahoo-finance";

const TARGET_STOCKS: Record<string, string> = {
    "NVDA": "엔비디아",
    "PLTR": "팔란티어",
    "MSFT": "마이크로소프트",
    "GOOGL": "구글",
    "AMZN": "아마존",
    "META": "메타",
    "TSLA": "테슬라"
};

export async function GET() {
  try {
    const symbols = Object.keys(TARGET_STOCKS);
    
    const results = await Promise.all(
      symbols.map(async (symbol) => {
        try {
          const ohlcv = await fetchOHLCV(symbol, 365);
          if (!ohlcv || ohlcv.length === 0) return null;
          
          const currentPrice = ohlcv[ohlcv.length - 1].close;
          
          // 52주 최고가 찾기
          let high52w = -1;
          let highDate = "";
          
          for (const d of ohlcv) {
            if (d.high > high52w) {
              high52w = d.high;
              highDate = d.date;
            }
          }
          
          const dropPct = ((high52w - currentPrice) / high52w) * 100;
          
          return {
            symbol,
            name: TARGET_STOCKS[symbol],
            currentPrice: Number(currentPrice.toFixed(2)),
            high52w: Number(high52w.toFixed(2)),
            highDate,
            dropPct: Number(dropPct.toFixed(2))
          };
        } catch (e) {
          console.error(`Error fetching data for ${symbol}:`, e);
          return null;
        }
      })
    );
    
    const filteredResults = results
      .filter((r): r is NonNullable<typeof r> => r !== null)
      .sort((a, b) => b.dropPct - a.dropPct);
    
    return NextResponse.json(filteredResults);
  } catch (error) {
    console.error('Error in bigtech API:', error);
    return NextResponse.json({ error: 'Failed to fetch big tech data' }, { status: 500 });
  }
}
