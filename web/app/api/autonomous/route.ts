import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

const EMPTY_MARKET = {
  equity: [],
  daily_pnl: [],
  trades: [],
  summary: { total_trades: 0, win_rate: 0, total_pnl: 0, max_drawdown: 0 },
  updated_at: null,
}

export async function GET() {
  const dataPath = path.join(process.cwd(), 'public', 'data', 'autonomous.json')
  try {
    const raw = JSON.parse(fs.readFileSync(dataPath, 'utf-8'))

    // Support both new {kr, us} format and legacy flat format
    if (raw.kr !== undefined) {
      return NextResponse.json(raw)
    }

    // Legacy flat format: wrap everything under "kr"
    return NextResponse.json({
      kr: {
        equity: raw.equity ?? [],
        daily_pnl: raw.daily_pnl ?? [],
        trades: raw.recent_trades ?? [],
        summary: raw.summary ?? EMPTY_MARKET.summary,
        updated_at: raw.updated_at ?? null,
      },
      us: EMPTY_MARKET,
    })
  } catch {
    return NextResponse.json({ kr: EMPTY_MARKET, us: EMPTY_MARKET })
  }
}
