import { NextResponse } from "next/server";
import { WATCH_LIST, SHORT_MA, LONG_MA, RSI_OVERSOLD } from "@/lib/constants";
import { fetchOHLCV } from "@/lib/yahoo-finance";
import { calcMovingAverage, calcRSI, calcVolumeRatio } from "@/lib/indicators";
import { logApiRequest } from "@/lib/api-logger";

interface ScanResult {
  ticker: string;
  name: string;
  price: number;
  reason: string;
}

export async function GET() {
  const start = Date.now();
  const goldenCross: ScanResult[] = [];
  const rsiOversold: ScanResult[] = [];
  const volumeSurge: ScanResult[] = [];

  // 모든 종목 데이터를 병렬 조회
  const results = await Promise.allSettled(
    WATCH_LIST.map(async (item) => {
      const ohlcv = await fetchOHLCV(item.ticker, 120);
      return { item, ohlcv };
    })
  );

  for (const result of results) {
    if (result.status !== "fulfilled") continue;

    const { item, ohlcv } = result.value;
    if (ohlcv.length < LONG_MA + 1) continue;

    const closes = ohlcv.map((d) => d.close);
    const volumes = ohlcv.map((d) => d.volume);
    const price = closes[closes.length - 1];

    // 1. 골든크로스 체크
    const shortMA = calcMovingAverage(closes, SHORT_MA);
    const longMA = calcMovingAverage(closes, LONG_MA);
    const len = shortMA.length;
    if (len >= 2 && longMA.length >= 2) {
      const prevShort = shortMA[len - 2];
      const prevLong = longMA[longMA.length - 2];
      const currShort = shortMA[len - 1];
      const currLong = longMA[longMA.length - 1];
      if (
        prevShort !== null && prevLong !== null &&
        currShort !== null && currLong !== null &&
        prevShort <= prevLong && currShort > currLong
      ) {
        goldenCross.push({
          ticker: item.ticker,
          name: item.name,
          price,
          reason: `MA${SHORT_MA}(${currShort.toFixed(0)})이 MA${LONG_MA}(${currLong.toFixed(0)}) 상향 돌파`,
        });
      }
    }

    // 2. RSI 과매도 체크
    const rsiValues = calcRSI(closes);
    const lastRSI = rsiValues[rsiValues.length - 1];
    if (lastRSI !== null && lastRSI <= RSI_OVERSOLD) {
      rsiOversold.push({
        ticker: item.ticker,
        name: item.name,
        price,
        reason: `RSI ${lastRSI.toFixed(1)} (기준: ${RSI_OVERSOLD} 이하)`,
      });
    }

    // 3. 거래량 급증 체크 (평균 대비 3배 이상)
    const volRatio = calcVolumeRatio(volumes);
    if (volRatio >= 3.0) {
      volumeSurge.push({
        ticker: item.ticker,
        name: item.name,
        price,
        reason: `거래량 ${volRatio.toFixed(1)}배 (20일 평균 대비)`,
      });
    }
  }

  logApiRequest("GET", "/api/scanner", 200, Date.now() - start);
  return NextResponse.json({
    goldenCross: goldenCross.slice(0, 5),
    rsiOversold: rsiOversold.slice(0, 5),
    volumeSurge: volumeSurge.slice(0, 5),
  });
}
