"""
가상 포지션 추적기

실제 주문 없이 매매 추천 시뮬레이션용 포지션을 SQLite에 기록한다.
매수 추천 시 가상 포지션 생성, 매도 추천 시 가상 포지션 청산.
"""

import sqlite3
import os
import json
from datetime import datetime, date
from typing import Dict, List, Optional


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "signalight.db")


def _get_conn(db_path: str = "") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables(db_path: str = "") -> None:
    """가상 포지션 테이블을 생성한다."""
    conn = _get_conn(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS virtual_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            phase INTEGER NOT NULL DEFAULT 1,
            entry_price INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            entry_atr REAL NOT NULL DEFAULT 0,
            entry_regime TEXT NOT NULL DEFAULT 'sideways',
            stop_loss INTEGER NOT NULL DEFAULT 0,
            target1 INTEGER NOT NULL DEFAULT 0,
            target2 INTEGER NOT NULL DEFAULT 0,
            target1_hit INTEGER NOT NULL DEFAULT 0,
            target2_hit INTEGER NOT NULL DEFAULT 0,
            highest_close INTEGER NOT NULL DEFAULT 0,
            weight_pct REAL NOT NULL DEFAULT 0,
            remaining_pct REAL NOT NULL DEFAULT 100.0,
            exit_price INTEGER,
            exit_date TEXT,
            exit_reason TEXT,
            pnl_pct REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_vp_ticker_status
            ON virtual_positions(ticker, status);
    """)
    # 기존 DB에 컬럼이 없으면 추가
    try:
        conn.execute("ALTER TABLE virtual_positions ADD COLUMN remaining_pct REAL NOT NULL DEFAULT 100.0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 이미 존재
    conn.close()


# 모듈 로드 시 테이블 생성
_init_tables()


class PositionTracker:
    """가상 포지션 추적기."""

    def __init__(self, db_path: str = ""):
        self._db_path = db_path
        _init_tables(db_path)

    def _conn(self) -> sqlite3.Connection:
        return _get_conn(self._db_path)

    def open_position(
        self,
        ticker: str,
        name: str,
        entry_price: int,
        entry_atr: float,
        regime: str,
        stop_loss: int,
        target1: int,
        target2: int,
        weight_pct: float,
    ) -> int:
        """새 가상 포지션을 생성한다.

        Returns:
            생성된 포지션 ID
        """
        conn = self._conn()
        cursor = conn.execute(
            """INSERT INTO virtual_positions
               (ticker, name, phase, entry_price, entry_date, entry_atr,
                entry_regime, stop_loss, target1, target2, highest_close, weight_pct,
                remaining_pct)
               VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 100.0)""",
            (ticker, name, entry_price, date.today().isoformat(),
             entry_atr, regime, stop_loss, target1, target2,
             entry_price, weight_pct),
        )
        conn.commit()
        pos_id = cursor.lastrowid
        conn.close()
        return pos_id

    def get_position(self, ticker: str) -> Optional[Dict]:
        """해당 종목의 활성 포지션을 조회한다."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM virtual_positions WHERE ticker = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        conn.close()

        if row is None:
            return None
        return dict(row)

    def get_all_open(self) -> List[Dict]:
        """모든 활성 포지션을 조회한다."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM virtual_positions WHERE status = 'open' ORDER BY entry_date",
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_phase(self, ticker: str, new_phase: int, additional_weight: float = 0) -> None:
        """분할 매수 단계를 업데이트한다."""
        conn = self._conn()
        conn.execute(
            """UPDATE virtual_positions
               SET phase = ?, weight_pct = weight_pct + ?,
                   updated_at = datetime('now', 'localtime')
               WHERE ticker = ? AND status = 'open'""",
            (new_phase, additional_weight, ticker),
        )
        conn.commit()
        conn.close()

    def update_highest_close(self, ticker: str, close_price: int) -> None:
        """최고 종가를 갱신한다 (트레일링 스탑용)."""
        conn = self._conn()
        conn.execute(
            """UPDATE virtual_positions
               SET highest_close = MAX(highest_close, ?),
                   updated_at = datetime('now', 'localtime')
               WHERE ticker = ? AND status = 'open'""",
            (close_price, ticker),
        )
        conn.commit()
        conn.close()

    def mark_target_hit(self, ticker: str, target_num: int) -> None:
        """목표가 도달을 기록한다."""
        col = f"target{target_num}_hit"
        conn = self._conn()
        conn.execute(
            f"""UPDATE virtual_positions
                SET {col} = 1, updated_at = datetime('now', 'localtime')
                WHERE ticker = ? AND status = 'open'""",
            (ticker,),
        )
        conn.commit()
        conn.close()

    def partial_sell(self, ticker: str, sell_pct: float) -> Optional[Dict]:
        """분할 매도 후 잔여 비율을 업데이트한다.

        Args:
            ticker: 종목 코드
            sell_pct: 매도 비율 (예: 33 = 33%)

        Returns:
            업데이트된 포지션 정보 (없으면 None)
        """
        position = self.get_position(ticker)
        if position is None:
            return None

        current_remaining = position.get("remaining_pct", 100.0)
        new_remaining = max(0.0, current_remaining - sell_pct)

        conn = self._conn()
        conn.execute(
            """UPDATE virtual_positions
               SET remaining_pct = ?, updated_at = datetime('now', 'localtime')
               WHERE ticker = ? AND status = 'open'""",
            (round(new_remaining, 1), ticker),
        )
        conn.commit()
        conn.close()

        position["remaining_pct"] = round(new_remaining, 1)
        return position

    def update_stop_loss(self, ticker: str, new_stop: int) -> None:
        """손절가를 갱신한다."""
        conn = self._conn()
        conn.execute(
            """UPDATE virtual_positions
               SET stop_loss = ?, updated_at = datetime('now', 'localtime')
               WHERE ticker = ? AND status = 'open'""",
            (new_stop, ticker),
        )
        conn.commit()
        conn.close()

    def close_position(
        self,
        ticker: str,
        exit_price: int,
        exit_reason: str,
    ) -> Optional[Dict]:
        """가상 포지션을 청산한다.

        Returns:
            청산된 포지션 정보 (없으면 None)
        """
        position = self.get_position(ticker)
        if position is None:
            return None

        # remaining_pct가 0 이하면 이미 전량 분할매도된 포지션
        remaining = position.get("remaining_pct", 100.0)
        if remaining <= 0:
            exit_reason = exit_reason or "partial_sell_complete"

        entry_price = position["entry_price"]
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        conn = self._conn()
        conn.execute(
            """UPDATE virtual_positions
               SET status = 'closed', exit_price = ?, exit_date = ?,
                   exit_reason = ?, pnl_pct = ?,
                   updated_at = datetime('now', 'localtime')
               WHERE ticker = ? AND status = 'open'""",
            (exit_price, date.today().isoformat(), exit_reason,
             round(pnl_pct, 2), ticker),
        )
        conn.commit()
        conn.close()

        position["exit_price"] = exit_price
        position["exit_date"] = date.today().isoformat()
        position["exit_reason"] = exit_reason
        position["pnl_pct"] = round(pnl_pct, 2)
        return position

    def get_closed_positions(self, limit: int = 20) -> List[Dict]:
        """최근 청산된 포지션 이력을 조회한다."""
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM virtual_positions
               WHERE status = 'closed'
               ORDER BY exit_date DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_performance_summary(self) -> Dict:
        """전체 가상 매매 성과 요약을 반환한다."""
        conn = self._conn()

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM virtual_positions WHERE status = 'closed'"
        ).fetchone()["cnt"]

        if total == 0:
            conn.close()
            return {
                "total_trades": 0,
                "win_rate": 0,
                "avg_pnl_pct": 0,
                "total_pnl_pct": 0,
                "best_trade_pct": 0,
                "worst_trade_pct": 0,
            }

        stats = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
                AVG(pnl_pct) as avg_pnl,
                SUM(pnl_pct) as total_pnl,
                MAX(pnl_pct) as best,
                MIN(pnl_pct) as worst
               FROM virtual_positions WHERE status = 'closed'"""
        ).fetchone()

        conn.close()

        return {
            "total_trades": stats["total"],
            "win_rate": round((stats["wins"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0,
            "avg_pnl_pct": round(stats["avg_pnl"] or 0, 2),
            "total_pnl_pct": round(stats["total_pnl"] or 0, 2),
            "best_trade_pct": round(stats["best"] or 0, 2),
            "worst_trade_pct": round(stats["worst"] or 0, 2),
        }
