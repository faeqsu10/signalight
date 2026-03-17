import fs from "fs";
import path from "path";
import Database from "better-sqlite3";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

type MarketKey = "kr" | "us" | "us_meanrev";

interface MarketData {
  equity: Array<{
    date: string;
    total: number;
    invested: number;
    cash: number;
    positions: number;
  }>;
  daily_pnl: Array<{
    date: string;
    pnl: number;
    trades: number;
    wins: number;
    losses: number;
  }>;
  trades: Array<{
    date: string;
    ticker: string;
    name: string;
    side: string;
    quantity: number;
    price: number;
    amount: number;
    status: string;
    reason: string | null;
    pnl_pct: number | null;
    pnl_amount: number | null;
  }>;
  current_positions: Array<{
    ticker: string;
    name: string;
    phase: number;
    entry_price: number;
    entry_date: string;
    stop_loss: number;
    target1: number;
    target2: number;
    highest_close: number;
    weight_pct: number;
    remaining_pct: number;
  }>;
  summary: {
    total_trades: number;
    win_rate: number;
    total_pnl: number;
    max_drawdown: number;
  };
  updated_at: string | null;
}

const MARKET_CONFIG: Record<MarketKey, { dbFile: string; isUsd: boolean }> = {
  kr: { dbFile: "signalight.db", isUsd: false },
  us: { dbFile: "signalight_us.db", isUsd: true },
  us_meanrev: { dbFile: "signalight_us_meanrev.db", isUsd: true },
};

const EMPTY_SUMMARY = {
  total_trades: 0,
  win_rate: 0,
  total_pnl: 0,
  max_drawdown: 0,
};

const EMPTY_MARKET: MarketData = {
  equity: [],
  daily_pnl: [],
  trades: [],
  current_positions: [],
  summary: EMPTY_SUMMARY,
  updated_at: null,
};

function storagePath(dbFile: string) {
  return path.join(process.cwd(), "..", "storage", dbFile);
}

function jsonFallbackPath() {
  return path.join(process.cwd(), "public", "data", "autonomous.json");
}

function normalizeMoney(value: number | null | undefined, isUsd: boolean) {
  if (value === null || value === undefined) return null;
  return isUsd ? value / 100 : value;
}

function tableExists(db: Database.Database, table: string) {
  const row = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?")
    .get(table);
  return Boolean(row);
}

function calcMaxDrawdown(equity: Array<{ total: number }>) {
  if (equity.length === 0) return 0;

  let peak = equity[0].total;
  let maxDrawdown = 0;

  for (const point of equity) {
    if (point.total > peak) peak = point.total;
    if (peak <= 0) continue;

    const drawdown = ((peak - point.total) / peak) * 100;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
    }
  }

  return Number(maxDrawdown.toFixed(2));
}

function readMarketFromDb(market: MarketKey): MarketData | null {
  const { dbFile, isUsd } = MARKET_CONFIG[market];
  const dbPath = storagePath(dbFile);

  if (!fs.existsSync(dbPath)) {
    return null;
  }

  const db = new Database(dbPath, { readonly: true });

  try {
    const equity = tableExists(db, "auto_equity_snapshots")
      ? (db
          .prepare(
            `
              SELECT snapshot_date, total_equity, invested_amount, cash_amount, open_positions
              FROM auto_equity_snapshots
              ORDER BY snapshot_date ASC
            `
          )
          .all() as Array<{
          snapshot_date: string;
          total_equity: number;
          invested_amount: number;
          cash_amount: number;
          open_positions: number;
        }>).map((row) => ({
          date: row.snapshot_date,
          total: normalizeMoney(row.total_equity, isUsd) ?? 0,
          invested: normalizeMoney(row.invested_amount, isUsd) ?? 0,
          cash: normalizeMoney(row.cash_amount, isUsd) ?? 0,
          positions: row.open_positions,
        }))
      : [];

    const dailyPnl = tableExists(db, "auto_daily_pnl")
      ? (db
          .prepare(
            `
              SELECT trade_date, realized_pnl, trades_count, wins, losses
              FROM auto_daily_pnl
              ORDER BY trade_date ASC
            `
          )
          .all() as Array<{
          trade_date: string;
          realized_pnl: number;
          trades_count: number;
          wins: number;
          losses: number;
        }>).map((row) => ({
          date: row.trade_date,
          pnl: normalizeMoney(row.realized_pnl, isUsd) ?? 0,
          trades: row.trades_count,
          wins: row.wins,
          losses: row.losses,
        }))
      : [];

    const trades = tableExists(db, "auto_trade_log")
      ? (db
          .prepare(
            `
              SELECT trade_date, ticker, name, side, quantity, price, amount,
                     status, reason, pnl_pct, pnl_amount
              FROM auto_trade_log
              ORDER BY id DESC
              LIMIT 30
            `
          )
          .all() as Array<{
          trade_date: string;
          ticker: string;
          name: string;
          side: string;
          quantity: number;
          price: number;
          amount: number;
          status: string;
          reason: string | null;
          pnl_pct: number | null;
          pnl_amount: number | null;
        }>).map((row) => ({
          date: row.trade_date,
          ticker: row.ticker,
          name: row.name,
          side: row.side,
          quantity: row.quantity,
          price: normalizeMoney(row.price, isUsd) ?? 0,
          amount: normalizeMoney(row.amount, isUsd) ?? 0,
          status: row.status,
          reason: row.reason,
          pnl_pct: row.pnl_pct,
          pnl_amount: normalizeMoney(row.pnl_amount, isUsd),
        }))
      : [];

    const currentPositions = tableExists(db, "virtual_positions")
      ? (db
          .prepare(
            `
              SELECT ticker, name, phase, entry_price, entry_date, stop_loss, target1,
                     target2, highest_close, weight_pct, remaining_pct
              FROM virtual_positions
              WHERE status = 'open'
              ORDER BY entry_date ASC, id ASC
            `
          )
          .all() as Array<{
          ticker: string;
          name: string;
          phase: number;
          entry_price: number;
          entry_date: string;
          stop_loss: number;
          target1: number;
          target2: number;
          highest_close: number;
          weight_pct: number;
          remaining_pct: number;
        }>)
      : [];

    const totals = tableExists(db, "auto_trade_log")
      ? (db
          .prepare(
            `
              SELECT
                SUM(CASE WHEN side = 'sell' AND pnl_amount IS NOT NULL THEN 1 ELSE 0 END) AS total_trades,
                SUM(CASE WHEN side = 'sell' AND pnl_amount > 0 THEN 1 ELSE 0 END) AS total_wins,
                SUM(CASE WHEN side = 'sell' AND pnl_amount IS NOT NULL THEN pnl_amount ELSE 0 END) AS total_pnl
              FROM auto_trade_log
            `
          )
          .get() as {
          total_trades: number | null;
          total_wins: number | null;
          total_pnl: number | null;
        })
      : { total_trades: 0, total_wins: 0, total_pnl: 0 };

    const totalTrades = totals.total_trades ?? 0;
    const winRate =
      totalTrades > 0
        ? Number((((totals.total_wins ?? 0) / totalTrades) * 100).toFixed(1))
        : 0;

    return {
      equity,
      daily_pnl: dailyPnl,
      trades,
      current_positions: currentPositions,
      summary: {
        total_trades: totalTrades,
        win_rate: winRate,
        total_pnl: normalizeMoney(totals.total_pnl, isUsd) ?? 0,
        max_drawdown: calcMaxDrawdown(equity),
      },
      updated_at: new Date().toISOString(),
    };
  } finally {
    db.close();
  }
}

function readJsonFallback(): Record<MarketKey, MarketData> {
  const fallback = jsonFallbackPath();

  if (!fs.existsSync(fallback)) {
    return {
      kr: EMPTY_MARKET,
      us: EMPTY_MARKET,
      us_meanrev: EMPTY_MARKET,
    };
  }

  const raw = JSON.parse(fs.readFileSync(fallback, "utf-8"));

  if (raw.kr !== undefined) {
    return {
      kr: raw.kr ?? EMPTY_MARKET,
      us: raw.us ?? EMPTY_MARKET,
      us_meanrev: raw.us_meanrev ?? EMPTY_MARKET,
    };
  }

  return {
    kr: {
      equity: raw.equity ?? [],
      daily_pnl: raw.daily_pnl ?? [],
      trades: raw.recent_trades ?? [],
      current_positions: raw.current_positions ?? [],
      summary: raw.summary ?? EMPTY_SUMMARY,
      updated_at: raw.updated_at ?? null,
    },
    us: EMPTY_MARKET,
    us_meanrev: EMPTY_MARKET,
  };
}

export async function GET() {
  const fallback = readJsonFallback();

  return NextResponse.json({
    kr: readMarketFromDb("kr") ?? fallback.kr,
    us: readMarketFromDb("us") ?? fallback.us,
    us_meanrev: readMarketFromDb("us_meanrev") ?? fallback.us_meanrev,
  });
}
