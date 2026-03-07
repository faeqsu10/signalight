import { NextResponse } from "next/server";
import { fetchOHLCV } from "@/lib/yahoo-finance";
import { calcMovingAverage, calcRSI, calcMACD } from "@/lib/indicators";
import { SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT } from "@/lib/constants";

interface Trade {
  date: string;
  type: "buy" | "sell";
  price: number;
  source: string;
}

export async function GET(
  _request: Request,
  { params }: { params: { ticker: string } }
) {
  try {
    const { ticker } = params;
    const ohlcv = await fetchOHLCV(ticker, 365);

    if (ohlcv.length < LONG_MA + 1) {
      return NextResponse.json({ error: "데이터 부족" }, { status: 400 });
    }

    const closes = ohlcv.map((d) => d.close);
    const shortMA = calcMovingAverage(closes, SHORT_MA);
    const longMA = calcMovingAverage(closes, LONG_MA);
    const rsiValues = calcRSI(closes, RSI_PERIOD);
    const { macdLine, signalLine } = calcMACD(closes);

    // 시그널 기반 간이 백테스트
    const trades: Trade[] = [];
    let position = false; // 포지션 보유 여부
    let entryPrice = 0;
    let capital = 10000000; // 1000만원
    const initialCapital = capital;
    let wins = 0;
    let losses = 0;
    let peakCapital = capital;
    let maxDrawdown = 0;

    for (let i = LONG_MA; i < closes.length; i++) {
      const date = ohlcv[i].date;
      const price = closes[i];

      // 매수 시그널
      if (!position) {
        let buySignal = false;

        // MA 골든크로스
        if (shortMA[i - 1] !== null && longMA[i - 1] !== null &&
            shortMA[i] !== null && longMA[i] !== null &&
            shortMA[i - 1]! <= longMA[i - 1]! && shortMA[i]! > longMA[i]!) {
          buySignal = true;
        }
        // RSI 과매도
        if (rsiValues[i] !== null && rsiValues[i]! <= RSI_OVERSOLD) {
          buySignal = true;
        }
        // MACD 상향돌파
        if (macdLine[i - 1] !== null && signalLine[i - 1] !== null &&
            macdLine[i] !== null && signalLine[i] !== null &&
            macdLine[i - 1]! <= signalLine[i - 1]! && macdLine[i]! > signalLine[i]!) {
          buySignal = true;
        }

        if (buySignal) {
          position = true;
          entryPrice = price;
          trades.push({ date, type: "buy", price, source: "signal" });
        }
      }
      // 매도 시그널
      else {
        let sellSignal = false;

        // MA 데드크로스
        if (shortMA[i - 1] !== null && longMA[i - 1] !== null &&
            shortMA[i] !== null && longMA[i] !== null &&
            shortMA[i - 1]! >= longMA[i - 1]! && shortMA[i]! < longMA[i]!) {
          sellSignal = true;
        }
        // RSI 과매수
        if (rsiValues[i] !== null && rsiValues[i]! >= RSI_OVERBOUGHT) {
          sellSignal = true;
        }
        // MACD 하향돌파
        if (macdLine[i - 1] !== null && signalLine[i - 1] !== null &&
            macdLine[i] !== null && signalLine[i] !== null &&
            macdLine[i - 1]! >= signalLine[i - 1]! && macdLine[i]! < signalLine[i]!) {
          sellSignal = true;
        }

        if (sellSignal) {
          position = false;
          const returnPct = (price - entryPrice) / entryPrice;
          capital *= (1 + returnPct);
          if (returnPct > 0) wins++;
          else losses++;
          trades.push({ date, type: "sell", price, source: "signal" });
        }
      }

      // MDD 계산
      if (capital > peakCapital) peakCapital = capital;
      const drawdown = ((peakCapital - capital) / peakCapital) * 100;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }

    // 미청산 포지션 처리
    if (position) {
      const lastPrice = closes[closes.length - 1];
      const returnPct = (lastPrice - entryPrice) / entryPrice;
      capital *= (1 + returnPct);
      if (returnPct > 0) wins++;
      else losses++;
    }

    const totalTrades = wins + losses;
    const totalReturnPct = ((capital - initialCapital) / initialCapital) * 100;
    const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;

    return NextResponse.json({
      ticker,
      period: "1Y",
      initialCapital,
      finalCapital: Math.round(capital),
      totalReturnPct: Number(totalReturnPct.toFixed(2)),
      maxDrawdownPct: Number(maxDrawdown.toFixed(2)),
      totalTrades,
      wins,
      losses,
      winRate: Number(winRate.toFixed(1)),
      trades: trades.slice(-10), // 최근 10건만
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
