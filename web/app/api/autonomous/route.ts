import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET() {
  const dataPath = path.join(process.cwd(), 'public', 'data', 'autonomous.json')
  try {
    const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'))
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({
      updated_at: null,
      equity: [],
      daily_pnl: [],
      recent_trades: [],
      summary: { total_trades: 0, win_rate: 0, total_pnl: 0, max_drawdown: 0 },
    })
  }
}
