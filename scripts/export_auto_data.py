"""자율매매 DB 데이터를 웹 대시보드용 JSON으로 export한다.

Usage:
    python3 scripts/export_auto_data.py

Output:
    web/public/data/autonomous.json

JSON 구조:
    {
      "kr": { "equity": [...], "daily_pnl": [...], "trades": [...],
               "summary": {...}, "updated_at": "..." },
      "us": { "equity": [...], "daily_pnl": [...], "trades": [...],
               "summary": {...}, "updated_at": "..." }
    }
"""

import json
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KR_DB_PATH = os.path.join(BASE_DIR, "storage", "signalight.db")
US_DB_PATH = os.path.join(BASE_DIR, "storage", "signalight_us.db")
OUT_PATH = os.path.join(BASE_DIR, "web", "public", "data", "autonomous.json")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _calc_summary(equity, daily_pnl):
    """equity 커브와 daily_pnl로 요약 통계를 계산한다."""
    total_trades = sum(d["trades"] for d in daily_pnl)
    total_wins = sum(d["wins"] for d in daily_pnl)
    total_pnl = sum(d["pnl"] for d in daily_pnl)
    win_rate = round(total_wins / total_trades * 100, 1) if total_trades > 0 else 0.0

    max_drawdown = 0.0
    if equity:
        peak = equity[0]["total"]
        for e in equity:
            if e["total"] > peak:
                peak = e["total"]
            if peak > 0:
                dd = (peak - e["total"]) / peak * 100
                if dd > max_drawdown:
                    max_drawdown = dd

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "max_drawdown": round(max_drawdown, 2),
    }


def _export_market(db_path: str, label: str) -> dict:
    """하나의 DB에서 equity, daily_pnl, trades를 추출한다."""
    if not os.path.exists(db_path):
        print(f"  {label}: DB 없음 ({db_path})")
        return {
            "equity": [],
            "daily_pnl": [],
            "trades": [],
            "summary": _calc_summary([], []),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    conn = _connect(db_path)

    # ── equity snapshots ──
    equity = []
    if _table_exists(conn, "auto_equity_snapshots"):
        rows = conn.execute(
            """
            SELECT snapshot_date, total_equity, invested_amount, cash_amount, open_positions
            FROM auto_equity_snapshots
            ORDER BY snapshot_date ASC
            """
        ).fetchall()
        equity = [
            {
                "date": row["snapshot_date"],
                "total": row["total_equity"],
                "invested": row["invested_amount"],
                "cash": row["cash_amount"],
                "positions": row["open_positions"],
            }
            for row in rows
        ]

    # ── daily PnL ──
    daily_pnl = []
    if _table_exists(conn, "auto_daily_pnl"):
        rows = conn.execute(
            """
            SELECT trade_date, realized_pnl, trades_count, wins, losses
            FROM auto_daily_pnl
            ORDER BY trade_date ASC
            """
        ).fetchall()
        daily_pnl = [
            {
                "date": row["trade_date"],
                "pnl": row["realized_pnl"],
                "trades": row["trades_count"],
                "wins": row["wins"],
                "losses": row["losses"],
            }
            for row in rows
        ]

    # ── recent trades (최근 30건) ──
    recent_trades = []
    if _table_exists(conn, "auto_trade_log"):
        rows = conn.execute(
            """
            SELECT trade_date, ticker, name, side, quantity, price, amount,
                   status, reason, pnl_pct, pnl_amount
            FROM auto_trade_log
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()
        recent_trades = [
            {
                "date": row["trade_date"],
                "ticker": row["ticker"],
                "name": row["name"],
                "side": row["side"],
                "quantity": row["quantity"],
                "price": row["price"],
                "amount": row["amount"],
                "status": row["status"],
                "reason": row["reason"],
                "pnl_pct": row["pnl_pct"],
                "pnl_amount": row["pnl_amount"],
            }
            for row in rows
        ]

    conn.close()

    summary = _calc_summary(equity, daily_pnl)
    print(f"  {label} equity: {len(equity)}건, daily_pnl: {len(daily_pnl)}건, trades: {len(recent_trades)}건")

    return {
        "equity": equity,
        "daily_pnl": daily_pnl,
        "trades": recent_trades,
        "summary": summary,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def export() -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    kr_data = _export_market(KR_DB_PATH, "KR")
    us_data = _export_market(US_DB_PATH, "US")

    data = {
        "kr": kr_data,
        "us": us_data,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[export_auto_data] 저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    export()
