import { NextResponse } from "next/server";
import { getCorpCode, fetchDisclosures } from "@/lib/opendart";
import { getCached, setCache } from "@/lib/cache";

export async function GET(
  _request: Request,
  { params }: { params: { ticker: string } }
) {
  try {
    const { ticker } = params;
    const cacheKey = `disclosure-${ticker}`;

    const cached = getCached<object>(cacheKey);
    if (cached) {
      return NextResponse.json(cached);
    }

    const corpCode = getCorpCode(ticker);
    if (!corpCode) {
      // 미국 주식이거나 매핑 없는 종목
      const result = { ticker, disclosures: [], message: "공시 데이터 미지원 종목" };
      setCache(cacheKey, result);
      return NextResponse.json(result);
    }

    const disclosures = await fetchDisclosures(corpCode, 5);
    const result = { ticker, disclosures };
    setCache(cacheKey, result);

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
