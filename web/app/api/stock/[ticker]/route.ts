import { NextResponse } from "next/server";
import { fetchOHLCV } from "@/lib/yahoo-finance";
import { analyze } from "@/lib/strategy";

export async function GET(
  _request: Request,
  { params }: { params: { ticker: string } }
) {
  try {
    const { ticker } = params;
    const ohlcv = await fetchOHLCV(ticker, 120);
    const closes = ohlcv.map((d) => d.close);
    const analysis = analyze(closes);

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
