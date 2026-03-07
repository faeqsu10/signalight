import { NextResponse } from "next/server";
import { fetchOHLCV, fetchVIX } from "@/lib/yahoo-finance";
import { fetchInvestorData } from "@/lib/investor";
import { analyze } from "@/lib/strategy";

export async function GET(
  _request: Request,
  { params }: { params: { ticker: string } }
) {
  try {
    const { ticker } = params;

    // OHLCV, VIX, 외인/기관 데이터를 병렬로 가져온다
    const [ohlcv, vixData, investorData] = await Promise.all([
      fetchOHLCV(ticker, 120),
      fetchVIX(120).catch(() => null),
      fetchInvestorData(ticker).catch(() => null),
    ]);

    const closes = ohlcv.map((d) => d.close);
    const analysis = analyze(closes, vixData, investorData);

    return NextResponse.json({
      ticker,
      ohlcv,
      ...analysis,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
