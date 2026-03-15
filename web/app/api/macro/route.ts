import { NextResponse } from "next/server";
import { MACRO_INDICATORS } from "@/lib/constants";
import { fetchGlobalMacroData } from "@/lib/yahoo-finance";
import { logApiRequest } from "@/lib/api-logger";

export async function GET() {
  const start = Date.now();
  
  try {
    const rawData = await fetchGlobalMacroData();
    const results = rawData.map(item => {
      let changePct = 0;
      if (item.price && item.prevClose) {
        changePct = ((item.price - item.prevClose) / item.prevClose) * 100;
      }
      return {
        key: item.ticker,
        name: item.name,
        ticker: item.ticker,
        price: item.price ?? 0,
        change_pct: changePct,
        unit: item.unit
      };
    });

    logApiRequest("GET", "/api/macro", 200, Date.now() - start);
    return NextResponse.json(results);
  } catch (err) {
    console.error("Macro data fetch error:", err);
    logApiRequest("GET", "/api/macro", 500, Date.now() - start);
    return NextResponse.json({ error: "Macro data fetch failed" }, { status: 500 });
  }
}
