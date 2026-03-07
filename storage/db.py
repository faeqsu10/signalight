import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "signalight.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """DB 테이블을 생성한다 (이미 있으면 무시)."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            source TEXT NOT NULL,
            trigger_name TEXT NOT NULL,
            detail TEXT,
            price INTEGER,
            confluence_score REAL,
            confluence_direction TEXT,
            indicators_json TEXT
        );

        CREATE TABLE IF NOT EXISTS news_sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            sentiment TEXT,
            confidence REAL,
            summary TEXT,
            headlines_json TEXT
        );

        CREATE TABLE IF NOT EXISTS llm_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            verdict TEXT,
            confidence REAL,
            reasoning TEXT,
            input_json TEXT,
            model TEXT
        );

        CREATE TABLE IF NOT EXISTS watch_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'KRX',
            sector TEXT NOT NULL DEFAULT '',
            added_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_signal_ticker_date ON signal_history(ticker, created_at);
        CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_date ON news_sentiment(ticker, created_at);
        CREATE INDEX IF NOT EXISTS idx_llm_ticker_date ON llm_analysis(ticker, created_at);
        CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watch_list(active);
    """)

    # WATCH_LIST 초기 시드 데이터 마이그레이션
    _seed_watchlist(conn)

    conn.close()


def save_signals(stock_data: Dict) -> None:
    """분석 결과의 시그널들을 DB에 저장한다."""
    conn = _get_conn()
    ticker = stock_data.get("ticker", "")
    name = stock_data.get("name", "")
    price = stock_data.get("price", 0)
    score = stock_data.get("confluence_score", 0)
    direction = stock_data.get("confluence_direction", "")
    indicators = json.dumps(stock_data.get("indicators", {}), ensure_ascii=False)

    for sig in stock_data.get("signals", []):
        conn.execute(
            """INSERT INTO signal_history
               (ticker, name, signal_type, source, trigger_name, detail, price,
                confluence_score, confluence_direction, indicators_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, name, sig.get("type", ""), sig.get("source", ""),
             sig.get("trigger", ""), sig.get("detail", ""), price,
             score, direction, indicators),
        )
    conn.commit()
    conn.close()


def save_sentiment(ticker: str, name: str, sentiment_data: Optional[Dict]) -> None:
    """뉴스 감성 분석 결과를 DB에 저장한다."""
    if not sentiment_data:
        return
    conn = _get_conn()
    conn.execute(
        """INSERT INTO news_sentiment
           (ticker, name, sentiment, confidence, summary, headlines_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticker, name,
         sentiment_data.get("sentiment", ""),
         sentiment_data.get("confidence", 0.0),
         sentiment_data.get("summary", ""),
         json.dumps(sentiment_data.get("headlines", []), ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def save_llm_analysis(ticker: str, name: str, result: Dict, model: str) -> None:
    """LLM 종합 판단 결과를 DB에 저장한다."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO llm_analysis
           (ticker, name, verdict, confidence, reasoning, input_json, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ticker, name,
         result.get("verdict", ""),
         result.get("confidence", 0.0),
         result.get("reasoning", ""),
         json.dumps(result.get("input_data", {}), ensure_ascii=False),
         model),
    )
    conn.commit()
    conn.close()


_SEED_DATA = [
    ("005930", "삼성전자", "KRX", "반도체"),
    ("000660", "SK하이닉스", "KRX", "반도체"),
    ("373220", "LG에너지솔루션", "KRX", "2차전지"),
    ("006400", "삼성SDI", "KRX", "2차전지"),
    ("207940", "삼성바이오로직스", "KRX", "바이오"),
    ("068270", "셀트리온", "KRX", "바이오"),
    ("105560", "KB금융", "KRX", "금융"),
    ("005380", "현대차", "KRX", "자동차"),
    ("035420", "NAVER", "KRX", "IT/플랫폼"),
    ("035720", "카카오", "KRX", "IT/플랫폼"),
]


def _seed_watchlist(conn: sqlite3.Connection) -> None:
    """WATCH_LIST 시드 데이터를 watch_list 테이블에 삽입 (이미 있으면 무시)."""
    for ticker, name, market, sector in _SEED_DATA:
        conn.execute(
            """INSERT OR IGNORE INTO watch_list (ticker, name, market, sector)
               VALUES (?, ?, ?, ?)""",
            (ticker, name, market, sector),
        )
    conn.commit()


def get_active_watchlist() -> List[Tuple[str, str]]:
    """활성화된 감시 종목 리스트를 반환한다. [(ticker, name), ...]"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ticker, name FROM watch_list WHERE active = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return [(row["ticker"], row["name"]) for row in rows]


def add_to_watchlist(ticker: str, name: str, market: str = "KRX", sector: str = "") -> bool:
    """감시 종목을 추가한다. 이미 존재하면 active=1로 재활성화."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id, active FROM watch_list WHERE ticker = ?", (ticker,)
    ).fetchone()

    if existing:
        if existing["active"] == 0:
            conn.execute("UPDATE watch_list SET active = 1, name = ? WHERE ticker = ?", (name, ticker))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False  # 이미 활성 상태
    else:
        conn.execute(
            "INSERT INTO watch_list (ticker, name, market, sector) VALUES (?, ?, ?, ?)",
            (ticker, name, market, sector),
        )
        conn.commit()
        conn.close()
        return True


def remove_from_watchlist(ticker: str) -> bool:
    """감시 종목을 비활성화한다."""
    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE watch_list SET active = 0 WHERE ticker = ? AND active = 1", (ticker,)
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_all_watchlist() -> List[Dict]:
    """전체 감시 종목 리스트를 반환한다 (활성/비활성 모두)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ticker, name, market, sector, active FROM watch_list ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_signals(ticker: str, days: int = 30) -> List[Dict]:
    """최근 N일간의 시그널 이력을 조회한다."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM signal_history
           WHERE ticker = ? AND created_at >= datetime('now', 'localtime', ?)
           ORDER BY created_at DESC""",
        (ticker, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_sentiments(ticker: str, days: int = 7) -> List[Dict]:
    """최근 N일간의 감성 분석 이력을 조회한다."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM news_sentiment
           WHERE ticker = ? AND created_at >= datetime('now', 'localtime', ?)
           ORDER BY created_at DESC""",
        (ticker, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
