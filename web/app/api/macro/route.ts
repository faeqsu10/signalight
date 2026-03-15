import { NextResponse } from "next/server";
import { MACRO_INDICATORS } from "@/lib/constants";
import { fetchMarketData } from "@/lib/yahoo-finance";
import { logApiRequest } from "@/lib/api-logger";

export async function GET() {
  const start = Date.now();
  
  try {
    const keys = Object.keys(MACRO_INDICATORS);
    const results = await Promise.all(
      keys.map(async (key) => {
        const info = MACRO_INDICATORS[key];
        try {
          const data = await fetchMarketData(info.ticker, 5); 
          const latest = data[data.length - 1];
          
          return {
            key,
            name: info.name,
            ticker: info.ticker,
            price: latest?.close ?? 0,
            change_pct: latest?.change_pct ?? 0,
            unit: info.unit,
          };
        } catch (e) {
          console.error(`Macro fetch failed for ${key}:`, e);
          return { key, name: info.name, error: true };
        }
      })
    );

    logApiRequest("GET", "/api/macro", 200, Date.now() - start);
    return NextResponse.json(results);
  } catch (err) {
    console.error("Macro data fetch error:", err);
    logApiRequest("GET", "/api/macro", 500, Date.now() - start);
    return NextResponse.json({ error: "Macro data fetch failed" }, { status: 500 });
  }
}
