"""
SQLite storage for MarketPulse.

Kept deliberately simple: one table of daily OHLCV rows, keyed by
(symbol, date) so re-ingesting the same day is an upsert, not a duplicate.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable, List, Tuple


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL NOT NULL,
            volume REAL,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.commit()
    return conn


def upsert_rows(conn: sqlite3.Connection, symbol: str, rows: Iterable[dict]) -> int:
    """Insert or update price rows for a symbol. Returns the number of
    rows written."""
    written = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO prices (symbol, date, open, high, low, close, volume)
            VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
            """,
            {"symbol": symbol, **row},
        )
        written += 1
    conn.commit()
    return written


def get_symbols(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol")
    return [r[0] for r in cur.fetchall()]


def get_closes(conn: sqlite3.Connection, symbol: str, limit: int = 90) -> List[Tuple[str, float]]:
    """Returns (date, close) pairs for a symbol, oldest first, capped at
    the most recent `limit` rows."""
    cur = conn.execute(
        """
        SELECT date, close FROM (
            SELECT date, close FROM prices
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
        ) ORDER BY date ASC
        """,
        (symbol, limit),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]
