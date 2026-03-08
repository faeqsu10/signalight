import { NextResponse } from "next/server";
import { WATCH_LIST } from "@/lib/constants";
import { getMetrics } from "@/lib/metrics";
import { logApiRequest } from "@/lib/api-logger";

export async function GET() {
  const start = Date.now();
  // constants.ts의 WATCH_LIST를 반환 (향후 DB 연동 시 교체 가능)
  const watchlist = WATCH_LIST.map((item) => ({
    ticker: item.ticker,
    name: item.name,
  }));

  logApiRequest("GET", "/api/watchlist", 200, Date.now() - start);
  return NextResponse.json({ watchlist, metrics: getMetrics() });
}
