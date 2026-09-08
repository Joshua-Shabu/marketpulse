"""
MarketPulse API — a small FastAPI service exposing commodity/economic price
data (from the Federal Reserve's public FRED API) and derived analytics
(moving average, volatility, daily return).

Run locally (after `pip install -r requirements.txt` and setting
FRED_API_KEY — see .env.example):
    uvicorn app.main:app --reload

Then, for example (DCOILWTICO = WTI crude oil, a daily FRED series):
    curl http://127.0.0.1:8000/symbols
    curl -X POST http://127.0.0.1:8000/ingest/DCOILWTICO
    curl http://127.0.0.1:8000/prices/DCOILWTICO
    curl http://127.0.0.1:8000/analytics/DCOILWTICO
"""
from __future__ import annotations

import os
import sqlite3
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import db, ingest
from .analytics import daily_returns, moving_average, rolling_volatility, latest_summary

load_dotenv()  # reads FRED_API_KEY (and anything else) from a local .env file

DB_PATH = os.environ.get("MARKETPULSE_DB", "marketpulse.db")

app = FastAPI(
    title="MarketPulse",
    description="ETL + analytics API for daily commodity/market price data.",
    version="0.1.0",
)


def get_conn() -> sqlite3.Connection:
    # A fresh connection per request keeps this simple and safe for a
    # small demo service; a production version would use a connection
    # pool instead.
    return db.init_db(DB_PATH)


class PricePoint(BaseModel):
    date: str
    close: float


class AnalyticsResponse(BaseModel):
    symbol: str
    latest_close: Optional[float]
    moving_average: Optional[float]
    volatility: Optional[float]
    daily_return: Optional[float]
    window: int


class IngestResponse(BaseModel):
    symbol: str
    rows_written: int


@app.get("/symbols", response_model=List[str])
def list_symbols():
    """All symbols that have at least one row of data ingested."""
    conn = get_conn()
    try:
        return db.get_symbols(conn)
    finally:
        conn.close()


@app.post("/ingest/{symbol}", response_model=IngestResponse)
def ingest_symbol(symbol: str):
    """Trigger a fresh Extract-Transform-Load run for one FRED series
    (e.g. DCOILWTICO for WTI crude oil). `symbol` here is a FRED series ID."""
    conn = get_conn()
    try:
        try:
            rows_written = ingest.run_ingest(symbol, conn)
        except ValueError as exc:
            # Missing/misconfigured API key is a client-side setup problem (400);
            # a real HTTPException from FastAPI itself should just pass through.
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            raise
        except Exception as exc:  # network/HTTP errors from requests, bad series_id, etc.
            raise HTTPException(status_code=502, detail=f"Failed to fetch data: {exc}")
        return IngestResponse(symbol=symbol, rows_written=rows_written)
    finally:
        conn.close()


@app.get("/prices/{symbol}", response_model=List[PricePoint])
def get_prices(symbol: str, limit: int = Query(90, ge=1, le=2000)):
    """Raw (date, close) history for a symbol, oldest first."""
    conn = get_conn()
    try:
        rows = db.get_closes(conn, symbol, limit=limit)
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No data for '{symbol}' yet — POST /ingest/{symbol} first.",
            )
        return [PricePoint(date=d, close=c) for d, c in rows]
    finally:
        conn.close()


@app.get("/analytics/{symbol}", response_model=AnalyticsResponse)
def get_analytics(
    symbol: str,
    window: int = Query(5, ge=2, le=250),
    limit: int = Query(90, ge=2, le=2000),
):
    """Derived analytics for a symbol: latest close, moving average,
    rolling volatility, and most recent daily return."""
    conn = get_conn()
    try:
        rows = db.get_closes(conn, symbol, limit=limit)
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No data for '{symbol}' yet — POST /ingest/{symbol} first.",
            )
        closes = [c for _, c in rows]
        summary = latest_summary(closes, ma_window=window, vol_window=window)
        return AnalyticsResponse(symbol=symbol, window=window, **summary)
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}
