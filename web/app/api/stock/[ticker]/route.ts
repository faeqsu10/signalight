import { NextResponse } from "next/server";
import { fetchOHLCV, fetchVIX } from "@/lib/yahoo-finance";
import { fetchInvestorData } from "@/lib/investor";
import { analyze } from "@/lib/strategy";
import { getCached, setCache } from "@/lib/cache";

export async function GET(
  request: Request,
  { params }: { params: { ticker: string } }
) {
  try {
    const { ticker } = params;
    const url = new URL(request.url);
    const period = parseInt(url.searchParams.get("period") ?? "120", 10) || 120;
    const cacheKey = `stock-${ticker}-${period}`;

    const cached = getCached<object>(cacheKey);
    if (cached) {
      return NextResponse.json(cached);
    }

    // OHLCV, VIX, 외인/기관 데이터를 병렬로 가져온다
    const [ohlcv, vixData, investorData] = await Promise.all([
      fetchOHLCV(ticker, period),
      fetchVIX(period).catch(() => null),
      fetchInvestorData(ticker).catch(() => null),
    ]);

    const closes = ohlcv.map((d) => d.close);
    const volumes = ohlcv.map((d) => d.volume);
    const analysis = analyze(closes, vixData, investorData, volumes);

    const result = { ticker, ohlcv, ...analysis };
    setCache(cacheKey, result);

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
