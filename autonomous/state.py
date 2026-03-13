"""파이프라인 상태 관리 — SQLite 기반 영속 상태.

일일 PnL, 주간 PnL, 연속 손실, 에퀴티 스냅샷을 추적한다.
서킷 브레이커 판단에 사용된다.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

# 기본 KR DB 경로
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "storage", "signalight.db"
)

# US 전용 DB 경로
US_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "storage", "signalight_us.db"
)


def _get_conn(db_path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables(db_path: str = None) -> None:
    """자율 트레이딩 전용 테이블을 생성한다."""
    conn = _get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS auto_daily_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL UNIQUE,
            realized_pnl INTEGER NOT NULL DEFAULT 0,
            trades_count INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS auto_equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL UNIQUE,
            total_equity INTEGER NOT NULL DEFAULT 0,
            invested_amount INTEGER NOT NULL DEFAULT 0,
            cash_amount INTEGER NOT NULL DEFAULT 0,
            open_positions INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS auto_trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            order_type TEXT NOT NULL DEFAULT 'market',
            status TEXT NOT NULL DEFAULT 'pending',
            order_id TEXT,
            reason TEXT,
            confluence_score REAL,
            regime TEXT,
            pnl_amount INTEGER,
            pnl_pct REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS auto_circuit_breaker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT NOT NULL,
            trigger_date TEXT NOT NULL,
            resume_date TEXT,
            detail TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_auto_pnl_date
            ON auto_daily_pnl(trade_date);
        CREATE INDEX IF NOT EXISTS idx_auto_equity_date
            ON auto_equity_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_auto_trade_date
            ON auto_trade_log(trade_date);
    """)
    conn.close()


# KR 테이블 초기화
_init_tables(DEFAULT_DB_PATH)


class PipelineState:
    """자율 트레이딩 파이프라인 상태 관리.

    Args:
        db_path: SQLite DB 경로. 기본값은 KR용 signalight.db.
                 US는 signalight_us.db를 사용한다.
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or DEFAULT_DB_PATH
        if db_path and db_path != DEFAULT_DB_PATH:
            _init_tables(db_path)

    def _conn(self) -> sqlite3.Connection:
        return _get_conn(self._db_path)

    # ── 일일 PnL ──

    def record_daily_pnl(
        self, trade_date: str, realized_pnl: int,
        trades: int, wins: int, losses: int
    ) -> None:
        """일일 PnL을 기록한다."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO auto_daily_pnl
               (trade_date, realized_pnl, trades_count, wins, losses)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(trade_date) DO UPDATE SET
                   realized_pnl = ?,
                   trades_count = ?,
                   wins = ?,
                   losses = ?""",
            (trade_date, realized_pnl, trades, wins, losses,
             realized_pnl, trades, wins, losses),
        )
        conn.commit()
        conn.close()

    def get_daily_pnl(self, trade_date: str) -> Optional[Dict]:
        """특정 일자의 PnL을 조회한다."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM auto_daily_pnl WHERE trade_date = ?",
            (trade_date,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_weekly_pnl(self, end_date: str = None) -> Dict:
        """최근 5영업일 누적 PnL을 계산한다."""
        if end_date is None:
            end_date = date.today().isoformat()
        start = (date.fromisoformat(end_date) - timedelta(days=7)).isoformat()

        conn = self._conn()
        row = conn.execute(
            """SELECT
                COALESCE(SUM(realized_pnl), 0) as total_pnl,
                COALESCE(SUM(trades_count), 0) as total_trades,
                COALESCE(SUM(wins), 0) as total_wins,
                COALESCE(SUM(losses), 0) as total_losses
               FROM auto_daily_pnl
               WHERE trade_date BETWEEN ? AND ?""",
            (start, end_date),
        ).fetchone()
        conn.close()
        return dict(row)

    # ── 연속 손실 ──

    def get_consecutive_losses(self) -> int:
        """최근 연속 패배 횟수를 계산한다."""
        conn = self._conn()
        rows = conn.execute(
            """SELECT side, pnl_amount FROM auto_trade_log
               WHERE side = 'sell' AND pnl_amount IS NOT NULL
               ORDER BY id DESC LIMIT 20"""
        ).fetchall()
        conn.close()

        count = 0
        for row in rows:
            if row["pnl_amount"] is not None and row["pnl_amount"] < 0:
                count += 1
            else:
                break
        return count

    # ── 에퀴티 스냅샷 ──

    def save_equity_snapshot(
        self, total_equity: int, invested: int,
        cash: int, open_positions: int
    ) -> None:
        """에퀴티 스냅샷을 저장한다."""
        today = date.today().isoformat()
        conn = self._conn()
        conn.execute(
            """INSERT INTO auto_equity_snapshots
               (snapshot_date, total_equity, invested_amount,
                cash_amount, open_positions)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(snapshot_date) DO UPDATE SET
                   total_equity = ?,
                   invested_amount = ?,
                   cash_amount = ?,
                   open_positions = ?""",
            (today, total_equity, invested, cash, open_positions,
             total_equity, invested, cash, open_positions),
        )
        conn.commit()
        conn.close()

    def get_max_drawdown(self) -> float:
        """최대 낙폭(%)을 계산한다."""
        conn = self._conn()
        rows = conn.execute(
            """SELECT total_equity FROM auto_equity_snapshots
               ORDER BY snapshot_date"""
        ).fetchall()
        conn.close()

        if not rows:
            return 0.0

        peak = 0
        max_dd = 0.0
        for row in rows:
            equity = row["total_equity"]
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        return round(max_dd, 2)

    def get_equity_history(self, days: int = 30) -> List[Dict]:
        """최근 N일 에퀴티 이력을 반환한다."""
        start = (date.today() - timedelta(days=days)).isoformat()
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM auto_equity_snapshots
               WHERE snapshot_date >= ?
               ORDER BY snapshot_date""",
            (start,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── 매매 로그 ──

    def log_trade(
        self, ticker: str, name: str, side: str,
        quantity: int, price: int, order_type: str = "market",
        status: str = "filled", order_id: str = "",
        reason: str = "", confluence_score: float = 0,
        regime: str = "", pnl_amount: int = None,
        pnl_pct: float = None
    ) -> None:
        """매매를 기록한다."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO auto_trade_log
               (trade_date, ticker, name, side, quantity, price, amount,
                order_type, status, order_id, reason,
                confluence_score, regime, pnl_amount, pnl_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date.today().isoformat(), ticker, name, side,
             quantity, price, quantity * price,
             order_type, status, order_id, reason,
             confluence_score, regime, pnl_amount, pnl_pct),
        )
        conn.commit()
        conn.close()

    def get_recent_trades(self, days: int = 30) -> List[Dict]:
        """최근 N일 매매 이력을 반환한다."""
        start = (date.today() - timedelta(days=days)).isoformat()
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM auto_trade_log
               WHERE trade_date >= ?
               ORDER BY id DESC""",
            (start,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── 서킷 브레이커 ──

    def record_circuit_breaker(
        self, trigger_type: str, resume_date: str = None,
        detail: str = ""
    ) -> None:
        """서킷 브레이커 발동을 기록한다."""
        conn = self._conn()
        conn.execute(
            """INSERT INTO auto_circuit_breaker
               (trigger_type, trigger_date, resume_date, detail)
               VALUES (?, ?, ?, ?)""",
            (trigger_type, date.today().isoformat(), resume_date, detail),
        )
        conn.commit()
        conn.close()

    def is_circuit_breaker_active(self) -> Optional[Dict]:
        """활성 서킷 브레이커가 있으면 반환한다."""
        today = date.today().isoformat()
        conn = self._conn()
        row = conn.execute(
            """SELECT * FROM auto_circuit_breaker
               WHERE resume_date IS NULL OR resume_date > ?
               ORDER BY id DESC LIMIT 1""",
            (today,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── 성과 요약 ──

    def get_performance_summary(self, days: int = 30) -> Dict:
        """기간별 성과 요약을 반환한다."""
        start = (date.today() - timedelta(days=days)).isoformat()
        conn = self._conn()

        trades = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl_amount > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_amount < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(AVG(pnl_pct), 0) as avg_pnl_pct,
                COALESCE(SUM(pnl_amount), 0) as total_pnl,
                COALESCE(MAX(pnl_pct), 0) as best_pct,
                COALESCE(MIN(pnl_pct), 0) as worst_pct
               FROM auto_trade_log
               WHERE side = 'sell' AND pnl_amount IS NOT NULL
                 AND trade_date >= ?""",
            (start,),
        ).fetchone()

        conn.close()

        total = trades["total"] or 0
        wins = trades["wins"] or 0

        return {
            "period_days": days,
            "total_trades": total,
            "wins": wins,
            "losses": trades["losses"] or 0,
            "win_rate": round((wins / total * 100) if total > 0 else 0, 1),
            "avg_pnl_pct": round(trades["avg_pnl_pct"] or 0, 2),
            "total_pnl": trades["total_pnl"] or 0,
            "best_trade_pct": round(trades["best_pct"] or 0, 2),
            "worst_trade_pct": round(trades["worst_pct"] or 0, 2),
            "max_drawdown_pct": self.get_max_drawdown(),
            "consecutive_losses": self.get_consecutive_losses(),
        }
