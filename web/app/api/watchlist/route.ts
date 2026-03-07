import { NextResponse } from "next/server";
import { WATCH_LIST } from "@/lib/constants";

export async function GET() {
  // constants.ts의 WATCH_LIST를 반환 (향후 DB 연동 시 교체 가능)
  const watchlist = WATCH_LIST.map((item) => ({
    ticker: item.ticker,
    name: item.name,
  }));

  return NextResponse.json({ watchlist });
}
