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

    const warnings: string[] = [];

    // OHLCV는 필수 — 실패하면 전체 에러
    const ohlcv = await fetchOHLCV(ticker, period);

    // VIX, 외인/기관은 선택적 — 실패해도 나머지 데이터 반환
    const [vixData, investorData] = await Promise.all([
      fetchVIX(period).catch((e) => {
        warnings.push(`VIX 데이터 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      }),
      fetchInvestorData(ticker).catch((e) => {
        warnings.push(`외인/기관 데이터 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      }),
    ]);

    const closes = ohlcv.map((d) => d.close);
    const volumes = ohlcv.map((d) => d.volume);
    const analysis = analyze(closes, vixData, investorData, volumes);

    const result = { ticker, ohlcv, ...analysis, warnings };
    setCache(cacheKey, result);

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: `OHLCV 데이터 조회 실패 (${message})` },
      { status: 500 }
    );
  }
}
