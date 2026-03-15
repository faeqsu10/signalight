import { NextResponse } from "next/server";
import { fetchOHLCV, fetchVIX } from "@/lib/yahoo-finance";
import { fetchInvestorData } from "@/lib/investor";
import { analyze } from "@/lib/strategy";
import { getCached, setCache } from "@/lib/cache";
import { logApiRequest } from "@/lib/api-logger";
import { recordSuccess, recordFailure } from "@/lib/metrics";
import { getLatestLLMAnalysis, getLatestSentiment } from "@/lib/db";

export async function GET(
  request: Request,
  { params }: { params: { ticker: string } }
) {
  const start = Date.now();
  try {
    const { ticker } = params;
    const url = new URL(request.url);
    const period = parseInt(url.searchParams.get("period") ?? "120", 10) || 120;
    const cacheKey = `stock-${ticker}-${period}`;

    const cached = getCached<object>(cacheKey);
    if (cached) {
      logApiRequest("GET", `/api/stock/${ticker}`, 200, Date.now() - start);
      return NextResponse.json(cached);
    }
    // VIX, 외인/기관, LLM, 뉴스 감성 데이터는 선택적 — 실패해도 나머지 데이터 반환
    const [vixData, investorData, llmAnalysis, sentiment] = await Promise.all([
      fetchVIX(period).catch((e) => {
        recordFailure("vix");
        warnings.push(`VIX 데이터 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      }),
      fetchInvestorData(ticker).catch((e) => {
        recordFailure("investor");
        warnings.push(`외인/기관 데이터 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      }),
      Promise.resolve(getLatestLLMAnalysis(ticker)).catch((e) => {
        warnings.push(`LLM 분석 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      }),
      Promise.resolve(getLatestSentiment(ticker)).catch((e) => {
        warnings.push(`뉴스 감성 조회 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
        return null;
      })
    ]);

    if (vixData !== null) recordSuccess("vix");
    if (investorData !== null) recordSuccess("investor");

    const closes = ohlcv.map((d) => d.close);
    const volumes = ohlcv.map((d) => d.volume);
    const analysis = analyze(closes, vixData, investorData, volumes);

    const result = { ticker, ohlcv, ...analysis, llmAnalysis, sentiment, warnings };

    setCache(cacheKey, result);

    logApiRequest("GET", `/api/stock/${ticker}`, 200, Date.now() - start);
    return NextResponse.json(result);
  } catch (error) {
    recordFailure("ohlcv");
    const { ticker } = params;
    logApiRequest("GET", `/api/stock/${ticker}`, 500, Date.now() - start);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: `OHLCV 데이터 조회 실패 (${message})` },
      { status: 500 }
    );
  }
}
