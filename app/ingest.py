"""
ETL pipeline: Extract daily commodity/economic price history from the
Federal Reserve's public FRED API, Transform it into clean rows, and Load
it into the local SQLite database.

FRED series used for commodities (examples — all daily):
    DCOILWTICO   = Crude Oil Prices: West Texas Intermediate (WTI)
    DCOILBRENTEU = Crude Oil Prices: Brent - Europe
    DHHNGSP      = Henry Hub Natural Gas Spot Price

Full catalog: https://fred.stlouisfed.org/

Requires a free FRED API key, read from the FRED_API_KEY environment
variable (see .env.example). Network access lives ONLY in
fetch_fred_series() below. Every other function in this module is
pure/deterministic and is exercised directly in tests/test_ingest.py with
a synthetic FRED-shaped JSON payload, so the parsing and loading logic is
verified without needing a live network call or a real API key.
"""
from __future__ import annotations

import os
import sqlite3
from typing import List

import requests

from . import db

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(series_id: str, api_key: str, timeout: float = 10.0) -> dict:
    """Extract: download the full observation history for a FRED series.

    Raises requests.HTTPError on a non-200 response (e.g. an invalid
    series_id or API key) and ValueError if FRED's response doesn't look
    like the shape we expect.
    """
    resp = requests.get(
        FRED_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "observations" not in payload:
        raise ValueError(
            f"Unexpected FRED response for series '{series_id}': {payload}"
        )
    return payload


def parse_fred_observations(payload: dict) -> List[dict]:
    """Transform: parse a FRED observations payload into row dicts
    matching the columns db.upsert_rows() expects.

    FRED gives one value per date (no open/high/low/volume), so this
    fills the price into `close` and leaves the other OHLC fields as
    None. FRED represents a missing reading (e.g. a market holiday) as
    the literal string "." — those rows are skipped rather than stored
    as a fake zero.
    """
    rows: List[dict] = []
    for obs in payload.get("observations", []):
        raw_value = obs.get("value")
        if raw_value in (None, ".", ""):
            continue
        try:
            close = float(raw_value)
        except ValueError:
            continue
        rows.append(
            {
                "date": obs["date"],
                "open": None,
                "high": None,
                "low": None,
                "close": close,
                "volume": None,
            }
        )
    return rows


def run_ingest(series_id: str, conn: sqlite3.Connection, api_key: str = None) -> int:
    """Extract + Transform + Load for one FRED series against an
    already-open DB connection. Returns the number of rows written.

    The series_id doubles as the "symbol" stored in the database, so the
    rest of the app (db.py, the API routes) doesn't need to know or care
    that the data now comes from FRED instead of a ticker-based source.
    """
    api_key = api_key or os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError(
            "No FRED API key found. Set FRED_API_KEY in your .env file "
            "(see .env.example) or pass api_key explicitly."
        )
    payload = fetch_fred_series(series_id, api_key)
    rows = parse_fred_observations(payload)
    return db.upsert_rows(conn, series_id, rows)
