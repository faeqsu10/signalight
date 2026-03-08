import { NextResponse } from "next/server";
import { fetchOHLCV, fetchVIX } from "@/lib/yahoo-finance";
import { fetchInvestorData } from "@/lib/investor";
import { analyze } from "@/lib/strategy";
import { analyzeRecovery, getPositionAction, classifyDrawdownContext } from "@/lib/recovery";
import { isKoreanTicker } from "@/lib/yahoo-finance";
import { getCached, setCache } from "@/lib/cache";
import { logApiRequest } from "@/lib/api-logger";

export async function GET(
  request: Request,
  { params }: { params: { ticker: string } },
) {
  const start = Date.now();
  try {
    const { ticker } = params;
    const url = new URL(request.url);
    const buyPriceStr = url.searchParams.get("buyPrice");
    const buyPrice = buyPriceStr ? parseFloat(buyPriceStr) : null;
    const period = parseInt(url.searchParams.get("period") ?? "120", 10) || 120;
    const cacheKey = `recovery-${ticker}-${buyPriceStr ?? "null"}-${period}`;

    const cached = getCached<object>(cacheKey);
    if (cached) {
      logApiRequest("GET", `/api/stock/${ticker}/recovery`, 200, Date.now() - start);
      return NextResponse.json(cached);
    }

    // 데이터 병렬 fetch (period일 + VIX + 수급)
    const [ohlcv, vixData, investorData] = await Promise.all([
      fetchOHLCV(ticker, period),
      fetchVIX(period).catch(() => null),
      isKoreanTicker(ticker) ? fetchInvestorData(ticker).catch(() => null) : Promise.resolve(null),
    ]);

    const closes = ohlcv.map((d) => d.close);
    const volumes = ohlcv.map((d) => d.volume);

    // 회복 분석
    const recovery = analyzeRecovery(closes, volumes, investorData);

    // 기존 시그널 분석 (signal_strength 추출용)
    const analysis = analyze(closes, vixData, investorData, volumes);

    // 포지션 진단 (buyPrice가 있을 때만)
    let positionAction = null;
    let pnlPct = null;
    if (buyPrice !== null && buyPrice > 0 && closes.length > 0) {
      const currentPrice = closes[closes.length - 1];
      pnlPct = ((currentPrice - buyPrice) / buyPrice) * 100;
      positionAction = getPositionAction(analysis.signalStrength, pnlPct);
    }

    // 시장 맥락 분류 (한국 종목만, VIX 기반 간이 판단)
    let drawdownContext = null;
    if (closes.length >= 20) {
      const stockChange = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;
      // VIX 변화를 시장 변화 프록시로 사용 (정밀하지 않지만 참고용)
      const marketChange = vixData && vixData.length >= 2
        ? -((vixData[vixData.length - 1].close - vixData[0].close) / vixData[0].close) * 100 * 0.5
        : 0;
      drawdownContext = classifyDrawdownContext(stockChange, marketChange);
    }

    const result = {
      ticker,
      recovery,
      positionAction,
      pnlPct: pnlPct !== null ? Math.round(pnlPct * 100) / 100 : null,
      drawdownContext,
      signalStrength: analysis.signalStrength,
    };
    setCache(cacheKey, result);

    logApiRequest("GET", `/api/stock/${ticker}/recovery`, 200, Date.now() - start);
    return NextResponse.json(result);
  } catch (error) {
    const { ticker } = params;
    logApiRequest("GET", `/api/stock/${ticker}/recovery`, 500, Date.now() - start);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
