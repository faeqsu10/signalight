import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

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

        CREATE INDEX IF NOT EXISTS idx_signal_ticker_date ON signal_history(ticker, created_at);
        CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_date ON news_sentiment(ticker, created_at);
        CREATE INDEX IF NOT EXISTS idx_llm_ticker_date ON llm_analysis(ticker, created_at);
    """)
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
